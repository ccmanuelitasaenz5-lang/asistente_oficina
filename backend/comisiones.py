import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.database import get_db

logger = logging.getLogger("comisiones")
router = APIRouter(prefix="/api/comisiones", tags=["Comisiones de Gestión Comunal"])


class VoceroComisionResponse(BaseModel):
    id: int
    vocero_id: int
    nombre: str
    cedula: Optional[str] = ""
    telefono: Optional[str] = ""
    cargo_origen: Optional[str] = ""
    consejo_nombre: Optional[str] = ""
    cargo_comision: str
    fecha_inicio: Optional[str] = ""
    activa: int


class ComisionResponse(BaseModel):
    id: int
    nombre: str
    area_tematica: Optional[str] = ""
    descripcion: Optional[str] = ""
    responsable_id: Optional[int] = None
    responsable_nombre: Optional[str] = ""
    activa: int
    miembros: List[VoceroComisionResponse] = []


class NuevaComisionRequest(BaseModel):
    nombre: str
    area_tematica: Optional[str] = ""
    descripcion: Optional[str] = ""
    responsable_id: Optional[int] = None


class ActualizarComisionRequest(BaseModel):
    nombre: Optional[str] = None
    area_tematica: Optional[str] = None
    descripcion: Optional[str] = None
    responsable_id: Optional[int] = None
    activa: Optional[int] = None


class AsignarMiembroRequest(BaseModel):
    vocero_id: int
    cargo: str = "Miembro"
    fecha_inicio: Optional[str] = ""


@router.get("", response_model=List[ComisionResponse])
async def listar_comisiones():
    """Retorna todas las comisiones de gestión comunal con sus miembros y responsable."""
    async with await get_db() as db:
        cursor = await db.execute("""
            SELECT c.id, c.nombre, c.area_tematica, c.descripcion, c.responsable_id, c.activa,
                   v.nombre as responsable_nombre
            FROM comisiones_gestion c
            LEFT JOIN voceros v ON c.responsable_id = v.id
            WHERE c.activa = 1
            ORDER BY c.nombre ASC
        """)
        comisiones_rows = await cursor.fetchall()

        resultado = []
        for com in comisiones_rows:
            com_id = com["id"]
            # Obtener miembros asignados a través de vocerias
            cur_miembros = await db.execute("""
                SELECT voc.id, voc.vocero_id, v.nombre, v.cedula, v.telefono, v.cargo as cargo_origen,
                       cc.nombre as consejo_nombre, voc.cargo as cargo_comision, voc.fecha_inicio, voc.activa
                FROM vocerias voc
                JOIN voceros v ON voc.vocero_id = v.id
                LEFT JOIN consejos_comunales cc ON v.consejo_id = cc.id
                WHERE voc.comision_id = ? AND voc.tipo_asignacion = 'comision' AND voc.activa = 1
                ORDER BY v.nombre ASC
            """, (com_id,))
            miembros_rows = await cur_miembros.fetchall()

            miembros_list = [
                VoceroComisionResponse(
                    id=mr["id"],
                    vocero_id=mr["vocero_id"],
                    nombre=mr["nombre"] or "",
                    cedula=mr["cedula"] or "",
                    telefono=mr["telefono"] or "",
                    cargo_origen=mr["cargo_origen"] or "",
                    consejo_nombre=mr["consejo_nombre"] or "",
                    cargo_comision=mr["cargo_comision"] or "",
                    fecha_inicio=mr["fecha_inicio"] or "",
                    activa=mr["activa"]
                ) for mr in miembros_rows
            ]

            resultado.append(ComisionResponse(
                id=com["id"],
                nombre=com["nombre"],
                area_tematica=com["area_tematica"] or "",
                descripcion=com["descripcion"] or "",
                responsable_id=com["responsable_id"],
                responsable_nombre=com["responsable_nombre"] or "",
                activa=com["activa"],
                miembros=miembros_list
            ))
        return resultado


@router.post("", response_model=dict)
async def crear_comision(req: NuevaComisionRequest):
    """Crea una nueva comisión de gestión comunal."""
    nombre = req.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre de la comisión es obligatorio")

    async with await get_db() as db:
        cur_check = await db.execute("SELECT id FROM comisiones_gestion WHERE LOWER(nombre) = LOWER(?)", (nombre,))
        if await cur_check.fetchone():
            raise HTTPException(status_code=400, detail="Ya existe una comisión con este nombre")

        cursor = await db.execute("""
            INSERT INTO comisiones_gestion (nombre, area_tematica, descripcion, responsable_id, activa)
            VALUES (?, ?, ?, ?, 1)
        """, (nombre, req.area_tematica or nombre, req.descripcion or "", req.responsable_id))
        com_id = cursor.lastrowid
        await db.commit()
        return {"status": "success", "id": com_id, "message": "Comisión creada exitosamente"}


@router.put("/{comision_id}")
async def actualizar_comision(comision_id: int, req: ActualizarComisionRequest):
    """Actualiza los datos de una comisión."""
    if comision_id < 1:
        raise HTTPException(status_code=400, detail="ID de comisión inválido")
    async with await get_db() as db:
        cur_ex = await db.execute("SELECT id FROM comisiones_gestion WHERE id = ?", (comision_id,))
        if not await cur_ex.fetchone():
            raise HTTPException(status_code=404, detail="Comisión no encontrada")

        campos = []
        valores = []
        if req.nombre is not None:
            nombre = req.nombre.strip()
            if not nombre:
                raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
            campos.append("nombre = ?")
            valores.append(nombre)
        if req.area_tematica is not None:
            campos.append("area_tematica = ?")
            valores.append(req.area_tematica.strip())
        if req.descripcion is not None:
            campos.append("descripcion = ?")
            valores.append(req.descripcion.strip())
        if req.responsable_id is not None:
            campos.append("responsable_id = ?")
            valores.append(req.responsable_id)
        if req.activa is not None:
            if req.activa not in (0, 1):
                raise HTTPException(status_code=400, detail="El campo 'activa' debe ser 0 o 1")
            campos.append("activa = ?")
            valores.append(req.activa)

        if not campos:
            return {"status": "no_changes"}

        valores.append(comision_id)
        sql = f"UPDATE comisiones_gestion SET {', '.join(campos)} WHERE id = ?"
        await db.execute(sql, tuple(valores))
        await db.commit()
        return {"status": "success", "message": "Comisión actualizada exitosamente"}


@router.post("/{comision_id}/voceros")
async def asignar_vocero_comision(comision_id: int, req: AsignarMiembroRequest):
    """Asigna un vocero del padrón a una comisión de gestión."""
    async with await get_db() as db:
        cur_com = await db.execute("SELECT id FROM comisiones_gestion WHERE id = ?", (comision_id,))
        if not await cur_com.fetchone():
            raise HTTPException(status_code=404, detail="Comisión no encontrada")

        cur_voc = await db.execute("SELECT id FROM voceros WHERE id = ?", (req.vocero_id,))
        if not await cur_voc.fetchone():
            raise HTTPException(status_code=404, detail="Vocero no encontrado")

        fecha = req.fecha_inicio or ""

        # Registrar en vocerias
        await db.execute("""
            INSERT INTO vocerias (vocero_id, tipo_asignacion, comision_id, cargo, fecha_inicio, activa)
            VALUES (?, 'comision', ?, ?, ?, 1)
        """, (req.vocero_id, comision_id, req.cargo, fecha))

        await db.commit()
        return {"status": "success", "message": "Vocero asignado exitosamente a la comisión"}


@router.delete("/{comision_id}/voceros/{vocero_id}")
async def desasignar_vocero_comision(comision_id: int, vocero_id: int):
    """Desactiva la asignación de un vocero en una comisión."""
    async with await get_db() as db:
        cur_check = await db.execute("""
            SELECT id FROM vocerias
            WHERE comision_id = ? AND vocero_id = ? AND tipo_asignacion = 'comision' AND activa = 1
        """, (comision_id, vocero_id))
        if not await cur_check.fetchone():
            raise HTTPException(status_code=404, detail="Asignación no encontrada o ya inactiva")

        await db.execute("""
            UPDATE vocerias
            SET activa = 0, fecha_fin = date('now')
            WHERE comision_id = ? AND vocero_id = ? AND tipo_asignacion = 'comision'
        """, (comision_id, vocero_id))

        await db.commit()
        return {"status": "success", "message": "Vocero desasignado de la comisión"}



MAPA_CARGOS_COMISIONES = {
    "Planificación": ["Planificación Comunal", "Tierra Urbana", "Vivienda Y Hábitat"],
    "Economía": ["Economía Comunal", "Alimentación Y Defensa Al Consumidor", "Tecnología E Innovación"],
    "Suprema Felicidad Social": [
        "Salud", "Educación Y Formación Ciudadana", "Comunitario De Personas Con Discapacidad",
        "Personas Adultas Mayores", "Mujer E Igualdad De Genero", "Protección Integral De Las Familias",
        "Proteccion De Niños Niñas Y Adolecentes", "Cultura", "Recreación Y Deportes",
        "Medios Alternativos Comunitarios", "Comunicacion"
    ],
    "Servicios Públicos": ["Mesa Técnica De Agua", "Mesa Técnica De Energía Y Gas", "Transporte", "Ecosocialismo"],
    "Seguridad": ["Seguridad Y Defensa Integral", "Gestión De Riesgo", "Derechos Humanos"],
    "Juventud": ["Juventud"]
}

@router.get("/{comision_id}/candidatos")
async def listar_candidatos_comision(comision_id: int):
    """
    Retorna únicamente los voceros Principales (P) de los Consejos Comunales
    cuyo comité corresponda al área de trabajo de la comisión comunal.
    """
    async with await get_db() as db:
        cur_com = await db.execute("SELECT id, nombre FROM comisiones_gestion WHERE id = ?", (comision_id,))
        com = await cur_com.fetchone()
        if not com:
            raise HTTPException(status_code=404, detail="Comisión no encontrada")

        nombre = com["nombre"]
        cargos = []
        for clave, lista in MAPA_CARGOS_COMISIONES.items():
            if clave.lower() in nombre.lower():
                cargos = lista
                break

        if not cargos:
            # Fallback: devolver todos los voceros principales
            sql = """
                SELECT v.id, v.nombre, v.cedula, v.telefono, v.cargo, v.tipo,
                       cc.nombre as consejo_nombre, cc.id as consejo_id
                FROM voceros v
                JOIN consejos_comunales cc ON v.consejo_id = cc.id
                WHERE v.activo = 1 AND v.tipo = 'Principal'
                ORDER BY cc.nombre ASC, v.nombre ASC
            """
            cursor = await db.execute(sql)
        else:
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
