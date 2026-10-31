import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.database import get_db

logger = logging.getLogger("rendiciones")
router = APIRouter(prefix="/api/rendiciones", tags=["Rendición de Cuentas (Art. 52 LOC)"])


class NuevaRendicionRequest(BaseModel):
    periodo: str
    instancia_id: Optional[int] = None
    comision_id: Optional[int] = None
    tipo: str = "Ordinaria"
    fecha_rendicion: str
    presupuesto_asignado: float = 0.0
    presupuesto_ejecutado: float = 0.0
    descripcion_logros: str
    observaciones: Optional[str] = ""
    aprobada: Optional[int] = 0


class EstadoAprobacionRequest(BaseModel):
    aprobada: int  # 0: Pendiente, 1: Aprobada, 2: Rechazada
    observaciones: Optional[str] = ""


@router.get("")
async def listar_rendiciones(
    periodo: Optional[str] = Query(None),
    instancia_id: Optional[int] = Query(None),
    comision_id: Optional[int] = Query(None)
):
    """Lista las rendiciones de cuentas con nombres de instancias y comisiones."""
    async with await get_db() as db:
        filtros = []
        params = []
        if periodo:
            filtros.append("r.periodo = ?")
            params.append(periodo)
        if instancia_id:
            filtros.append("r.instancia_id = ?")
            params.append(instancia_id)
        if comision_id:
            filtros.append("r.comision_id = ?")
            params.append(comision_id)

        where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ""

        sql = f"""
            SELECT r.*,
                   i.nombre as instancia_nombre,
                   c.nombre as comision_nombre
            FROM rendiciones_cuentas r
            LEFT JOIN instancias_gobierno i ON r.instancia_id = i.id
            LEFT JOIN comisiones_gestion c ON r.comision_id = c.id
            {where_clause}
            ORDER BY r.fecha_rendicion DESC, r.id DESC
        """
        cursor = await db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


@router.get("/resumen")
async def resumen_presupuestario():
    """Retorna totales financieros de asignación y ejecución para control comunal."""
    async with await get_db() as db:
        cursor = await db.execute("""
            SELECT 
                COUNT(*) as total_rendiciones,
                SUM(presupuesto_asignado) as total_asignado,
                SUM(presupuesto_ejecutado) as total_ejecutado,
                SUM(CASE WHEN aprobada = 1 THEN 1 ELSE 0 END) as total_aprobadas,
                SUM(CASE WHEN aprobada = 2 THEN 1 ELSE 0 END) as total_rechazadas,
                SUM(CASE WHEN aprobada = 0 THEN 1 ELSE 0 END) as total_pendientes
            FROM rendiciones_cuentas
        """)
        row = await cursor.fetchone()
        totales = dict(row) if row else {}

        # Desglose por instancia
        cur_inst = await db.execute("""
            SELECT i.nombre,
                   SUM(r.presupuesto_asignado) as asignado,
                   SUM(r.presupuesto_ejecutado) as ejecutado,
                   COUNT(r.id) as rendiciones
            FROM instancias_gobierno i
            JOIN rendiciones_cuentas r ON r.instancia_id = i.id
            GROUP BY i.id, i.nombre
        """)
        totales["por_instancia"] = [dict(r) for r in await cur_inst.fetchall()]

        return totales


@router.get("/{rendicion_id}")
async def detalle_rendicion(rendicion_id: int):
    """Retorna los detalles de una rendición de cuentas específica."""
    async with await get_db() as db:
        cursor = await db.execute("""
            SELECT r.*,
                   i.nombre as instancia_nombre,
                   c.nombre as comision_nombre
            FROM rendiciones_cuentas r
            LEFT JOIN instancias_gobierno i ON r.instancia_id = i.id
            LEFT JOIN comisiones_gestion c ON r.comision_id = c.id
            WHERE r.id = ?
        """, (rendicion_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Rendición no encontrada")
        return dict(row)


@router.post("")
async def registrar_rendicion(req: NuevaRendicionRequest):
    """Registra una nueva rendición de cuentas (anual o periódica)."""
    periodo = req.periodo.strip() if req.periodo else ""
    if not periodo:
        raise HTTPException(status_code=400, detail="El campo 'periodo' es obligatorio (ej: 2024)")
    logros = req.descripcion_logros.strip() if req.descripcion_logros else ""
    if not logros:
        raise HTTPException(status_code=400, detail="La descripción de logros es obligatoria")
    fecha = req.fecha_rendicion.strip() if req.fecha_rendicion else ""
    if not fecha:
        raise HTTPException(status_code=400, detail="La fecha de rendición es obligatoria")
    if req.presupuesto_asignado < 0:
        raise HTTPException(status_code=400, detail="El presupuesto asignado no puede ser negativo")
    if req.presupuesto_ejecutado < 0:
        raise HTTPException(status_code=400, detail="El presupuesto ejecutado no puede ser negativo")
    if req.aprobada not in (0, 1, 2):
        raise HTTPException(status_code=400, detail="El campo 'aprobada' debe ser 0, 1 o 2")

    async with await get_db() as db:
        if req.instancia_id is not None:
            cur_inst = await db.execute("SELECT id FROM instancias_gobierno WHERE id = ?", (req.instancia_id,))
            if not await cur_inst.fetchone():
                raise HTTPException(status_code=404, detail="Instancia de gobierno no encontrada")
        if req.comision_id is not None:
            cur_com = await db.execute("SELECT id FROM comisiones_gestion WHERE id = ?", (req.comision_id,))
            if not await cur_com.fetchone():
                raise HTTPException(status_code=404, detail="Comisión de gestión no encontrada")

        cursor = await db.execute("""
            INSERT INTO rendiciones_cuentas (
                periodo, instancia_id, comision_id, tipo, fecha_rendicion,
                presupuesto_asignado, presupuesto_ejecutado, descripcion_logros,
                observaciones, aprobada
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            periodo, req.instancia_id, req.comision_id, req.tipo, fecha,
            req.presupuesto_asignado, req.presupuesto_ejecutado, logros,
            req.observaciones or "", req.aprobada or 0
        ))
        rend_id = cursor.lastrowid
        await db.commit()
        return {"status": "success", "id": rend_id, "message": "Rendición de cuentas registrada"}


@router.post("/{rendicion_id}/aprobar")
async def cambiar_estado_rendicion(rendicion_id: int, req: EstadoAprobacionRequest):
    """Actualiza la aprobación de una rendición por el Parlamento o Contraloría."""
    if req.aprobada not in (0, 1, 2):
        raise HTTPException(status_code=400, detail="El campo 'aprobada' debe ser 0 (pendiente), 1 (aprobada) o 2 (rechazada)")
    async with await get_db() as db:
        cur_ex = await db.execute("SELECT id FROM rendiciones_cuentas WHERE id = ?", (rendicion_id,))
        if not await cur_ex.fetchone():
            raise HTTPException(status_code=404, detail="Rendición de cuentas no encontrada")
        await db.execute("""
            UPDATE rendiciones_cuentas
            SET aprobada = ?, observaciones = ?
            WHERE id = ?
        """, (req.aprobada, req.observaciones or "", rendicion_id))
        await db.commit()
        return {"status": "success", "message": "Estado de rendición actualizado"}

