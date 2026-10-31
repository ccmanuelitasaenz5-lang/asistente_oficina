import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.database import get_db

logger = logging.getLogger("censo")
router = APIRouter(prefix="/api/censo", tags=["Censo Comunal"])


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS PYDANTIC
# ─────────────────────────────────────────────────────────────────────────────

class DiscapacidadRequest(BaseModel):
    tipo_discapacidad: str
    grado: Optional[str] = "Moderada"
    certificado_conapdis: Optional[int] = 0
    observaciones: Optional[str] = ""


class MiembroDemograficoRequest(BaseModel):
    nombre_completo: str
    cedula: Optional[str] = ""
    fecha_nacimiento: Optional[str] = ""
    sexo: Optional[str] = "F"
    parentesco: Optional[str] = "Hijo(a)"
    nivel_educativo: Optional[str] = ""
    ocupacion: Optional[str] = ""
    ingreso_mensual: Optional[float] = 0.0
    discapacidad: Optional[DiscapacidadRequest] = None


class ViviendaRequest(BaseModel):
    tipo_vivienda: Optional[str] = "Casa"
    tenencia: Optional[str] = "Propia"
    material_paredes: Optional[str] = "Bloque friso"
    material_techo: Optional[str] = "Platabanda"
    material_piso: Optional[str] = "Cemento/Cerámica"
    num_habitaciones: Optional[int] = 2
    num_banos: Optional[int] = 1
    estado_general: Optional[str] = "Bueno"


class ServicioPublicoItem(BaseModel):
    servicio: str
    tiene: int = 1
    calidad: Optional[str] = "Regular"
    frecuencia: Optional[str] = "Continuo"
    observaciones: Optional[str] = ""


class RegistrarFamiliaRequest(BaseModel):
    consejo_id: int
    familia_codigo: Optional[str] = ""
    jefe_familia: str
    cedula_jefe: Optional[str] = ""
    direccion: Optional[str] = ""
    telefono: Optional[str] = ""
    miembros: Optional[List[MiembroDemograficoRequest]] = []
    vivienda: Optional[ViviendaRequest] = None
    servicios: Optional[List[ServicioPublicoItem]] = []


class ElectorRequest(BaseModel):
    consejo_id: int
    cedula: str
    nombre: str
    fecha_nacimiento: Optional[str] = ""
    direccion: Optional[str] = ""
    centro_votacion: Optional[str] = ""
    mesa: Optional[int] = 1
    habilitado: Optional[int] = 1


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS FAMILIAS Y CENSO MAESTRO
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/familias")
async def listar_familias(
    consejo_id: Optional[int] = Query(None),
    busqueda: Optional[str] = Query(None),
    limit: int = 50,
    offset: int = 0
):
    """Lista las familias censadas con opción de filtrado."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="El parámetro 'limit' debe estar entre 1 y 500")
    if offset < 0:
        raise HTTPException(status_code=400, detail="El parámetro 'offset' no puede ser negativo")
    async with await get_db() as db:
        filtros = ["c.activo = 1"]
        params = []
        if consejo_id:
            filtros.append("c.consejo_id = ?")
            params.append(consejo_id)
        if busqueda:
            filtros.append("(c.jefe_familia LIKE ? OR c.cedula_jefe LIKE ? OR c.familia_codigo LIKE ?)")
            q = f"%{busqueda.strip()}%"
            params.extend([q, q, q])

        where_clause = " AND ".join(filtros)
        sql = f"""
            SELECT c.id, c.consejo_id, cc.nombre as consejo_nombre, c.familia_codigo,
                   c.jefe_familia, c.cedula_jefe, c.direccion, c.telefono, c.fecha_registro,
                   (SELECT COUNT(*) FROM censo_demografico cd WHERE cd.censo_id = c.id) as total_integrantes
            FROM censo c
            LEFT JOIN consejos_comunales cc ON c.consejo_id = cc.id
            WHERE {where_clause}
            ORDER BY c.fecha_registro DESC, c.id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        cursor = await db.execute(sql, tuple(params))
        rows = await cursor.fetchall()

        # Conteo total para paginación
        sql_count = f"SELECT COUNT(*) FROM censo c WHERE {where_clause}"
        cur_count = await db.execute(sql_count, tuple(params[:-2]))
        total_records = (await cur_count.fetchone())[0]

        familias = [dict(r) for r in rows]
        return {
            "total": total_records,
            "limit": limit,
            "offset": offset,
            "familias": familias
        }


@router.get("/familias/{censo_id}")
async def detalle_familia(censo_id: int):
    """Retorna el expediente familiar completo: datos maestro, miembros, vivienda y servicios."""
    async with await get_db() as db:
        # 1. Maestro
        cursor = await db.execute("""
            SELECT c.*, cc.nombre as consejo_nombre
            FROM censo c
            LEFT JOIN consejos_comunales cc ON c.consejo_id = cc.id
            WHERE c.id = ? AND c.activo = 1
        """, (censo_id,))
        familia = await cursor.fetchone()
        if not familia:
            raise HTTPException(status_code=404, detail="Familia no encontrada en el censo")

        familia_dict = dict(familia)

        # 2. Miembros y sus discapacidades
        cur_m = await db.execute("""
            SELECT cd.*, 
                   dis.tipo_discapacidad, dis.grado as grado_discapacidad, dis.certificado_conapdis
            FROM censo_demografico cd
            LEFT JOIN censo_discapacidad dis ON dis.demografico_id = cd.id
            WHERE cd.censo_id = ?
            ORDER BY cd.id ASC
        """, (censo_id,))
        familia_dict["miembros"] = [dict(r) for r in await cur_m.fetchall()]

        # 3. Vivienda
        cur_v = await db.execute("SELECT * FROM censo_viviendas WHERE censo_id = ?", (censo_id,))
        viv = await cur_v.fetchone()
        if viv:
            viv_dict = dict(viv)
            # Servicios de la vivienda
            cur_s = await db.execute("SELECT * FROM censo_servicios_publicos WHERE vivienda_id = ?", (viv["id"],))
            viv_dict["servicios"] = [dict(r) for r in await cur_s.fetchall()]
            familia_dict["vivienda"] = viv_dict
        else:
            familia_dict["vivienda"] = None

        return familia_dict


@router.post("/familias")
async def registrar_familia(req: RegistrarFamiliaRequest):
    """Registra una nueva familia con su núcleo demográfico, vivienda y servicios."""
    jefe = req.jefe_familia.strip() if req.jefe_familia else ""
    if not jefe:
        raise HTTPException(status_code=400, detail="El nombre del jefe de familia es obligatorio")
    if req.consejo_id < 1:
        raise HTTPException(status_code=400, detail="El consejo_id es inválido")

    # Validaciones de vivienda
    if req.vivienda:
        if req.vivienda.num_habitaciones is not None and req.vivienda.num_habitaciones < 0:
            raise HTTPException(status_code=400, detail="El número de habitaciones no puede ser negativo")
        if req.vivienda.num_banos is not None and req.vivienda.num_banos < 0:
            raise HTTPException(status_code=400, detail="El número de baños no puede ser negativo")

    async with await get_db() as db:
        # Verificar que el consejo existe
        cur_cc = await db.execute("SELECT id FROM consejos_comunales WHERE id = ?", (req.consejo_id,))
        if not await cur_cc.fetchone():
            raise HTTPException(status_code=404, detail="Consejo Comunal no encontrado")

        # Generar código correlativo si no viene provisto
        codigo = req.familia_codigo.strip() if req.familia_codigo else ""
        if not codigo:
            cur_seq = await db.execute("SELECT COUNT(*) FROM censo WHERE consejo_id = ?", (req.consejo_id,))
            seq = (await cur_seq.fetchone())[0] + 1
            codigo = f"FAM-CC{req.consejo_id:02d}-{seq:04d}"
        else:
            # Verificar UNIQUE de familia_codigo
            cur_uniq = await db.execute("SELECT id FROM censo WHERE familia_codigo = ?", (codigo,))
            if await cur_uniq.fetchone():
                raise HTTPException(status_code=400, detail=f"Ya existe una familia con el código '{codigo}'")

        # Insertar maestro censo
        cursor = await db.execute("""
            INSERT INTO censo (consejo_id, familia_codigo, jefe_familia, cedula_jefe, direccion, telefono, activo)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (req.consejo_id, codigo, jefe, req.cedula_jefe or "", req.direccion or "", req.telefono or ""))
        censo_id = cursor.lastrowid

        # Insertar miembros demográficos
        for m in req.miembros:
            cur_m = await db.execute("""
                INSERT INTO censo_demografico (censo_id, nombre_completo, cedula, fecha_nacimiento,
                                              sexo, parentesco, nivel_educativo, ocupacion, ingreso_mensual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (censo_id, m.nombre_completo, m.cedula, m.fecha_nacimiento, m.sexo, m.parentesco,
                  m.nivel_educativo, m.ocupacion, m.ingreso_mensual))
            demografico_id = cur_m.lastrowid

            # Si tiene discapacidad asociada
            if m.discapacidad:
                await db.execute("""
                    INSERT INTO censo_discapacidad (demografico_id, tipo_discapacidad, grado, certificado_conapdis, observaciones)
                    VALUES (?, ?, ?, ?, ?)
                """, (demografico_id, m.discapacidad.tipo_discapacidad, m.discapacidad.grado,
                      m.discapacidad.certificado_conapdis, m.discapacidad.observaciones))

        # Insertar vivienda
        if req.vivienda:
            cur_v = await db.execute("""
                INSERT INTO censo_viviendas (censo_id, tipo_vivienda, tenencia, material_paredes,
                                            material_techo, material_piso, num_habitaciones, num_banos, estado_general)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (censo_id, req.vivienda.tipo_vivienda, req.vivienda.tenencia, req.vivienda.material_paredes,
                  req.vivienda.material_techo, req.vivienda.material_piso, req.vivienda.num_habitaciones,
                  req.vivienda.num_banos, req.vivienda.estado_general))
            vivienda_id = cur_v.lastrowid

            # Insertar servicios públicos de la vivienda
            for s in req.servicios:
                await db.execute("""
                    INSERT INTO censo_servicios_publicos (vivienda_id, servicio, tiene, calidad, frecuencia, observaciones)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (vivienda_id, s.servicio, s.tiene, s.calidad, s.frecuencia, s.observaciones))

        # Actualizar la población total en el consejo comunal
        await db.execute("""
            UPDATE consejos_comunales
            SET poblacion_total = (
                SELECT COUNT(*) FROM censo_demografico cd
                JOIN censo c ON cd.censo_id = c.id
                WHERE c.consejo_id = ? AND c.activo = 1
            )
            WHERE id = ?
        """, (req.consejo_id, req.consejo_id))

        await db.commit()
        return {
            "status": "success",
            "censo_id": censo_id,
            "familia_codigo": codigo,
            "message": "Familia y censo registrados exitosamente"
        }


# ─────────────────────────────────────────────────────────────────────────────
# DISCAPACIDADES Y ESTADÍSTICAS CENSALES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/estadisticas")
async def estadisticas_censo():
    """Retorna métricas consolidadas del censo comunal."""
    async with await get_db() as db:
        # Total familias
        cur1 = await db.execute("SELECT COUNT(*) FROM censo WHERE activo = 1")
        total_familias = (await cur1.fetchone())[0]

        # Total habitantes
        cur2 = await db.execute("""
            SELECT COUNT(*) FROM censo_demografico cd
            JOIN censo c ON cd.censo_id = c.id
            WHERE c.activo = 1
        """)
        total_habitantes = (await cur2.fetchone())[0]

        # Habitantes por sexo
        cur_sex = await db.execute("""
            SELECT cd.sexo, COUNT(*) FROM censo_demografico cd
            JOIN censo c ON cd.censo_id = c.id
            WHERE c.activo = 1
            GROUP BY cd.sexo
        """)
        por_sexo = {r[0] or "Sin especificar": r[1] for r in await cur_sex.fetchall()}

        # Total personas con discapacidad
        cur_disc = await db.execute("SELECT COUNT(*) FROM censo_discapacidad")
        total_discapacitados = (await cur_disc.fetchone())[0]

        # Desglose de discapacidades
        cur_disc_types = await db.execute("""
            SELECT tipo_discapacidad, COUNT(*) FROM censo_discapacidad
            GROUP BY tipo_discapacidad
            ORDER BY COUNT(*) DESC
        """)
        discapacidades_tipo = [dict(tipo=r[0], cantidad=r[1]) for r in await cur_disc_types.fetchall()]

        # Familias por Consejo Comunal
        cur_cc = await db.execute("""
            SELECT cc.nombre, COUNT(c.id) as familias,
                   COALESCE(SUM((SELECT COUNT(*) FROM censo_demografico cd WHERE cd.censo_id = c.id)), 0) as habitantes
            FROM consejos_comunales cc
            LEFT JOIN censo c ON c.consejo_id = cc.id AND c.activo = 1
            GROUP BY cc.id, cc.nombre
            ORDER BY familias DESC
        """)
        por_consejo = [dict(r) for r in await cur_cc.fetchall()]

        return {
            "total_familias": total_familias,
            "total_habitantes": total_habitantes,
            "por_sexo": por_sexo,
            "total_discapacitados": total_discapacitados,
            "discapacidades_tipo": discapacidades_tipo,
            "por_consejo": por_consejo
        }


# ─────────────────────────────────────────────────────────────────────────────
# PADRÓN ELECTORAL COMUNAL
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/electoral")
async def listar_censo_electoral(
    consejo_id: Optional[int] = Query(None),
    busqueda: Optional[str] = Query(None),
    limit: int = 50,
    offset: int = 0
):
    """Lista los votantes registrados en el censo electoral comunal."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="El parámetro 'limit' debe estar entre 1 y 500")
    if offset < 0:
        raise HTTPException(status_code=400, detail="El parámetro 'offset' no puede ser negativo")
    async with await get_db() as db:
        filtros = ["ce.habilitado = 1"]
        params = []
        if consejo_id:
            filtros.append("ce.consejo_id = ?")
            params.append(consejo_id)
        if busqueda:
            filtros.append("(ce.nombre LIKE ? OR ce.cedula LIKE ?)")
            q = f"%{busqueda.strip()}%"
            params.extend([q, q])

        where_clause = " AND ".join(filtros)
        sql = f"""
            SELECT ce.*, cc.nombre as consejo_nombre
            FROM censo_electoral ce
            LEFT JOIN consejos_comunales cc ON ce.consejo_id = cc.id
            WHERE {where_clause}
            ORDER BY ce.nombre ASC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        cursor = await db.execute(sql, tuple(params))
        electores = [dict(r) for r in await cursor.fetchall()]

        cur_c = await db.execute(f"SELECT COUNT(*) FROM censo_electoral ce WHERE {where_clause}", tuple(params[:-2]))
        total = (await cur_c.fetchone())[0]

        return {"total": total, "electores": electores}


@router.post("/electoral")
async def registrar_elector(req: ElectorRequest):
    """Registra o actualiza a un elector en el censo electoral comunal."""
    async with await get_db() as db:
        await db.execute("""
            INSERT INTO censo_electoral (consejo_id, cedula, nombre, fecha_nacimiento, direccion, centro_votacion, mesa, habilitado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (req.consejo_id, req.cedula.strip(), req.nombre.strip(), req.fecha_nacimiento,
              req.direccion, req.centro_votacion, req.mesa, req.habilitado))
        await db.commit()
        return {"status": "success", "message": "Elector registrado exitosamente"}

