import logging
import html
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.database import get_db
from backend.config import INFORMES_PATH, COMUNA_INFO

logger = logging.getLogger("gaceta")
router = APIRouter(prefix="/api/gaceta", tags=["Gaceta Comunal (Art. 41 LOC)"])


class NuevaDecisionRequest(BaseModel):
    numero: Optional[str] = ""
    fecha: str
    titulo: str
    tipo_decision: str = "Acuerdo"  # Ley Comunal, Acuerdo, Resolución, Decreto
    contenido: str
    parlamento_sesion: Optional[str] = ""
    aprobado_por: Optional[str] = ""
    publicada: Optional[int] = 1


@router.get("/siguiente-numero")
async def obtener_siguiente_numero_gaceta():
    """Genera el siguiente correlativo para la Gaceta Comunal: GC-CPPO-YYYY-0001."""
    ano = datetime.now().year
    prefijo = f"GC-CPPO-{ano}"
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT numero FROM gaceta_comunal WHERE numero LIKE ? ORDER BY id DESC LIMIT 1",
            (f"{prefijo}%",)
        )
        row = await cursor.fetchone()
        if row and row[0]:
            try:
                seq = int(row[0].split("-")[-1]) + 1
            except Exception:
                seq = 1
        else:
            seq = 1
        return {"numero": f"{prefijo}-{seq:04d}"}


@router.get("")
async def listar_gaceta(
    tipo_decision: Optional[str] = Query(None),
    publicada: Optional[int] = Query(None)
):
    """Lista las publicaciones de la Gaceta Comunal."""
    async with await get_db() as db:
        filtros = []
        params = []
        if tipo_decision:
            filtros.append("tipo_decision = ?")
            params.append(tipo_decision)
        if publicada is not None:
            filtros.append("publicada = ?")
            params.append(publicada)

        where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ""
        sql = f"""
            SELECT * FROM gaceta_comunal
            {where_clause}
            ORDER BY fecha DESC, id DESC
        """
        cursor = await db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


@router.get("/{gaceta_id}")
async def detalle_decision(gaceta_id: int):
    """Retorna el contenido íntegro de una publicación en la Gaceta."""
    async with await get_db() as db:
        cursor = await db.execute("SELECT * FROM gaceta_comunal WHERE id = ?", (gaceta_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Decisión o gaceta no encontrada")
        return dict(row)


@router.post("")
async def registrar_decision(req: NuevaDecisionRequest):
    """Registra y publica una decisión del Parlamento Comunal en la Gaceta."""
    titulo = req.titulo.strip() if req.titulo else ""
    if not titulo:
        raise HTTPException(status_code=400, detail="El título de la decisión es obligatorio")
    contenido = req.contenido.strip() if req.contenido else ""
    if not contenido:
        raise HTTPException(status_code=400, detail="El contenido de la decisión es obligatorio")
    fecha = req.fecha.strip() if req.fecha else ""
    if not fecha:
        raise HTTPException(status_code=400, detail="La fecha es obligatoria")
    if req.publicada not in (0, 1):
        raise HTTPException(status_code=400, detail="El campo 'publicada' debe ser 0 o 1")

    numero = req.numero.strip() if req.numero else ""
    if not numero:
        siguiente = await obtener_siguiente_numero_gaceta()
        numero = siguiente["numero"]

    async with await get_db() as db:
        # Verificar UNIQUE en numero
        cur_uniq = await db.execute("SELECT id FROM gaceta_comunal WHERE numero = ?", (numero,))
        if await cur_uniq.fetchone():
            raise HTTPException(status_code=400, detail=f"Ya existe una publicación con el número '{numero}' en la Gaceta Comunal")

        cursor = await db.execute("""
            INSERT INTO gaceta_comunal (
                numero, fecha, titulo, tipo_decision, contenido,
                parlamento_sesion, aprobado_por, publicada
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            numero, fecha, titulo, req.tipo_decision, contenido,
            req.parlamento_sesion or "", req.aprobado_por or "", req.publicada if req.publicada is not None else 1
        ))
        gaceta_id = cursor.lastrowid
        await db.commit()
        return {"status": "success", "id": gaceta_id, "numero": numero, "message": "Publicado en Gaceta Comunal"}


@router.get("/{gaceta_id}/pdf")
async def generar_pdf_gaceta(gaceta_id: int):
    """Genera el documento oficial PDF de la decisión en Gaceta Comunal."""
    async with await get_db() as db:
        cursor = await db.execute("SELECT * FROM gaceta_comunal WHERE id = ?", (gaceta_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Publicación no encontrada")
        
        datos = dict(row)

    # Escapar caracteres HTML y formatear saltos de línea para PDF seguro
    titulo_esc = html.escape(datos.get('titulo') or 'Sin título')
    contenido_esc = html.escape(datos.get('contenido') or '').replace('\n', '<br>')
    numero_esc = html.escape(datos.get('numero') or '')
    fecha_esc = html.escape(datos.get('fecha') or '')
    tipo_esc = html.escape(datos.get('tipo_decision') or 'Acuerdo')
    sesion_esc = html.escape(datos.get('parlamento_sesion') or 'Ordinaria')
    aprobado_esc = html.escape(datos.get('aprobado_por') or 'Parlamento Comunal en Pleno')

    # Crear el PDF con xhtml2pdf
    nombre_archivo = f"Gaceta_{datos['numero'].replace('-', '_')}.pdf"
    pdf_filepath = INFORMES_PATH / nombre_archivo

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: letter;
                margin: 2.5cm 2cm;
            }}
            body {{
                font-family: 'Helvetica Neue', Arial, sans-serif;
                color: #1a202c;
                line-height: 1.6;
                font-size: 11pt;
            }}
            .header-gaceta {{
                text-align: center;
                border-bottom: 2px solid #2b6cb0;
                padding-bottom: 15px;
                margin-bottom: 25px;
            }}
            .republica {{ font-size: 10pt; font-weight: bold; text-transform: uppercase; color: #4a5568; }}
            .comuna {{ font-size: 14pt; font-weight: bold; color: #1a365d; text-transform: uppercase; }}
            .rif {{ font-size: 9pt; color: #718096; }}
            .titulo-gaceta {{
                text-align: center;
                font-size: 18pt;
                font-weight: bold;
                color: #2b6cb0;
                margin: 15px 0 5px 0;
                letter-spacing: 1px;
            }}
            .numero-gaceta {{
                text-align: center;
                font-size: 12pt;
                font-weight: bold;
                color: #e53e3e;
                margin-bottom: 20px;
            }}
            .meta-box {{
                background-color: #f7fafc;
                border: 1px solid #e2e8f0;
                padding: 12px;
                border-radius: 6px;
                margin-bottom: 25px;
                font-size: 9.5pt;
            }}
            .decision-titulo {{
                font-size: 14pt;
                font-weight: bold;
                color: #2d3748;
                margin-bottom: 15px;
                text-align: center;
            }}
            .contenido {{
                text-align: justify;
                margin-bottom: 40px;
            }}
            .firma-box {{
                text-align: center;
                margin-top: 50px;
                page-break-inside: avoid;
            }}
            .linea-firma {{
                width: 250px;
                border-top: 1px solid #4a5568;
                margin: 0 auto 5px auto;
            }}
        </style>
    </head>
    <body>
        <div class="header-gaceta">
            <div class="republica">República Bolivariana de Venezuela</div>
            <div class="comuna">{COMUNA_INFO.get('nombre', 'Comuna Productiva Presidente Obrero')}</div>
            <div class="rif">Código Comunal: C-MIX-2018-11-0019 | RIF: {COMUNA_INFO.get('rif', '')}</div>
        </div>

        <div class="titulo-gaceta">GACETA COMUNAL OFICIAL</div>
        <div class="numero-gaceta">{numero_esc} — FECHA: {fecha_esc}</div>

        <div class="meta-box">
            <strong>Tipo de Decisión:</strong> {tipo_esc}<br>
            <strong>Sesión del Parlamento:</strong> {sesion_esc}<br>
            <strong>Aprobado por:</strong> {aprobado_esc}
        </div>

        <div class="decision-titulo">{titulo_esc}</div>

        <div class="contenido">
            {contenido_esc}
        </div>

        <div class="firma-box">
            <div class="linea-firma"></div>
            <strong>{aprobado_esc}</strong><br>
            <span style="font-size: 9pt; color: #718096;">Doy fe de la autenticidad y promulgación</span>
        </div>
    </body>
    </html>
    """

    try:
        from xhtml2pdf import pisa
        with open(pdf_filepath, "w+b") as result_file:
            pisa_status = pisa.CreatePDF(html_content, dest=result_file, encoding='utf-8')
        
        if pisa_status.err:
            raise HTTPException(status_code=500, detail="Error al generar el PDF de la Gaceta")

        # Guardar ruta en BD
        async with await get_db() as db:
            await db.execute("UPDATE gaceta_comunal SET pdf_path = ? WHERE id = ?", (str(pdf_filepath), gaceta_id))
            await db.commit()

        return {
            "status": "success",
            "pdf_url": f"/informes/{nombre_archivo}",
            "pdf_path": str(pdf_filepath)
        }
    except Exception as e:
        logger.error(f"Error generando PDF de gaceta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al generar el PDF de la Gaceta Comunal")

