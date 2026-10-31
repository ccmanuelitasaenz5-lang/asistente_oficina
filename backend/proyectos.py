import logging
import io
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from backend.database import get_db

logger = logging.getLogger("proyectos")
router = APIRouter(prefix="/api/proyectos", tags=["Proyectos ACA (Agenda Concreta de Acción)"])


class NuevoProyectoRequest(BaseModel):
    nombre: str
    codigo_proyecto: Optional[str] = ""
    descripcion: Optional[str] = ""
    comision_id: Optional[int] = None
    consejo_id: Optional[int] = None
    monto_estimado: Optional[float] = 0.0
    monto_ejecutado: Optional[float] = 0.0
    fecha_inicio: Optional[str] = ""
    fecha_fin_estimada: Optional[str] = ""
    estado: Optional[str] = "planificado"
    porcentaje_avance: Optional[int] = 0
    beneficiarios: Optional[int] = 0
    observaciones: Optional[str] = ""
    # Campos Oficiales Matriz ACA (7T)
    transformacion_7t: Optional[str] = ""
    voceria_vinculada: Optional[str] = ""
    nudo_critico: Optional[str] = ""
    potencialidades: Optional[str] = ""
    accion_ejecutar: Optional[str] = ""
    requerimiento: Optional[str] = ""
    tiempo_ejecucion: Optional[str] = "Corto Plazo"


class EditarProyectoRequest(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    comision_id: Optional[int] = None
    consejo_id: Optional[int] = None
    monto_estimado: Optional[float] = None
    monto_ejecutado: Optional[float] = None
    estado: Optional[str] = None
    porcentaje_avance: Optional[int] = None
    beneficiarios: Optional[int] = None
    observaciones: Optional[str] = None
    transformacion_7t: Optional[str] = None
    voceria_vinculada: Optional[str] = None
    nudo_critico: Optional[str] = None
    potencialidades: Optional[str] = None
    accion_ejecutar: Optional[str] = None
    requerimiento: Optional[str] = None
    tiempo_ejecucion: Optional[str] = None


class ActualizarAvanceRequest(BaseModel):
    porcentaje_avance: int
    monto_ejecutado: Optional[float] = None
    estado: Optional[str] = None
    observaciones: Optional[str] = ""


@router.get("")
async def listar_proyectos(
    transformacion: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    comision_id: Optional[int] = Query(None),
    consejo_id: Optional[int] = Query(None)
):
    """Lista los proyectos de la Agenda Concreta de Acción (ACA)."""
    async with await get_db() as db:
        filtros = []
        params = []
        if transformacion:
            filtros.append("p.transformacion_7t LIKE ?")
            params.append(f"%{transformacion.strip()}%")
        if estado:
            filtros.append("p.estado = ?")
            params.append(estado)
        if comision_id:
            filtros.append("p.comision_id = ?")
            params.append(comision_id)
        if consejo_id:
            filtros.append("p.consejo_id = ?")
            params.append(consejo_id)

        where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ""
        sql = f"""
            SELECT p.*,
                   c.nombre as comision_nombre,
                   cc.nombre as consejo_nombre
            FROM proyectos_aca p
            LEFT JOIN comisiones_gestion c ON p.comision_id = c.id
            LEFT JOIN consejos_comunales cc ON p.consejo_id = cc.id
            {where_clause}
            ORDER BY p.id DESC
        """
        cursor = await db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


@router.get("/dashboard")
async def dashboard_proyectos():
    """Retorna KPIs y métricas de avance de los proyectos comunales."""
    async with await get_db() as db:
        cur_kpi = await db.execute("""
            SELECT 
                COUNT(*) as total_proyectos,
                COALESCE(SUM(monto_estimado), 0) as inversion_total_estimada,
                COALESCE(SUM(monto_ejecutado), 0) as inversion_ejecutada,
                COALESCE(SUM(beneficiarios), 0) as total_beneficiarios,
                COALESCE(AVG(porcentaje_avance), 0) as avance_promedio,
                SUM(CASE WHEN estado = 'planificado' THEN 1 ELSE 0 END) as planificados,
                SUM(CASE WHEN estado = 'en_ejecucion' THEN 1 ELSE 0 END) as en_ejecucion,
                SUM(CASE WHEN estado = 'completado' THEN 1 ELSE 0 END) as completados,
                SUM(CASE WHEN estado = 'suspendido' THEN 1 ELSE 0 END) as suspendidos
            FROM proyectos_aca
        """)
        row = await cur_kpi.fetchone()
        kpis = dict(row) if row else {}

        # Distribución por Transformación 7T
        cur_7t = await db.execute("""
            SELECT COALESCE(NULLIF(transformacion_7t, ''), 'Otras') as transformacion,
                   COUNT(id) as cantidad
            FROM proyectos_aca
            GROUP BY transformacion
            ORDER BY transformacion ASC
        """)
        kpis["por_transformacion"] = [dict(r) for r in await cur_7t.fetchall()]

        # Distribución por comisiones
        cur_com = await db.execute("""
            SELECT c.nombre, COUNT(p.id) as cantidad, COALESCE(SUM(p.monto_estimado), 0) as monto
            FROM comisiones_gestion c
            JOIN proyectos_aca p ON p.comision_id = c.id
            GROUP BY c.id, c.nombre
        """)
        kpis["por_comision"] = [dict(r) for r in await cur_com.fetchall()]

        return kpis


@router.get("/{proyecto_id}")
async def detalle_proyecto(proyecto_id: int):
    """Retorna la ficha técnica de un proyecto comunal."""
    async with await get_db() as db:
        cursor = await db.execute("""
            SELECT p.*,
                   c.nombre as comision_nombre,
                   cc.nombre as consejo_nombre
            FROM proyectos_aca p
            LEFT JOIN comisiones_gestion c ON p.comision_id = c.id
            LEFT JOIN consejos_comunales cc ON p.consejo_id = cc.id
            WHERE p.id = ?
        """, (proyecto_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")
        return dict(row)


@router.post("")
async def crear_proyecto(req: NuevoProyectoRequest):
    """Registra un nuevo proyecto en la Agenda Concreta de Acción (ACA 7T)."""
    nombre = req.nombre.strip() if req.nombre else ""
    if not nombre and req.accion_ejecutar:
        nombre = req.accion_ejecutar.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre o acción a ejecutar es obligatorio")

    porcentaje = req.porcentaje_avance if req.porcentaje_avance is not None else 0
    if not (0 <= porcentaje <= 100):
        raise HTTPException(status_code=400, detail="El porcentaje de avance debe estar entre 0 y 100")
    monto_est = req.monto_estimado if req.monto_estimado is not None else 0.0
    if monto_est < 0:
        raise HTTPException(status_code=400, detail="El monto estimado no puede ser negativo")
    monto_eje = req.monto_ejecutado if req.monto_ejecutado is not None else 0.0
    if monto_eje < 0:
        raise HTTPException(status_code=400, detail="El monto ejecutado no puede ser negativo")
    beneficiarios = req.beneficiarios if req.beneficiarios is not None else 0
    if beneficiarios < 0:
        raise HTTPException(status_code=400, detail="El número de beneficiarios no puede ser negativo")

    codigo = req.codigo_proyecto.strip() if req.codigo_proyecto else ""

    async with await get_db() as db:
        if req.comision_id is not None:
            cur_com = await db.execute("SELECT id FROM comisiones_gestion WHERE id = ?", (req.comision_id,))
            if not await cur_com.fetchone():
                raise HTTPException(status_code=404, detail="Comisión de gestión no encontrada")
        if req.consejo_id is not None:
            cur_cc = await db.execute("SELECT id FROM consejos_comunales WHERE id = ?", (req.consejo_id,))
            if not await cur_cc.fetchone():
                raise HTTPException(status_code=404, detail="Consejo Comunal no encontrado")

        if not codigo:
            ano = datetime.now().year
            cur_seq = await db.execute("SELECT COUNT(*) FROM proyectos_aca")
            seq = (await cur_seq.fetchone())[0] + 1
            codigo = f"ACA-CPPO-{ano}-{seq:03d}"
        else:
            cur_uniq = await db.execute("SELECT id FROM proyectos_aca WHERE codigo_proyecto = ?", (codigo,))
            if await cur_uniq.fetchone():
                raise HTTPException(status_code=400, detail=f"Ya existe un proyecto con el código '{codigo}'")

        cursor = await db.execute("""
            INSERT INTO proyectos_aca (
                nombre, codigo_proyecto, descripcion, comision_id, consejo_id,
                monto_estimado, monto_ejecutado, fecha_inicio, fecha_fin_estimada,
                estado, porcentaje_avance, beneficiarios, observaciones,
                transformacion_7t, voceria_vinculada, nudo_critico, potencialidades,
                accion_ejecutar, requerimiento, tiempo_ejecucion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            nombre, codigo, req.descripcion or "", req.comision_id, req.consejo_id,
            monto_est, monto_eje, req.fecha_inicio or "",
            req.fecha_fin_estimada or "", req.estado or "planificado",
            porcentaje, beneficiarios, req.observaciones or "",
            req.transformacion_7t or "", req.voceria_vinculada or "",
            req.nudo_critico or "", req.potencialidades or "",
            req.accion_ejecutar or nombre, req.requerimiento or "",
            req.tiempo_ejecucion or "Corto Plazo"
        ))
        pid = cursor.lastrowid
        await db.commit()
        return {"status": "success", "id": pid, "codigo_proyecto": codigo, "message": "Proyecto guardado exitosamente"}


@router.put("/{proyecto_id}")
async def editar_proyecto(proyecto_id: int, req: EditarProyectoRequest):
    """Permite editar cualquier campo del proyecto/nudo crítico del ACA."""
    async with await get_db() as db:
        cur_ex = await db.execute("SELECT id FROM proyectos_aca WHERE id = ?", (proyecto_id,))
        if not await cur_ex.fetchone():
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")

        campos = []
        valores = []

        if req.nombre is not None:
            campos.append("nombre = ?")
            valores.append(req.nombre.strip())
        if req.descripcion is not None:
            campos.append("descripcion = ?")
            valores.append(req.descripcion.strip())
        if req.comision_id is not None:
            campos.append("comision_id = ?")
            valores.append(req.comision_id)
        if req.consejo_id is not None:
            campos.append("consejo_id = ?")
            valores.append(req.consejo_id)
        if req.monto_estimado is not None:
            if req.monto_estimado < 0:
                raise HTTPException(status_code=400, detail="El monto estimado no puede ser negativo")
            campos.append("monto_estimado = ?")
            valores.append(req.monto_estimado)
        if req.monto_ejecutado is not None:
            if req.monto_ejecutado < 0:
                raise HTTPException(status_code=400, detail="El monto ejecutado no puede ser negativo")
            campos.append("monto_ejecutado = ?")
            valores.append(req.monto_ejecutado)
        if req.estado is not None:
            campos.append("estado = ?")
            valores.append(req.estado)
        if req.porcentaje_avance is not None:
            if not (0 <= req.porcentaje_avance <= 100):
                raise HTTPException(status_code=400, detail="El avance debe estar entre 0 y 100")
            campos.append("porcentaje_avance = ?")
            valores.append(req.porcentaje_avance)
        if req.beneficiarios is not None:
            if req.beneficiarios < 0:
                raise HTTPException(status_code=400, detail="Beneficiarios no puede ser negativo")
            campos.append("beneficiarios = ?")
            valores.append(req.beneficiarios)
        if req.observaciones is not None:
            campos.append("observaciones = ?")
            valores.append(req.observaciones.strip())
        if req.transformacion_7t is not None:
            campos.append("transformacion_7t = ?")
            valores.append(req.transformacion_7t.strip())
        if req.voceria_vinculada is not None:
            campos.append("voceria_vinculada = ?")
            valores.append(req.voceria_vinculada.strip())
        if req.nudo_critico is not None:
            campos.append("nudo_critico = ?")
            valores.append(req.nudo_critico.strip())
        if req.potencialidades is not None:
            campos.append("potencialidades = ?")
            valores.append(req.potencialidades.strip())
        if req.accion_ejecutar is not None:
            campos.append("accion_ejecutar = ?")
            valores.append(req.accion_ejecutar.strip())
        if req.requerimiento is not None:
            campos.append("requerimiento = ?")
            valores.append(req.requerimiento.strip())
        if req.tiempo_ejecucion is not None:
            campos.append("tiempo_ejecucion = ?")
            valores.append(req.tiempo_ejecucion.strip())

        if not campos:
            return {"status": "no_changes"}

        valores.append(proyecto_id)
        sql = f"UPDATE proyectos_aca SET {', '.join(campos)} WHERE id = ?"
        await db.execute(sql, tuple(valores))
        await db.commit()
        return {"status": "success", "message": "Proyecto/Acción actualizada exitosamente"}


@router.delete("/{proyecto_id}")
async def eliminar_proyecto(proyecto_id: int):
    """Elimina una acción o nudo crítico resuelto o descartado de la ACA."""
    async with await get_db() as db:
        cur_ex = await db.execute("SELECT id FROM proyectos_aca WHERE id = ?", (proyecto_id,))
        if not await cur_ex.fetchone():
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")
        await db.execute("DELETE FROM proyectos_aca WHERE id = ?", (proyecto_id,))
        await db.commit()
        return {"status": "success", "message": "Proyecto/Acción eliminada exitosamente"}


@router.put("/{proyecto_id}/avance")
async def actualizar_avance(proyecto_id: int, req: ActualizarAvanceRequest):
    """Actualiza el porcentaje de ejecución física y presupuestaria del proyecto."""
    if not (0 <= req.porcentaje_avance <= 100):
        raise HTTPException(status_code=400, detail="El porcentaje de avance debe estar entre 0 y 100")
    if req.monto_ejecutado is not None and req.monto_ejecutado < 0:
        raise HTTPException(status_code=400, detail="El monto ejecutado no puede ser negativo")
    async with await get_db() as db:
        cur_ex = await db.execute("SELECT id FROM proyectos_aca WHERE id = ?", (proyecto_id,))
        if not await cur_ex.fetchone():
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")
        campos = ["porcentaje_avance = ?"]
        valores = [req.porcentaje_avance]

        if req.monto_ejecutado is not None:
            campos.append("monto_ejecutado = ?")
            valores.append(req.monto_ejecutado)

        if req.estado:
            campos.append("estado = ?")
            valores.append(req.estado)
        elif req.porcentaje_avance >= 100:
            campos.append("estado = 'completado'")
        elif req.porcentaje_avance > 0:
            campos.append("estado = 'en_ejecucion'")

        if req.observaciones:
            campos.append("observaciones = ?")
            valores.append(req.observaciones)

        valores.append(proyecto_id)
        sql = f"UPDATE proyectos_aca SET {', '.join(campos)} WHERE id = ?"
        await db.execute(sql, tuple(valores))
        await db.commit()
        return {"status": "success", "message": "Avance de proyecto actualizado"}


@router.post("/importar-docx")
async def importar_matriz_docx(file: UploadFile = File(...)):
    """
    Importa y extrae automáticamente las filas de la Matriz ACA (7T)
    desde un archivo Microsoft Word (.docx). Retorna la lista extraída para revisión.
    """
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="El archivo debe tener extensión .docx")

    try:
        import docx
        MAX_DOCX_SIZE = 20 * 1024 * 1024  # 20 MB
        contents = await file.read()
        if len(contents) > MAX_DOCX_SIZE:
            raise HTTPException(status_code=400, detail="El archivo Word excede el tamaño máximo permitido (20 MB)")
        doc = docx.Document(io.BytesIO(contents))
        filas_extraidas = []

        transformacion_actual = "1T. Transformación Económica"

        for table in doc.tables:
            for row in table.rows:
                celdas = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                if not any(celdas):
                    continue

                texto_primera = celdas[0]

                # Detectar encabezado de transformación
                for num_t in ["1T", "2T", "3T", "4T", "5T", "6T", "7T"]:
                    if num_t in texto_primera.upper():
                        transformacion_actual = texto_primera[:100]
                        break

                # Si es fila de datos (tiene al menos 5 columnas y no es encabezado repetido)
                if len(celdas) >= 6 and "TRANSFORMACIÓN" not in celdas[0].upper() and "PROBLEMA" not in celdas[1].upper():
                    voceria = celdas[1] if len(celdas) > 1 else ""
                    nudo = celdas[2] if len(celdas) > 2 else ""
                    potencial = celdas[3] if len(celdas) > 3 else ""
                    accion = celdas[4] if len(celdas) > 4 else ""
                    requerimiento = celdas[5] if len(celdas) > 5 else ""
                    tiempo = celdas[6] if len(celdas) > 6 else "Corto Plazo"

                    if any([nudo, accion, requerimiento]):
                        filas_extraidas.append({
                            "transformacion_7t": transformacion_actual,
                            "voceria_vinculada": voceria,
                            "nudo_critico": nudo,
                            "potencialidades": potencial,
                            "accion_ejecutar": accion or nudo,
                            "requerimiento": requerimiento,
                            "tiempo_ejecucion": tiempo or "Corto Plazo",
                            "nombre": accion or nudo
                        })

        return {
            "status": "success",
            "total_extraidos": len(filas_extraidas),
            "proyectos": filas_extraidas
        }
    except Exception as e:
        logger.error(f"Error procesando docx: {e}")
        raise HTTPException(status_code=422, detail="Error al leer el archivo Word .docx. Verifique el formato de tablas del documento.")
