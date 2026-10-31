import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.database import get_db

logger = logging.getLogger("instancias")
router = APIRouter(prefix="/api/instancias", tags=["Instancias de Gobierno"])


class VoceroInstanciaResponse(BaseModel):
    id: int
    vocero_id: int
    nombre: str
    cedula: Optional[str] = ""
    telefono: Optional[str] = ""
    cargo_origen: Optional[str] = ""
    consejo_nombre: Optional[str] = ""
    cargo_instancia: str
    fecha_designacion: Optional[str] = ""
    activo: int


class InstanciaResponse(BaseModel):
    id: int
    nombre: str
    tipo: str
    descripcion: Optional[str] = ""
    base_legal: Optional[str] = ""
    fecha_constitucion: Optional[str] = ""
    activa: int
    voceros: List[VoceroInstanciaResponse] = []


class AsignarVoceroRequest(BaseModel):
    vocero_id: int
    cargo_instancia: str
    fecha_designacion: Optional[str] = ""


class ActualizarInstanciaRequest(BaseModel):
    descripcion: Optional[str] = None
    fecha_constitucion: Optional[str] = None
    activa: Optional[int] = None


@router.get("", response_model=List[InstanciaResponse])
async def listar_instancias():
    """Retorna las 5 instancias de gobierno con sus voceros miembros asignados."""
    async with await get_db() as db:
        cursor = await db.execute("""
            SELECT id, nombre, tipo, descripcion, base_legal, fecha_constitucion, activa
            FROM instancias_gobierno
            ORDER BY id ASC
        """)
        instancias_rows = await cursor.fetchall()
        
        resultado = []
        for inst in instancias_rows:
            inst_id = inst["id"]
            # Obtener voceros asignados a la instancia
            cur_voc = await db.execute("""
                SELECT iv.id, iv.vocero_id, v.nombre, v.cedula, v.telefono, v.cargo as cargo_origen,
                       c.nombre as consejo_nombre, iv.cargo_instancia, iv.fecha_designacion, iv.activo
                FROM instancias_voceros iv
                JOIN voceros v ON iv.vocero_id = v.id
                LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
                WHERE iv.instancia_id = ? AND iv.activo = 1
                ORDER BY iv.cargo_instancia ASC, v.nombre ASC
            """, (inst_id,))
            voc_rows = await cur_voc.fetchall()

            voceros_list = [
                VoceroInstanciaResponse(
                    id=vr["id"],
                    vocero_id=vr["vocero_id"],
                    nombre=vr["nombre"] or "",
                    cedula=vr["cedula"] or "",
                    telefono=vr["telefono"] or "",
                    cargo_origen=vr["cargo_origen"] or "",
                    consejo_nombre=vr["consejo_nombre"] or "",
                    cargo_instancia=vr["cargo_instancia"] or "",
                    fecha_designacion=vr["fecha_designacion"] or "",
                    activo=vr["activo"]
                ) for vr in voc_rows
            ]

            resultado.append(InstanciaResponse(
                id=inst["id"],
                nombre=inst["nombre"],
                tipo=inst["tipo"],
                descripcion=inst["descripcion"] or "",
                base_legal=inst["base_legal"] or "",
                fecha_constitucion=inst["fecha_constitucion"] or "",
                activa=inst["activa"],
                voceros=voceros_list
            ))
        return resultado


@router.get("/{instancia_id}", response_model=InstanciaResponse)
async def detalle_instancia(instancia_id: int):
    """Retorna una instancia específica con sus voceros."""
    async with await get_db() as db:
        cursor = await db.execute("""
            SELECT id, nombre, tipo, descripcion, base_legal, fecha_constitucion, activa
            FROM instancias_gobierno
            WHERE id = ?
        """, (instancia_id,))
        inst = await cursor.fetchone()
        if not inst:
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        cur_voc = await db.execute("""
            SELECT iv.id, iv.vocero_id, v.nombre, v.cedula, v.telefono, v.cargo as cargo_origen,
                   c.nombre as consejo_nombre, iv.cargo_instancia, iv.fecha_designacion, iv.activo
            FROM instancias_voceros iv
            JOIN voceros v ON iv.vocero_id = v.id
            LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
            WHERE iv.instancia_id = ? AND iv.activo = 1
            ORDER BY iv.cargo_instancia ASC, v.nombre ASC
        """, (instancia_id,))
        voc_rows = await cur_voc.fetchall()

        voceros_list = [
            VoceroInstanciaResponse(
                id=vr["id"],
                vocero_id=vr["vocero_id"],
                nombre=vr["nombre"] or "",
                cedula=vr["cedula"] or "",
                telefono=vr["telefono"] or "",
                cargo_origen=vr["cargo_origen"] or "",
                consejo_nombre=vr["consejo_nombre"] or "",
                cargo_instancia=vr["cargo_instancia"] or "",
                fecha_designacion=vr["fecha_designacion"] or "",
                activo=vr["activo"]
            ) for vr in voc_rows
        ]

        return InstanciaResponse(
            id=inst["id"],
            nombre=inst["nombre"],
            tipo=inst["tipo"],
            descripcion=inst["descripcion"] or "",
            base_legal=inst["base_legal"] or "",
            fecha_constitucion=inst["fecha_constitucion"] or "",
            activa=inst["activa"],
            voceros=voceros_list
        )


@router.post("/{instancia_id}/voceros")
async def asignar_vocero(instancia_id: int, req: AsignarVoceroRequest):
    """Asigna un vocero del padrón a una instancia de gobierno."""
    async with await get_db() as db:
        # Verificar que la instancia exista
        cur_inst = await db.execute("SELECT id FROM instancias_gobierno WHERE id = ?", (instancia_id,))
        if not await cur_inst.fetchone():
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        # Verificar que el vocero exista
        cur_voc = await db.execute("SELECT id FROM voceros WHERE id = ?", (req.vocero_id,))
        if not await cur_voc.fetchone():
            raise HTTPException(status_code=404, detail="Vocero no encontrado")

        fecha = req.fecha_designacion or ""

        # Insertar o reactivar en instancias_voceros
        await db.execute("""
            INSERT INTO instancias_voceros (instancia_id, vocero_id, cargo_instancia, fecha_designacion, activo)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(instancia_id, vocero_id) DO UPDATE SET
                cargo_instancia = excluded.cargo_instancia,
                fecha_designacion = excluded.fecha_designacion,
                activo = 1
        """, (instancia_id, req.vocero_id, req.cargo_instancia, fecha))

        # Registrar también en tabla vocerias para histórico/trazabilidad
        await db.execute("""
            INSERT INTO vocerias (vocero_id, tipo_asignacion, instancia_id, cargo, fecha_inicio, activa)
            VALUES (?, 'instancia', ?, ?, ?, 1)
        """, (req.vocero_id, instancia_id, req.cargo_instancia, fecha))

        await db.commit()
        return {"status": "success", "message": "Vocero asignado exitosamente a la instancia"}


@router.delete("/{instancia_id}/voceros/{vocero_id}")
async def desasignar_vocero(instancia_id: int, vocero_id: int):
    """Desactiva la asignación de un vocero en una instancia."""
    async with await get_db() as db:
        cur = await db.execute("""
            SELECT id FROM instancias_voceros
            WHERE instancia_id = ? AND vocero_id = ? AND activo = 1
        """, (instancia_id, vocero_id))
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Asignación de vocero en instancia no encontrada")

        await db.execute("""
            UPDATE instancias_voceros
            SET activo = 0
            WHERE instancia_id = ? AND vocero_id = ?
        """, (instancia_id, vocero_id))

        await db.execute("""
            UPDATE vocerias
            SET activa = 0, fecha_fin = date('now')
            WHERE instancia_id = ? AND vocero_id = ? AND tipo_asignacion = 'instancia'
        """, (instancia_id, vocero_id))

        await db.commit()
        return {"status": "success", "message": "Vocero desasignado de la instancia"}


@router.put("/{instancia_id}")
async def actualizar_instancia(instancia_id: int, req: ActualizarInstanciaRequest):
    """Actualiza datos descriptivos de la instancia."""
    if instancia_id <= 0:
        raise HTTPException(status_code=400, detail="ID de instancia inválido")

    async with await get_db() as db:
        cur_chk = await db.execute("SELECT id FROM instancias_gobierno WHERE id = ?", (instancia_id,))
        if not await cur_chk.fetchone():
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        if req.activa is not None and req.activa not in (0, 1):
            raise HTTPException(status_code=400, detail="El estado activa debe ser 0 o 1")

        campos = []
        valores = []
        if req.descripcion is not None:
            campos.append("descripcion = ?")
            valores.append(req.descripcion.strip())
        if req.fecha_constitucion is not None:
            campos.append("fecha_constitucion = ?")
            valores.append(req.fecha_constitucion.strip())
        if req.activa is not None:
            campos.append("activa = ?")
            valores.append(req.activa)

        if not campos:
            return {"status": "no_changes"}

        valores.append(instancia_id)
        sql = f"UPDATE instancias_gobierno SET {', '.join(campos)} WHERE id = ?"
        await db.execute(sql, tuple(valores))
        await db.commit()
        return {"status": "success", "message": "Instancia actualizada"}



MAPA_CARGOS_INSTANCIAS = {
    "Electoral": ["Comision Electoral"],
    "Contraloría": ["Contraloria Social"],
    "Banco": ["Administrativa Y Financiera"],
    "Parlamento": ["Comité De Legislación"],
    "Justicia": ["Justicia De Paz Comunal"],
}

@router.get("/{instancia_id}/candidatos")
async def listar_candidatos_instancia(instancia_id: int):
    """
    Retorna únicamente los voceros Principales (P) de los Consejos Comunales
    cuyo comité u origen corresponda a la instancia de autogobierno comunal.
    """
    async with await get_db() as db:
        cur_inst = await db.execute("SELECT id, nombre, tipo FROM instancias_gobierno WHERE id = ?", (instancia_id,))
        inst = await cur_inst.fetchone()
        if not inst:
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        tipo = inst["tipo"]
        cargos = MAPA_CARGOS_INSTANCIAS.get(tipo, [])

        if not cargos:
            # Fallback seguro
            cargos = [tipo]

        placeholders = ",".join(["?"] * len(cargos))
        sql = f"""
            SELECT v.id, v.nombre, v.cedula, v.telefono, v.cargo, v.tipo,
                   cc.nombre as consejo_nombre, cc.id as consejo_id
            FROM voceros v
            JOIN consejos_comunales cc ON v.consejo_id = cc.id
            WHERE v.activo = 1
              AND v.tipo = 'Principal'
              AND v.cargo IN ({placeholders})
            ORDER BY cc.nombre ASC, v.nombre ASC
        """
        cursor = await db.execute(sql, tuple(cargos))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
