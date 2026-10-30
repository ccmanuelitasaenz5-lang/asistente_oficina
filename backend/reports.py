import html
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib
# Usar backend no interactivo para evitar fallos de interfaz gráfica en subprocesos
matplotlib.use('Agg')
import matplotlib.pyplot as plt
# WeasyPrint no disponible en este sistema; se genera HTML directamente
from backend.config import INFORMES_PATH, MEDIA_PATH, COMUNA_INFO
from backend.database import get_db
from backend.activities import obtener_actividades


logger = logging.getLogger("reports")

INFORMES_PATH.mkdir(parents=True, exist_ok=True)
MEDIA_PATH.mkdir(parents=True, exist_ok=True)

PLANTILLA_INFORME_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Informe de Gestión Comunal</title>
    <style>
        @page {{
            size: letter;
            margin: 2.5cm 2cm;
            @top-center {{
                content: element(header);
            }}
            @bottom-center {{
                content: element(footer);
            }}
        }}
        
        body {{
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            color: #2d3748;
            font-size: 11pt;
            line-height: 1.6;
        }}
        
        div.header {{
            position: running(header);
            border-bottom: 2px solid #2b6cb0;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        
        .header-title {{
            font-size: 13pt;
            font-weight: bold;
            color: #2b6cb0;
            text-transform: uppercase;
        }}
        
        .header-sub {{
            font-size: 9pt;
            color: #718096;
        }}
        
        div.footer {{
            position: running(footer);
            border-top: 1px solid #e2e8f0;
            padding-top: 5px;
            font-size: 8pt;
            color: #718096;
            text-align: center;
            width: 100%;
        }}
        
        .titulo-informe {{
            text-align: center;
            font-size: 20pt;
            font-weight: bold;
            color: #1a365d;
            margin-top: 20px;
            margin-bottom: 5px;
        }}
        
        .periodo-informe {{
            text-align: center;
            font-size: 11pt;
            color: #4a5568;
            margin-bottom: 30px;
        }}
        
        /* Tarjetas de estadísticas estilo premium */
        .grid-stats {{
            display: table;
            width: 100%;
            margin-bottom: 30px;
            border-spacing: 15px 0;
        }}
        
        .card-stat {{
            display: table-cell;
            background: #f7fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            width: 33%;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        }}
        
        .card-val {{
            font-size: 22pt;
            font-weight: bold;
            color: #2b6cb0;
        }}
        
        .card-lbl {{
            font-size: 9pt;
            color: #718096;
            text-transform: uppercase;
            font-weight: bold;
            margin-top: 5px;
        }}
        
        .galeria-collage {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            justify-content: center;
            margin: 30px 0;
            page-break-inside: avoid;
        }}
        
        .galeria-collage img {{
            width: 220px;
            height: 160px;
            object-fit: cover;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }}
        
        .page-break {{
            page-break-before: always;
        }}
        
        .titulo-seccion {{
            font-size: 14pt;
            font-weight: bold;
            color: #2b6cb0;
            border-bottom: 2px solid #edf2f7;
            padding-bottom: 5px;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        
        .actividad-item {{
            margin-bottom: 25px;
            padding-bottom: 20px;
            border-bottom: 1px solid #edf2f7;
            page-break-inside: avoid;
        }}
        
        .actividad-meta {{
            font-size: 9.5pt;
            color: #4a5568;
            margin-bottom: 8px;
        }}
        
        .badge-cat {{
            background: #ebf8ff;
            color: #2b6cb0;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 8.5pt;
        }}
        
        .actividad-desc {{
            text-align: justify;
            font-size: 10pt;
            color: #2d3748;
        }}
        
        .btn-imprimir {{
            display: block;
            margin: 20px auto;
            padding: 10px 20px;
            background-color: #2b6cb0;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 14pt;
            cursor: pointer;
            text-align: center;
        }}
        
        @media print {{
            .btn-imprimir {{
                display: none;
            }}
        }}
    </style>
</head>
<body>

    <button class="btn-imprimir" onclick="window.print()">🖨️ Imprimir Informe</button>

    <div class="header">
        <span class="header-title">{comuna_nombre}</span> - 
        <span class="header-sub">Informe Oficial de Gestión y Actividades</span>
    </div>

    <div class="footer">
        Comuna Productiva Presidente Obrero - Reporte generado automáticamente el {fecha_generacion}
    </div>

    <div class="titulo-informe">Informe de Actividades</div>
    <div class="periodo-informe">Período: {rango_fechas} ({tipo_informe})</div>

    <div class="grid-stats">
        <div class="card-stat">
            <div class="card-val">{total_actividades}</div>
            <div class="card-lbl">Actividades Realizadas</div>
        </div>
        <div class="card-stat">
            <div class="card-val">{total_participantes}</div>
            <div class="card-lbl">Participantes Totales</div>
        </div>
        <div class="card-stat">
            <div class="card-val">{promedio_participantes:.1f}</div>
            <div class="card-lbl">Prom. Participantes / Act.</div>
        </div>
    </div>

    {html_galeria}

    <div class="page-break"></div>

    <div class="titulo-seccion">Detalle de Actividades Realizadas</div>
    
    {html_actividades}

</body>
</html>
"""

def generar_grafico_estadisticas(actividades: list, filename: str) -> str:
    """Genera un gráfico de barra de actividades por categoría usando matplotlib."""
    if not actividades:
        return ""
        
    conteos = {}
    for act in actividades:
        cat = act["categoria"]
        conteos[cat] = conteos.get(cat, 0) + 1
        
    categorias = list(conteos.keys())
    valores = list(conteos.values())
    
    # Crear figura
    plt.figure(figsize=(7, 4))
    colors = ['#3182ce', '#319795', '#d69e2e', '#e53e3e', '#805ad5', '#38a169', '#dd6b20']
    
    plt.bar(categorias, valores, color=colors[:len(categorias)])
    plt.title("Cantidad de Actividades por Categoría", fontsize=12, fontweight='bold', pad=15)
    plt.xlabel("Categoría", fontsize=10)
    plt.ylabel("Número de Actividades", fontsize=10)
    plt.xticks(rotation=30, ha='right', fontsize=9)
    plt.tight_layout()
    
    grafico_path = MEDIA_PATH / filename
    plt.savefig(grafico_path, dpi=150)
    plt.close()
    
    # Retornar una URL relativa para que el servidor web la sirva
    return f"/media/{filename}"

async def generar_informe_pdf(periodo: str) -> dict:
    """
    Genera un informe consolidado en PDF para un periodo específico.
    Periodos: 'diario', 'semanal', 'mensual', 'anual'
    """
    hoy = datetime.now()
    fecha_fin = hoy.strftime("%Y-%m-%d")
    
    if periodo == "diario":
        fecha_inicio = fecha_fin
        tipo_str = "Diario"
    elif periodo == "semanal":
        fecha_inicio = (hoy - timedelta(days=7)).strftime("%Y-%m-%d")
        tipo_str = "Semanal"
    elif periodo == "mensual":
        fecha_inicio = (hoy - timedelta(days=30)).strftime("%Y-%m-%d")
        tipo_str = "Mensual"
    elif periodo == "anual":
        fecha_inicio = (hoy - timedelta(days=365)).strftime("%Y-%m-%d")
        tipo_str = "Anual"
    else:
        fecha_inicio = (hoy - timedelta(days=30)).strftime("%Y-%m-%d")
        tipo_str = "Personalizado"
        
    # Obtener actividades del periodo
    actividades = await obtener_actividades(fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    
    total_act = len(actividades)
    total_part = sum(a["participantes"] for a in actividades)
    promedio_part = total_part / total_act if total_act > 0 else 0.0
    
    todas_las_fotos = []
    
    # Construir HTML de las actividades y recolectar fotos
    html_actividades = ""
    if not actividades:
        html_actividades = "<p>No se registraron actividades en este periodo.</p>"
    else:
        for act in actividades:
            # Recolectar fotos
            if act["fotos"]:
                for foto in act["fotos"]:
                    nombre_foto = Path(foto).name
                    ruta_real = MEDIA_PATH / nombre_foto
                    if ruta_real.exists():
                        # Para xhtml2pdf usamos ruta absoluta local
                        todas_las_fotos.append(str(ruta_real.resolve()))

            # Formatear la fecha
            try:
                f_obj = datetime.strptime(act["fecha"], "%Y-%m-%d")
                fecha_formato = f_obj.strftime("%d/%m/%Y")
            except Exception:
                fecha_formato = act["fecha"]
                
            cat_esc = html.escape(str(act.get('categoria') or ''))
            desc_esc = html.escape(str(act.get('descripcion') or '')).replace('\n', '<br>')
            html_actividades += f"""
            <div class="actividad-item">
                <div class="actividad-meta">
                    <strong>Fecha:</strong> {fecha_formato} | 
                    <span class="badge-cat">{cat_esc}</span> | 
                    <strong>Participantes:</strong> {act['participantes']}
                </div>
                <div class="actividad-desc">
                    {desc_esc}
                </div>
            </div>
            """
            
    # Generar galeria (reemplazando el gráfico)
    html_galeria = ""
    if todas_las_fotos:
        html_galeria = '<div class="galeria-collage">'
        # Limitaremos a unas 8 fotos para que no sature la primera página
        for foto_url in todas_las_fotos[:8]:
            html_galeria += f'<img src="{foto_url}" alt="Foto de actividad">'
        html_galeria += '</div>'
            
    rango_fechas = f"Desde {fecha_inicio} hasta {fecha_fin}"
    fecha_generacion = hoy.strftime("%d/%m/%Y %I:%M %p")
    
    html_informe = PLANTILLA_INFORME_HTML.format(
        comuna_nombre=COMUNA_INFO["nombre"],
        fecha_generacion=fecha_generacion,
        tipo_informe=tipo_str,
        rango_fechas=rango_fechas,
        total_actividades=total_act,
        total_participantes=total_part,
        promedio_participantes=promedio_part,
        html_galeria=html_galeria,
        html_actividades=html_actividades
    )
    
    # Generar y guardar PDF usando xhtml2pdf
    nombre_archivo = f"Informe_Gestion_{tipo_str}_{hoy.strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_filepath = INFORMES_PATH / nombre_archivo
    
    try:
        from xhtml2pdf import pisa
        with open(pdf_filepath, "w+b") as result_file:
            pisa_status = pisa.CreatePDF(
                html_informe,
                dest=result_file,
                encoding='utf-8'
            )
        
        if pisa_status.err:
            logger.error(f"Error interno xhtml2pdf: {pisa_status.err}")
            pdf_path_str = ""
        else:
            logger.info(f"Informe PDF generado en: {pdf_filepath}")
            pdf_path_str = str(pdf_filepath.resolve())
    except ImportError:
        logger.error("xhtml2pdf no instalado.")
        pdf_path_str = ""
    except Exception as e:
        logger.error(f"Error generando PDF: {e}")
        pdf_path_str = ""
        
    return {
        "periodo": periodo,
        "tipo": tipo_str,
        "total_actividades": total_act,
        "total_participantes": total_part,
        "pdf_path": pdf_path_str,
        "nombre_archivo": nombre_archivo
    }
