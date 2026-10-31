import logging
import json
import re
import asyncio
import unicodedata
import hashlib
import time
from functools import wraps
from typing import Optional, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("universal_agent")


# ─────────────────────────────────────────────────────────────────────────────
# Cache LRU para consultas (Fase 2)
# ─────────────────────────────────────────────────────────────────────────────
class QueryCache:
    """Cache LRU con expiración de 5 minutos."""

    def __init__(self, max_size: int = 100, ttl: int = 300):
        self.cache: dict = {}
        self.max_size = max_size
        self.ttl = ttl
        self.hits = 0
        self.misses = 0

    def _make_key(self, query: str, params: tuple) -> str:
        data = f"{query}:{params}"
        return hashlib.md5(data.encode()).hexdigest()

    def get(self, query: str, params: tuple = ()):
        key = self._make_key(query, params)
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                return value
            else:
                del self.cache[key]
        self.misses += 1
        return None

    def set(self, query: str, params: tuple, value):
        key = self._make_key(query, params)
        self.cache[key] = (value, time.time())
        if len(self.cache) > self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]

    def invalidate(self, query: str = None, params: tuple = ()):
        """Invalida una entrada específica o todo el cache."""
        if query is None:
            self.cache.clear()
        else:
            key = self._make_key(query, params)
            if key in self.cache:
                del self.cache[key]

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0,
            "size": len(self.cache),
        }


# Instancia global del cache
VOCEROS_CACHE = QueryCache(max_size=100, ttl=300)


def cache_query(cache_instance):
    """Decorador para cachear resultados de consultas."""
    def decorator(func):
        @wraps(func)
        async def wrapper(query: str, *args, **kwargs):
            # No cachear consultas muy específicas (>5 palabras)
            if len(query.split()) > 5:
                return await func(query, *args, **kwargs)

            cached = cache_instance.get(query)
            if cached is not None:
                logger.info(f"Cache HIT para: '{query[:50]}'")
                return cached

            result = await func(query, *args, **kwargs)
            cache_instance.set(query, (), result)
            logger.info(f"Cache MISS para: '{query[:50]}' - guardado")
            return result
        return wrapper
    return decorator
def invalidar_cache():
    """Invalida todo el cache de consultas. Llamar desde padron.py al modificar datos."""
    VOCEROS_CACHE.invalidate()
    logger.info("Cache de consultas invalidado")
# ─────────────────────────────────────────────────────────────────────────────
# PASO 1: Clasificador de intención
# ─────────────────────────────────────────────────────────────────────────────

INTENT_KEYWORDS = {
    "voceros": [
        "vocero", "vocalía", "vocería", "principal", "suplente", "electo",
        "elegido", "cargo", "cédula", "teléfono", "contacto", "miembro",
        "consejo comunal", "quién es", "quién fue", "quiénes son",
    ],
    "actas": [
        "acta", "asamblea", "elección", "votación", "votos", "elegido",
        "acta de elección", "reunión", "sesión", "resolución", "aprobó",
    ],
    "cartas": [
        "carta", "oficio", "solicitud", "correspondencia", "comunicado",
        "CPPO", "número de oficio", "dirigida", "destinatario", "envió",
        "escribió", "redactó",
    ],
    "actividades": [
        "actividad", "jornada", "evento", "censo", "obra", "construcción",
        "taller", "formación", "visita", "rendición de cuentas", "realiz",
        "hicieron", "hizo", "participantes",
    ],
    "tareas": [
        "tarea", "pendiente", "plazo", "vencimiento", "recordatorio",
        "programado", "calendario", "agenda", "compromiso", "deadline",
    ],
    "documentos": [
        "documento", "archivo", "informe", "reporte", "pdf", "word",
        "excel", "planilla", "presupuesto", "proyecto", "plan",
        "qué dice", "qué contiene", "busca en", "encuentra en",
    ],
        "instancias": [
        "instancia", "gobierno comunal", "parlamento", "parlamento comunal",
        "banco comunal", "contraloría", "comisión electoral", "justicia de paz",
        "quién conforma", "quién integra", "instancias de gobierno",
    ],
    "comisiones": [
        "comisión", "comisiones", "gestión comunal", "salud", "educación",
        "tierras", "hábitat", "economía", "seguridad", "comisionado",
    ],
    "censo": [
        "censo", "familia", "población", "demográfico", "vivienda",
        "discapacidad", "servicio público", "habitante", "jefe de familia",
        "cuántas familias", "cuántos habitantes", "elector", "votante",
        "chamo", "chamos", "niño", "niños", "personas", "discapacitados",
        "cuantos viven", "cuanta gente",
    ],
    "rendiciones": [
        "rendición", "cuentas", "presupuesto", "ejecutado", "asignado",
        "rendición de cuentas", "memoria y cuenta", "artículo 52",
        "plata", "dinero", "gastado", "fondos", "cuánto se gastó",
    ],
    "gaceta": [
        "gaceta", "decisión", "ley comunal", "acuerdo", "resolución",
        "publicación", "promulgada", "artículo 41",
    ],
    "proyectos": [
        "proyecto", "obra", "inversión", "avance", "agenda concreta",
        "ACA", "beneficiarios", "ejecución física",
        "alumbrado", "vialidad", "construcción", "reparación", "mejora",
    ],
    "legal": [
        "ley", "artículo", "LOC", "ley orgánica", "normativa",
        "reglamento", "regulación", "qué dice el artículo",
        "articulo", "art", "norma", "base legal",
    ],
    "consultas_populares": [
        "consulta", "consultas", "consulta popular", "referéndum", "referendum",
        "votación", "participantes", "votos", "opciones", "preguntas",
    ],
}


def _clasificar_intencion(query: str) -> dict:
    q = query.lower()
    scores = {fuente: 0.0 for fuente in INTENT_KEYWORDS}

    for fuente, keywords in INTENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in q)
        scores[fuente] = min(hits / max(len(keywords) * 0.3, 1), 1.0)

    if max(scores.values()) < 0.05:
        scores["documentos"] = 0.5
        scores["voceros"] = 0.3

    if any(p in q for p in ["quién", "quien", "quiénes", "quienes"]):
        scores["voceros"] = max(scores["voceros"], 0.6)

    if any(p in q for p in ["cuándo", "cuando", "fecha", "día", "mes"]):
        scores["actas"] = max(scores["actas"], 0.4)
        scores["tareas"] = max(scores["tareas"], 0.4)

    fuentes_activas = {f: s for f, s in scores.items() if s > 0.1}
    if not fuentes_activas:
        fuentes_activas = {f: 0.2 for f in INTENT_KEYWORDS}

    logger.info(f"Fuentes activas para '{query[:50]}': {fuentes_activas}")
    return fuentes_activas


# ─────────────────────────────────────────────────────────────────────────────
# PASO 2: Búsquedas por fuente
# ─────────────────────────────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """Quita tildes y convierte a minúsculas para comparaciones robustas."""
    if not texto:
        return ""
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().strip()


def _get_unidad_desde_query(q: str) -> Optional[str]:
    """Detecta si la consulta pide voceros de una unidad específica."""
    q = q.lower()
    if any(p in q for p in ["legislat", "legislació", "comité de legislaci"]):
        return "Legislativa"
    if any(p in q for p in ["contralor", "contraloria", "contraloría", "control social"]):
        return "Contraloría Social"
    if any(p in q for p in ["financ", "banco", "administra", "tesorer"]):
        return "Administración y Finanzas"
    if any(p in q for p in ["ejecutiv"]):
        return "Ejecutiva"
    return None

UNIDAD_CARGOS = {
    "Legislativa":             ["comité de legislaci", "comision electoral", "comisión electoral"],
    "Contraloría Social":      ["contralor"],
    "Administración y Finanzas": ["financier", "administrat"],
    "Ejecutiva":               [],  # todos los demás
}


def _extract_keywords_voceros(query: str) -> List[str]:
    """Extraer palabras clave significativas evitando stopwords"""
    stopwords = {"los", "las", "del", "de", "la", "el", "en", "un", "una",
                 "y", "e", "o", "al", "con", "por", "que", "cuáles", "cuales",
                 "son", "voceros", "vocero", "consejo", "comunal", "cuántos",
                 "cuantos", "cual", "cuál", "dónde", "donde", "cómo", "como"}

    palabras = [
        w for w in re.findall(r'\w+', query.lower())
        if len(w) > 3 and w not in stopwords
    ]
    return palabras[:3]


def _build_voceros_query_corregida(
    query: str,
    unidad_pedida: Optional[str],
    palabras_clave: List[str]
) -> tuple:
    """
    Construir query SQL con parámetros seguros (NO concatenación de valores).
    Versión CORREGIDA con los 4 casos completos y LIMIT corregidos.
    """

    # Caso 1: Consulta específica por unidad (sin consejo específico)
    if unidad_pedida and unidad_pedida != "Ejecutiva":
        cargos_unidad = UNIDAD_CARGOS.get(unidad_pedida, [])
        if cargos_unidad:
            if unidad_pedida == "Legislativa":
                sql = """
                SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
                       c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
                FROM voceros v
                LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
                LEFT JOIN actas a ON v.acta_id = a.id
                WHERE v.activo = 1
                  AND (
                    LOWER(v.cargo) LIKE ?
                    OR LOWER(v.cargo) LIKE ?
                    OR LOWER(v.cargo) LIKE ?
                  )
                ORDER BY c.nombre, v.nombre
                LIMIT 50
                """
                params = [f"%{cargo}%" for cargo in cargos_unidad]

            elif unidad_pedida == "Contraloría Social":
                sql = """
                SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
                       c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
                FROM voceros v
                LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
                LEFT JOIN actas a ON v.acta_id = a.id
                WHERE v.activo = 1
                  AND LOWER(v.cargo) LIKE ?
                ORDER BY c.nombre, v.nombre
                LIMIT 50
                """
                params = [f"%{cargos_unidad[0]}%"]

            elif unidad_pedida == "Administración y Finanzas":
                sql = """
                SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
                       c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
                FROM voceros v
                LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
                LEFT JOIN actas a ON v.acta_id = a.id
                WHERE v.activo = 1
                  AND (
                    LOWER(v.cargo) LIKE ?
                    OR LOWER(v.cargo) LIKE ?
                  )
                ORDER BY c.nombre, v.nombre
                LIMIT 50
                """
                params = [f"%{cargo}%" for cargo in cargos_unidad]

            else:
                return _build_voceros_query_corregida(query, None, palabras_clave)

            return sql, params

    # Caso especial: Ejecutiva (todos los que NO son de otras unidades)
    elif unidad_pedida == "Ejecutiva":
        terminos_excluidos = []
        for unidad, terminos in UNIDAD_CARGOS.items():
            if unidad != "Ejecutiva":
                terminos_excluidos.extend(terminos)

        if terminos_excluidos:
            placeholders = " AND ".join(["LOWER(v.cargo) NOT LIKE ?" for _ in terminos_excluidos])

            sql = f"""
            SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
                   c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
            FROM voceros v
            LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
            LEFT JOIN actas a ON v.acta_id = a.id
            WHERE v.activo = 1
              AND ({placeholders})
            ORDER BY c.nombre, v.nombre
            LIMIT 50
            """
            params = tuple(f"%{termino}%" for termino in terminos_excluidos)
        else:
            sql = """
            SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
                   c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
            FROM voceros v
            LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
            LEFT JOIN actas a ON v.acta_id = a.id
            WHERE v.activo = 1
            ORDER BY c.nombre, v.nombre
            LIMIT 100
            """
            params = ()

        return sql, params

    # Caso 2: Búsqueda por palabras clave (con LIKE parametrizado)
    elif palabras_clave:
        kw = f"%{' '.join(palabras_clave)}%"

        sql = """
        SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
               c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
        FROM voceros v
        LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
        LEFT JOIN actas a ON v.acta_id = a.id
        WHERE v.activo = 1
          AND (
            LOWER(v.nombre)   LIKE ?
            OR LOWER(v.cedula) LIKE ?
            OR LOWER(v.cargo)  LIKE ?
            OR LOWER(c.nombre) LIKE ?
          )
        ORDER BY c.nombre, v.nombre
        LIMIT 50
        """
        return sql, (kw, kw, kw, kw)

    # Caso 3: Consulta general (fallback)
    sql = """
    SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
           c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
    FROM voceros v
    LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
    LEFT JOIN actas a ON v.acta_id = a.id
    WHERE v.activo = 1
    ORDER BY c.nombre, v.nombre
    LIMIT 100
    """
    return sql, ()


@cache_query(VOCEROS_CACHE)
async def _buscar_voceros(query: str) -> list:
    """
    Versión optimizada FASE 1:
    - SQL con parámetros seguros (sin f-strings con valores de usuario)
    - Usa las funciones auxiliares _extract_keywords_voceros y 
      _build_voceros_query_corregida
    - NOTA: Cache LRU y timeout se agregarán en FASE 2
    """
    resultados = []
    q_lower = query.lower()
    unidad_pedida = _get_unidad_desde_query(q_lower)

    try:
        from backend.database import get_db
        async with await get_db() as db:
            # Buscar por consejo conocido primero
            CONSEJOS_CONOCIDOS = [
                "la inmaculada", "barrio bolivar", "divino niño", "la esperanza",
                "la victoria", "manuelita saenz", "pablo rosales", "sur america",
                "suramerica"
            ]
            q_normalizada = _normalizar(q_lower)
            consejo_en_query = None
            for c in CONSEJOS_CONOCIDOS:
                if _normalizar(c) in q_normalizada:
                    consejo_en_query = c
                    break

            rows = []

            if consejo_en_query and unidad_pedida:
                # Buscar voceros del consejo Y que pertenezcan a esa unidad
                if unidad_pedida == "Ejecutiva":
                    cursor = await db.execute(
                        """
                        SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
                               c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
                        FROM voceros v
                        LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
                        LEFT JOIN actas a ON v.acta_id = a.id
                        WHERE v.activo = 1
                          AND LOWER(c.nombre) LIKE ?
                          AND LOWER(v.cargo) NOT LIKE ?
                          AND LOWER(v.cargo) NOT LIKE ?
                          AND LOWER(v.cargo) NOT LIKE ?
                          AND LOWER(v.cargo) NOT LIKE ?
                          AND LOWER(v.cargo) NOT LIKE ?
                        ORDER BY v.nombre
                        LIMIT 50
                        """,
                        (f"%{consejo_en_query}%", "%contralor%", "%financier%",
                         "%administrat%", "%legislaci%", "%electoral%"),
                    )
                    rows = await cursor.fetchall()
                else:
                    # Usar la función auxiliar para construir el SQL seguro
                    sql, params = _build_voceros_query_corregida(q_lower, unidad_pedida, [])
                    # Filtrar además por consejo
                    sql_con_consejo = sql.replace(
                        "WHERE v.activo = 1",
                        "WHERE v.activo = 1 AND LOWER(c.nombre) LIKE ?"
                    )
                    params_con_consejo = tuple([f"%{consejo_en_query}%"] + list(params))
                    cursor = await db.execute(sql_con_consejo, params_con_consejo)
                    rows = await cursor.fetchall()

            elif consejo_en_query:
                cursor = await db.execute(
                    """
                    SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
                           c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
                    FROM voceros v
                    LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
                    LEFT JOIN actas a ON v.acta_id = a.id
                    WHERE v.activo = 1
                      AND LOWER(c.nombre) LIKE ?
                    ORDER BY v.nombre
                    LIMIT 60
                    """,
                    (f"%{consejo_en_query}%",),
                )
                rows = await cursor.fetchall()

            elif unidad_pedida:
                # Solo por unidad (sin consejo específico)
                palabras_clave = _extract_keywords_voceros(query)
                sql, params = _build_voceros_query_corregida(q_lower, unidad_pedida, palabras_clave)
                cursor = await db.execute(sql, params)
                rows = await cursor.fetchall()

            # Estrategia 2: Búsqueda por texto libre
            if not rows:
                palabras = _extract_keywords_voceros(query)
                if palabras:
                    kw = f"%{' '.join(palabras)}%"
                    cursor = await db.execute(
                        """
                        SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
                               c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
                        FROM voceros v
                        LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
                        LEFT JOIN actas a ON v.acta_id = a.id
                        WHERE v.activo = 1
                          AND (
                            LOWER(v.nombre)   LIKE ?
                            OR LOWER(v.cedula) LIKE ?
                            OR LOWER(v.cargo)  LIKE ?
                            OR LOWER(c.nombre) LIKE ?
                          )
                        LIMIT 50
                        """,
                        (kw, kw, kw, kw),
                    )
                    rows = await cursor.fetchall()

            # Estrategia 3: Fallback – todos los voceros
            if not rows:
                cursor = await db.execute(
                    """
                    SELECT v.nombre, v.cedula, v.cargo, v.tipo, v.telefono, v.votos,
                           c.nombre as consejo_nombre, a.fecha_acta, a.pdf_path
                    FROM voceros v
                    LEFT JOIN consejos_comunales c ON v.consejo_id = c.id
                    LEFT JOIN actas a ON v.acta_id = a.id
                    WHERE v.activo = 1
                    ORDER BY c.nombre, v.nombre
                    LIMIT 100
                    """
                )
                rows = await cursor.fetchall()

            for r in rows:
                resultados.append({
                    "fuente": "voceros",
                    "tipo_doc": "Padrón de Voceros",
                    "nombre": (r[0] or "").strip(),
                    "cedula": (r[1] or "").strip(),
                    "cargo": (r[2] or "").strip(),
                    "tipo": (r[3] or "Principal").strip(),
                    "telefono": (r[4] or "").strip(),
                    "votos": int(r[5] or 0),
                    "consejo": (r[6] or "").strip(),
                    "fecha_acta": (r[7] or "").strip(),
                    "pdf_acta": (r[8] or "").strip(),
                    "resumen": (
                        f"{r[0]} — {r[2]} ({r[3]}) en {r[6] or 'N/A'}"
                        + (f", C.I: {r[1]}" if r[1] else "")
                        + (f", Tel: {r[4]}" if r[4] else "")
                    ),
                })
    except Exception as e:
        logger.error(f"Error buscando voceros: {e}")
    return resultados


async def _buscar_actas(query: str) -> list:
    resultados = []
    q = f"%{query.lower()}%"
    try:
        from backend.database import get_db
        async with await get_db() as db:
            cursor = await db.execute(
                """
                SELECT a.codigo_registro, a.fecha_acta, a.nombre_consejo,
                       a.sector, a.pdf_path, c.nombre as consejo_nombre
                FROM actas a
                LEFT JOIN consejos_comunales c ON a.consejo_id = c.id
                WHERE LOWER(a.nombre_consejo) LIKE ?
                   OR LOWER(a.sector) LIKE ?
                   OR LOWER(c.nombre) LIKE ?
                ORDER BY a.fecha_acta DESC
                LIMIT 20
                """,
                (q, q, q),
            )
            rows = await cursor.fetchall()
            for r in rows:
                resultados.append({
                    "fuente": "actas",
                    "tipo_doc": "Acta de Elección",
                    "codigo": (r[0] or ""),
                    "fecha": (r[1] or ""),
                    "consejo": (r[2] or r[5] or ""),
                    "sector": (r[3] or ""),
                    "pdf_path": (r[4] or ""),
                    "resumen": f"Acta del {r[1]} — {r[2] or r[5]} (sector: {r[3] or 'N/A'})",
                })
    except Exception as e:
        logger.error(f"Error buscando actas: {e}")
    return resultados


async def _buscar_cartas(query: str) -> list:
    resultados = []
    q = f"%{query.lower()}%"
    try:
        from backend.database import get_db
        async with await get_db() as db:
            cursor = await db.execute(
                """
                SELECT numero_oficio, tipo, fecha, destinatario,
                       asunto, contenido, pdf_path
                FROM cartas
                WHERE LOWER(destinatario) LIKE ?
                   OR LOWER(asunto)       LIKE ?
                   OR LOWER(contenido)    LIKE ?
                   OR LOWER(numero_oficio) LIKE ?
                ORDER BY fecha DESC
                LIMIT 15
                """,
                (q, q, q, q),
            )
            rows = await cursor.fetchall()
            for r in rows:
                resultados.append({
                    "fuente": "cartas",
                    "tipo_doc": f"Carta / Oficio ({r[1]})",
                    "numero": r[0],
                    "tipo": r[1],
                    "fecha": r[2],
                    "destinatario": r[3],
                    "asunto": r[4],
                    "preview": (r[5] or "")[:200].replace("\n", " "),
                    "pdf_path": r[6],
                    "resumen": f"[{r[0]}] {r[4]} — Para: {r[3]} ({r[2]})",
                })
    except Exception as e:
        logger.error(f"Error buscando cartas: {e}")
    return resultados


async def _buscar_actividades(query: str) -> list:
    resultados = []
    q = f"%{query.lower()}%"
    try:
        from backend.database import get_db
        async with await get_db() as db:
            cursor = await db.execute(
                """
                SELECT fecha, categoria, descripcion, participantes
                FROM actividades
                WHERE LOWER(descripcion) LIKE ?
                   OR LOWER(categoria)   LIKE ?
                ORDER BY fecha DESC
                LIMIT 20
                """,
                (q, q),
            )
            rows = await cursor.fetchall()
            for r in rows:
                resultados.append({
                    "fuente": "actividades",
                    "tipo_doc": "Actividad Comunal",
                    "fecha": r[0],
                    "categoria": r[1],
                    "descripcion": r[2],
                    "participantes": r[3],
                    "resumen": f"[{r[1]}] {r[2][:100]} — {r[0]} ({r[3]} participantes)",
                })
    except Exception as e:
        logger.error(f"Error buscando actividades: {e}")
    return resultados


async def _buscar_tareas(query: str) -> list:
    resultados = []
    q = f"%{query.lower()}%"
    try:
        from backend.database import get_db
        async with await get_db() as db:
            cursor = await db.execute(
                """
                SELECT titulo, descripcion, fecha_limite, completada
                FROM tareas
                WHERE LOWER(titulo)      LIKE ?
                   OR LOWER(descripcion) LIKE ?
                ORDER BY fecha_limite ASC
                LIMIT 20
                """,
                (q, q),
            )
            rows = await cursor.fetchall()
            for r in rows:
                estado = "✅ Completada" if r[3] else "⏳ Pendiente"
                resultados.append({
                    "fuente": "tareas",
                    "tipo_doc": "Tarea / Compromiso",
                    "titulo": r[0],
                    "descripcion": r[1],
                    "fecha_limite": r[2],
                    "completada": bool(r[3]),
                    "resumen": f"{estado} — {r[0]} (vence: {r[2]})",
                })
    except Exception as e:
        logger.error(f"Error buscando tareas: {e}")
    return resultados


async def _buscar_consultas_populares(query: str) -> list:
    resultados = []
    q = f"%{query.lower()}%"
    try:
        from backend.database import get_db
        async with await get_db() as db:
            cursor = await db.execute(
                """
                SELECT id, titulo, descripcion, fecha_inicio, fecha_cierre, estado
                FROM consultas_populares
                WHERE LOWER(titulo)      LIKE ?
                   OR LOWER(descripcion) LIKE ?
                   OR LOWER(estado)      LIKE ?
                ORDER BY fecha_inicio DESC
                LIMIT 20
                """,
                (q, q, q),
            )
            rows = await cursor.fetchall()
            
            if not rows and any(w in query.lower() for w in ["cuanta", "cuánta", "cuantas", "cuántas", "cuantos", "cuántos", "todas"]):
                cursor2 = await db.execute("SELECT id, titulo, descripcion, fecha_inicio, fecha_cierre, estado FROM consultas_populares LIMIT 50")
                rows = await cursor2.fetchall()

            for r in rows:
                resultados.append({
                    "fuente": "consultas_populares",
                    "tipo_doc": "Consulta Popular",
                    "id": r[0],
                    "titulo": r[1],
                    "descripcion": r[2],
                    "fecha_inicio": r[3],
                    "fecha_cierre": r[4],
                    "estado": r[5],
                    "resumen": f"[{r[5]}] Consulta Popular: {r[1]} — (Inicio: {r[3]})",
                })
    except Exception as e:
        logger.error(f"Error buscando consultas populares: {e}")
    return resultados


async def _buscar_documentos_rag(query: str) -> list:
    resultados = []
    try:
        from backend.search import buscar_documentos
        docs = await buscar_documentos(query, top_k=8)
        for d in docs:
            resultados.append({
                "fuente": "documentos",
                "tipo_doc": f"Documento ({d.get('metodo', 'FTS5')})",
                "nombre": d["nombre"],
                "ruta": d["ruta"],
                "pagina": d["pagina"],
                "contenido": d["contenido"],
                "score": d.get("score", 0.0),
                "resumen": f"[{d['nombre']}] pág. {d['pagina']} — {d['contenido'][:120]}...",
            })
    except Exception as e:
        logger.error(f"Error en búsqueda RAG: {e}")
    return resultados


# ─────────────────────────────────────────────────────────────────────────────

async def _buscar_instancias(query: str) -> list:
    resultados = []
    q = f"%{query.lower()}%"
    try:
        from backend.database import get_db
        async with await get_db() as db:
            cursor = await db.execute("""
                SELECT i.nombre, i.tipo, i.descripcion, i.base_legal,
                       GROUP_CONCAT(v.nombre || ' (' || iv.cargo_instancia || ')') as voceros_asignados
                FROM instancias_gobierno i
                LEFT JOIN instancias_voceros iv ON iv.instancia_id = i.id AND iv.activo = 1
                LEFT JOIN voceros v ON iv.vocero_id = v.id
                WHERE LOWER(i.nombre) LIKE ? OR LOWER(i.tipo) LIKE ? OR LOWER(i.descripcion) LIKE ?
                GROUP BY i.id
                LIMIT 10
            """, (q, q, q))
            for r in await cursor.fetchall():
                resultados.append({
                    "fuente": "instancias",
                    "tipo_doc": "Instancia de Gobierno Comunal",
                    "nombre": r[0],
                    "tipo": r[1],
                    "descripcion": r[2],
                    "base_legal": r[3],
                    "voceros": r[4] or "Ninguno asignado aún",
                    "resumen": f"Instancia {r[0]} ({r[1]} - {r[3]}): Voceros: {r[4] or 'Sin voceros'}"
                })
    except Exception as e:
        logger.error(f"Error buscando instancias: {e}")
    return resultados


async def _buscar_comisiones(query: str) -> list:
    resultados = []
    q = f"%{query.lower()}%"
    try:
        from backend.database import get_db
        async with await get_db() as db:
            cursor = await db.execute("""
                SELECT c.nombre, c.area_tematica, c.descripcion, v.nombre as responsable,
                       GROUP_CONCAT(vm.nombre || ' (' || voc.cargo || ')') as voceros_miembros
                FROM comisiones_gestion c
                LEFT JOIN voceros v ON c.responsable_id = v.id
                LEFT JOIN vocerias voc ON voc.comision_id = c.id AND voc.activa = 1 AND voc.tipo_asignacion = 'comision'
                LEFT JOIN voceros vm ON voc.vocero_id = vm.id
                WHERE LOWER(c.nombre) LIKE ? OR LOWER(c.area_tematica) LIKE ? OR LOWER(c.descripcion) LIKE ?
                GROUP BY c.id
                LIMIT 10
            """, (q, q, q))
            for r in await cursor.fetchall():
                resultados.append({
                    "fuente": "comisiones",
                    "tipo_doc": "Comisión de Gestión Comunal",
                    "nombre": r[0],
                    "area": r[1],
                    "responsable": r[3] or "Por designar",
                    "miembros": r[4] or "Sin miembros adicionales",
                    "resumen": f"Comisión {r[0]} (Responsable: {r[3] or 'Por designar'}). Miembros: {r[4] or 'Sin miembros'}"
                })
    except Exception as e:
        logger.error(f"Error buscando comisiones: {e}")
    return resultados


async def _buscar_censo(query: str) -> list:
    resultados = []
    try:
        from backend.database import get_db
        q_norm = query.lower().strip()
        # Detectar consulta de estadísticas globales
        is_stats = any(w in q_norm for w in ["cuantas", "cuántas", "cuantos", "cuántos", "total",
                                              "estadistic", "resumen", "discapacidad", "chamos", "cuanta gente"])
        stopwords = {"de", "la", "el", "los", "las", "en", "un", "una", "y", "o", "al", "del",
                     "familia", "familias", "censo", "cuantas", "cuantos", "hay", "tienen",
                     "personas", "habitantes", "busca"}
        tokens = [w for w in q_norm.split() if len(w) > 3 and w not in stopwords]

        async with await get_db() as db:
            if is_stats or not tokens:
                # Retornar estadísticas globales
                cur1 = await db.execute("SELECT COUNT(*) FROM censo WHERE activo = 1")
                total_fam = (await cur1.fetchone())[0]
                cur2 = await db.execute("""
                    SELECT COUNT(*) FROM censo_demografico cd
                    JOIN censo c ON cd.censo_id = c.id WHERE c.activo = 1
                """)
                total_hab = (await cur2.fetchone())[0]
                cur3 = await db.execute("SELECT COUNT(*) FROM censo_discapacidad")
                total_disc = (await cur3.fetchone())[0]
                resultados.append({
                    "fuente": "censo",
                    "tipo_doc": "Estadísticas Censales",
                    "total_familias": total_fam,
                    "total_habitantes": total_hab,
                    "total_discapacitados": total_disc,
                    "resumen": (f"Censo comunal: {total_fam} familias registradas, "
                                f"{total_hab} habitantes totales, "
                                f"{total_disc} personas con discapacidad")
                })
                return resultados

            # Búsqueda por tokens individuales (OR entre tokens)
            conditions = " OR ".join([
                "(LOWER(c.jefe_familia) LIKE ? OR LOWER(c.cedula_jefe) LIKE ? OR LOWER(c.familia_codigo) LIKE ? OR LOWER(cc.nombre) LIKE ?)"
                for _ in tokens
            ])
            params = []
            for t in tokens:
                q = f"%{t}%"
                params.extend([q, q, q, q])

            cursor = await db.execute(f"""
                SELECT c.familia_codigo, c.jefe_familia, c.cedula_jefe, cc.nombre as consejo_nombre,
                       c.direccion, c.telefono,
                       (SELECT COUNT(*) FROM censo_demografico cd WHERE cd.censo_id = c.id) as habitantes
                FROM censo c
                LEFT JOIN consejos_comunales cc ON c.consejo_id = cc.id
                WHERE c.activo = 1 AND ({conditions})
                LIMIT 15
            """, params)
            for r in await cursor.fetchall():
                resultados.append({
                    "fuente": "censo",
                    "tipo_doc": "Expediente Censal Familiar",
                    "codigo": r[0],
                    "jefe": r[1],
                    "cedula": r[2],
                    "consejo": r[3],
                    "direccion": r[4],
                    "habitantes": r[6],
                    "resumen": f"Familia {r[0]} ({r[1]} - C.I. {r[2]}): {r[6]} hab. en {r[3]}, {r[4]}"
                })
    except Exception as e:
        logger.error(f"Error buscando censo: {e}")
    return resultados


async def _buscar_rendiciones(query: str) -> list:
    resultados = []
    q = f"%{query.lower()}%"
    try:
        from backend.database import get_db
        async with await get_db() as db:
            cursor = await db.execute("""
                SELECT r.periodo, COALESCE(i.nombre, c.nombre, 'Comunal') as instancia,
                       r.presupuesto_asignado, r.presupuesto_ejecutado, r.descripcion_logros,
                       r.aprobada, r.fecha_rendicion
                FROM rendiciones_cuentas r
                LEFT JOIN instancias_gobierno i ON r.instancia_id = i.id
                LEFT JOIN comisiones_gestion c ON r.comision_id = c.id
                WHERE LOWER(r.periodo) LIKE ? OR LOWER(r.descripcion_logros) LIKE ? OR LOWER(i.nombre) LIKE ? OR LOWER(c.nombre) LIKE ?
                ORDER BY r.fecha_rendicion DESC
                LIMIT 10
            """, (q, q, q, q))
            for r in await cursor.fetchall():
                estado = "Aprobada por Parlamento" if r[5] == 1 else "Observada" if r[5] == 2 else "En Revisión"
                resultados.append({
                    "fuente": "rendiciones",
                    "tipo_doc": "Rendición de Cuentas (Art. 52 LOC)",
                    "periodo": r[0],
                    "instancia": r[1],
                    "asignado": r[2],
                    "ejecutado": r[3],
                    "estado": estado,
                    "resumen": f"Rendición {r[0]} ({r[1]}): Ejecutado {r[3]:,.2f} Bs. de {r[2]:,.2f} Bs. [{estado}]"
                })
    except Exception as e:
        logger.error(f"Error buscando rendiciones: {e}")
    return resultados


async def _buscar_gaceta(query: str) -> list:
    resultados = []
    try:
        from backend.database import get_db
        q_norm = query.lower().strip()
        stopwords = {"de", "la", "el", "los", "las", "en", "un", "una", "y", "o", "al", "del",
                     "gaceta", "comunal", "decision", "decisión", "busca", "hay"}
        tokens = [w for w in q_norm.split() if len(w) > 3 and w not in stopwords]

        async with await get_db() as db:
            if not tokens:
                # Fallback: últimas 10 publicaciones
                cursor = await db.execute("""
                    SELECT numero, fecha, titulo, tipo_decision, contenido, aprobado_por
                    FROM gaceta_comunal
                    ORDER BY fecha DESC
                    LIMIT 10
                """)
            else:
                conditions = " OR ".join([
                    "(LOWER(titulo) LIKE ? OR LOWER(contenido) LIKE ? OR LOWER(numero) LIKE ? OR LOWER(tipo_decision) LIKE ?)"
                    for _ in tokens
                ])
                params = []
                for t in tokens:
                    q = f"%{t}%"
                    params.extend([q, q, q, q])
                cursor = await db.execute(f"""
                    SELECT numero, fecha, titulo, tipo_decision, contenido, aprobado_por
                    FROM gaceta_comunal
                    WHERE {conditions}
                    ORDER BY fecha DESC
                    LIMIT 10
                """, params)
            for r in await cursor.fetchall():
                resultados.append({
                    "fuente": "gaceta",
                    "tipo_doc": f"Gaceta Comunal ({r[3]})",
                    "numero": r[0],
                    "fecha": r[1],
                    "titulo": r[2],
                    "contenido": r[4][:300] if r[4] else "",
                    "resumen": f"[{r[0]}] {r[3]}: {r[2]} ({r[1]}) — {(r[4] or '')[:150]}..."
                })
    except Exception as e:
        logger.error(f"Error buscando gaceta: {e}")
    return resultados


async def _buscar_proyectos(query: str) -> list:
    resultados = []
    try:
        from backend.database import get_db
        q_norm = query.lower().strip()
        stopwords = {"de", "la", "el", "los", "las", "en", "un", "una", "y", "o", "al", "del",
                     "proyecto", "proyectos", "busca", "cuales", "cuáles", "hay", "tienen"}
        tokens = [w for w in q_norm.split() if len(w) > 3 and w not in stopwords]

        async with await get_db() as db:
            if not tokens:
                # Fallback: listar todos
                cursor = await db.execute("""
                    SELECT p.codigo_proyecto, p.nombre, p.descripcion, c.nombre as comision,
                           p.monto_estimado, p.porcentaje_avance, p.estado, p.beneficiarios
                    FROM proyectos_aca p
                    LEFT JOIN comisiones_gestion c ON p.comision_id = c.id
                    ORDER BY p.porcentaje_avance DESC
                    LIMIT 10
                """)
            else:
                conditions = " OR ".join([
                    "(LOWER(p.nombre) LIKE ? OR LOWER(p.descripcion) LIKE ? OR LOWER(p.codigo_proyecto) LIKE ? OR LOWER(p.estado) LIKE ?)"
                    for _ in tokens
                ])
                params = []
                for t in tokens:
                    q = f"%{t}%"
                    params.extend([q, q, q, q])
                cursor = await db.execute(f"""
                    SELECT p.codigo_proyecto, p.nombre, p.descripcion, c.nombre as comision,
                           p.monto_estimado, p.porcentaje_avance, p.estado, p.beneficiarios
                    FROM proyectos_aca p
                    LEFT JOIN comisiones_gestion c ON p.comision_id = c.id
                    WHERE {conditions}
                    ORDER BY p.porcentaje_avance DESC
                    LIMIT 10
                """, params)
            for r in await cursor.fetchall():
                resultados.append({
                    "fuente": "proyectos",
                    "tipo_doc": "Proyecto ACA",
                    "codigo": r[0],
                    "nombre": r[1],
                    "avance": r[5],
                    "estado": r[6],
                    "resumen": f"[{r[0]}] {r[1]} — Avance: {r[5]}% ({r[6]}). Inversión: {r[4]:,.2f} Bs."
                })
    except Exception as e:
        logger.error(f"Error buscando proyectos: {e}")
    return resultados


async def _buscar_loc(query: str) -> list:
    try:
        from backend.loc_knowledge import buscar_articulos_loc
        return buscar_articulos_loc(query)
    except Exception as e:
        logger.error(f"Error buscando en LOC: {e}")
        return []

# PASO 3: Fusión y ranking
# ─────────────────────────────────────────────────────────────────────────────

def _fusionar_resultados(
    resultados_por_fuente: dict,
    scores_fuentes: dict,
    limite: int = 30,
) -> list:
    todos = []
    seen = set()

    for fuente, resultados in resultados_por_fuente.items():
        peso = scores_fuentes.get(fuente, 0.1)
        for r in resultados:
            clave = r.get("resumen", "")[:80].lower().strip()
            if clave in seen:
                continue
            seen.add(clave)
            score_interno = r.get("score", 0.5)
            r["_score"] = peso * (1 - score_interno) if fuente == "documentos" else peso
            todos.append(r)

    todos.sort(key=lambda x: x["_score"], reverse=True)
    return todos[:limite]


# ─────────────────────────────────────────────────────────────────────────────
# PASO 4: Generación de respuesta con IA
# ─────────────────────────────────────────────────────────────────────────────

async def _ejecutar_herramienta(tool_name: str, args: dict) -> str:
    logger.info(f"Ejecutando herramienta IA: {tool_name} con args: {args}")
    try:
        if tool_name == "generar_carta":
            from backend.letters import crear_y_guardar_carta
            res = await crear_y_guardar_carta(
                tipo=args.get("tipo", "Oficio"),
                destinatario=args.get("destinatario", "A quien corresponda"),
                asunto=args.get("asunto", "Sin asunto"),
                instrucciones=args.get("instrucciones", ""),
                vocero_firma_id=None
            )
            return f"✅ Carta generada exitosamente. Archivo PDF guardado en: {res['pdf_path']}"
        elif tool_name == "programar_actividad":
            from backend.database import get_db
            async with await get_db() as db:
                await db.execute(
                    "INSERT INTO tareas (titulo, fecha_limite, descripcion) VALUES (?, ?, ?)",
                    (args.get("titulo", "Actividad programada por IA"), args.get("fecha_limite", ""), args.get("descripcion", ""))
                )
                await db.commit()
            return f"✅ Tarea/Actividad '{args.get('titulo')}' programada exitosamente."
        else:
            return f"❌ Herramienta desconocida: {tool_name}"
    except Exception as e:
        logger.error(f"Error en herramienta {tool_name}: {e}")
        return f"❌ Hubo un error al ejecutar la acción: {str(e)}"


async def _generar_respuesta_ia(
    query: str,
    resultados: list,
    history: list = None,
    max_context_entries: int = 30,
) -> str:
    """
    Versión optimizada FASE 1:
    - Limita contexto a máximo 30 entradas (antes: 60 para voceros, 15 para otros)
    - Resúmenes compactos con cédula incluida
    - Parámetro 'formato' eliminado (ya no se usa)
    - 'history' se pasa directamente a generar_texto()
    """
    from backend.ai_router import generar_texto

    # Función auxiliar definida UNA VEZ (no dentro del bucle)
    def _truncar(texto, limite=50):
        """Truncar texto añadiendo '...' si excede el límite"""
        return texto[:limite] + "..." if len(texto) > limite else texto

    def _enmascarar_cedula(cedula_val, query_str=""):
        """Enmascara la cédula (ej. V-***789) para proteger la privacidad ante LLMs externos."""
        if not cedula_val or str(cedula_val).strip() in ("Sin cédula", ""):
            return "No registrada"
        c_limp = str(cedula_val).strip()
        nums = "".join(ch for ch in c_limp if ch.isdigit())
        if nums and len(nums) >= 5 and nums in (query_str or ""):
            return c_limp  # El usuario buscó explícitamente esta cédula
        if len(nums) >= 4:
            pref = c_limp.split("-")[0] + "-" if "-" in c_limp else ""
            return f"{pref}***{nums[-3:]}"
        return "***"


    # OPTIMIZACIÓN: Limitar contexto a máximo 30 entradas
    limite_contexto = min(len(resultados), max_context_entries)

    # OPTIMIZACIÓN: Compactar resúmenes por tipo de fuente
    contexto_parts = []
    for i, r in enumerate(resultados[:limite_contexto], 1):
        fuente = r.get("fuente", "")
        fuente_label = r.get("tipo_doc", f"Fuente: {fuente}")

        if fuente == "voceros":
            nombre = r.get("nombre", "Sin nombre")
            cedula = _enmascarar_cedula(r.get("cedula", ""), query)
            cargo = r.get("cargo", "Sin cargo")
            consejo = r.get("consejo", "Sin consejo")

            contexto_parts.append(
                f"[{i}] 👤 {fuente_label}: {_truncar(nombre, 50)} - "
                f"C.I. {cedula} - {_truncar(cargo, 50)} ({_truncar(consejo, 50)})"
            )

        elif fuente == "documentos":
            nombre = r.get("nombre", "Documento")
            snippet = r.get("contenido", "")
            contexto_parts.append(
                f"[{i}] 📄 {fuente_label}: {_truncar(nombre, 60)} - {_truncar(snippet, 80)}"
            )

        elif fuente == "cartas":
            numero = r.get("numero", "Sin número")
            asunto = r.get("asunto", "Sin asunto")
            destinatario = r.get("destinatario", "")
            contexto_parts.append(
                f"[{i}] 📨 {fuente_label}: {numero} - {_truncar(asunto, 50)} "
                f"({_truncar(destinatario, 30)})"
            )

        elif fuente == "instancias":
            nombre = r.get("nombre", "Sin nombre")
            tipo = r.get("tipo", "")
            voceros = r.get("voceros", "Sin voceros asignados")
            contexto_parts.append(
                f"[{i}] 🏛️ {fuente_label}: {nombre} ({tipo}) — {voceros}"
            )

        elif fuente == "comisiones":
            nombre = r.get("nombre", "Sin nombre")
            resp = r.get("responsable", "Por designar")
            miembros = r.get("miembros", "")
            contexto_parts.append(
                f"[{i}] 🔧 {fuente_label}: {nombre} — Responsable: {resp}. Miembros: {_truncar(miembros, 80)}"
            )

        elif fuente == "rendiciones":
            periodo = r.get("periodo", "")
            instancia = r.get("instancia", "")
            asignado = r.get("asignado", 0)
            ejecutado = r.get("ejecutado", 0)
            estado = r.get("estado", "")
            contexto_parts.append(
                f"[{i}] 💰 {fuente_label}: {periodo} ({instancia}) — "
                f"Asignado: {asignado:,.2f} Bs. | Ejecutado: {ejecutado:,.2f} Bs. [{estado}]"
            )

        elif fuente == "gaceta":
            numero = r.get("numero", "")
            titulo = r.get("titulo", "")
            contenido = r.get("contenido", "")
            contexto_parts.append(
                f"[{i}] 📜 {fuente_label}: [{numero}] {titulo} — {_truncar(contenido, 150)}"
            )

        elif fuente == "proyectos":
            codigo = r.get("codigo", "")
            nombre = r.get("nombre", "")
            avance = r.get("avance", 0)
            estado = r.get("estado", "")
            contexto_parts.append(
                f"[{i}] 🚧 {fuente_label}: [{codigo}] {nombre} — Avance: {avance}% ({estado})"
            )

        elif fuente == "censo":
            if r.get("tipo_doc") == "Estadísticas Censales":
                contexto_parts.append(
                    f"[{i}] 📊 {fuente_label}: {r.get('resumen', '')}"
                )
            else:
                jefe = r.get("jefe", "")
                cedula = _enmascarar_cedula(r.get("cedula", ""), query)
                consejo = r.get("consejo", "")
                habitantes = r.get("habitantes", 0)
                contexto_parts.append(
                    f"[{i}] 🏠 {fuente_label}: {jefe} (C.I. {cedula}) — {habitantes} hab. en {consejo}"
                )

        else:
            resumen = r.get("resumen", "Sin resumen")
            contexto_parts.append(f"[{i}] 📋 {fuente_label}: {_truncar(resumen, 120)}")

    # Agrupar por fuente si hay muchos resultados
    if len(resultados) > 15:
        conteo_fuentes = {}
        for r in resultados:
            fuente = r.get("fuente", "otros")
            conteo_fuentes[fuente] = conteo_fuentes.get(fuente, 0) + 1

        resumen_fuentes = "\n".join(
            f"- {fuente}: {count} resultados"
            for fuente, count in conteo_fuentes.items()
        )

        contexto_str = (
            f"Resumen por fuente:\n{resumen_fuentes}\n\n"
            f"Resultados relevantes (máximo {limite_contexto}):\n"
        ) + "\n".join(contexto_parts)
    else:
        contexto_str = "\n".join(contexto_parts) if contexto_parts else "No se encontraron datos relevantes."

    system = """Eres el Asistente Digital de la Comuna Productiva Presidente Obrero (Código: C-MIX-2018-11-0019).
Tienes acceso a todos los datos de autogobierno comunal: las 5 instancias de gobierno,
las 6 comisiones de gestión, censo demográfico y comunal, rendiciones de cuentas anuales,
publicaciones de la Gaceta Comunal, Agenda Concreta de Acción (proyectos ACA) y la Ley Orgánica de las Comunas (LOC).
Tienes acceso a los datos comunales: padrón de voceros, actas de elección,
cartas y oficios, actividades, tareas y documentos archivados.

Reglas CRÍTICAS:
1. Responde SIEMPRE en español, de forma clara y estructurada.
2. Usa ÚNICAMENTE los datos de la sección "INFORMACIÓN ENCONTRADA". NO inventes ni añadas datos externos.
3. Si la consulta pide voceros de una unidad específica (ej: Legislativa), muestra SOLO los de esa unidad. La lista ya viene pre-filtrada.
4. Cuando respondas sobre voceros, usa una tabla Markdown con columnas: # | Nombre | Cédula | Cargo | Tipo | Teléfono | Consejo Comunal.
5. Si no encuentras algo específico, dilo claramente sin inventar.
6. Al inicio de tu respuesta, indica el filtro aplicado (ej: "Voceros Legislativos del CC Manuelita Sáenz: X encontrados")."""
    system += """
7. HERRAMIENTAS (Function Calling): Si el usuario pide crear una carta u oficio, O programar una actividad, DEBES responder ÚNICAMENTE con un bloque JSON, sin texto adicional:
{
  "tool": "nombre_herramienta",
  "args": { "param1": "valor1" }
}
Herramientas disponibles:
- generar_carta: args={"tipo": "Solicitud/Convocatoria", "destinatario": "...", "asunto": "...", "instrucciones": "..."}
- programar_actividad: args={"titulo": "...", "fecha_limite": "YYYY-MM-DD HH:MM", "descripcion": "..."}"""

    prompt = f"""CONSULTA: {query}

INFORMACIÓN ENCONTRADA ({len(resultados)} registros pre-filtrados según tu consulta):
{contexto_str}

Genera una respuesta completa y EXACTA basada ÚNICAMENTE en estos datos. No añadas voceros que no estén en la lista."""

    try:
        respuesta = await generar_texto(prompt, system_instruction=system, history=history)

        # Interceptar Tool Calling
        json_match = re.search(r'```json\n(.*?)\n```', respuesta, re.DOTALL)
        if not json_match:
            if respuesta.strip().startswith('{') and respuesta.strip().endswith('}'):
                json_str = respuesta.strip()
            else:
                json_str = None
        else:
            json_str = json_match.group(1)

        if json_str:
            try:
                tool_data = json.loads(json_str)
                if "tool" in tool_data and "args" in tool_data:
                    return await _ejecutar_herramienta(tool_data["tool"], tool_data["args"])
            except json.JSONDecodeError:
                pass

        return respuesta
    except Exception as e:
        logger.error(f"Error generando respuesta IA: {e}")
        lines = [f"**Resultados encontrados para:** *{query}*\n"]
        for r in resultados[:15]:
            lines.append(f"- **{r.get('tipo_doc', 'Dato')}**: {r['resumen']}")
        if not resultados:
            lines.append("No se encontraron resultados en ninguna fuente.")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

async def consulta_universal(
    query: str,
    formato: str = "markdown",
    incluir_raw: bool = False,
    thread_id: str = None,
) -> dict:
    from backend.database import guardar_mensaje_chat, obtener_historial_chat
    inicio = datetime.now()
    logger.info(f"[UniversalAgent] Consulta: '{query}' (Thread: {thread_id})")

    history = []
    if thread_id:
        history = await obtener_historial_chat(thread_id, limit=10)

    scores_fuentes = _clasificar_intencion(query)

    mapa_funciones = {
        "voceros":    _buscar_voceros,
        "actas":      _buscar_actas,
        "cartas":     _buscar_cartas,
        "actividades": _buscar_actividades,
        "tareas":     _buscar_tareas,
        "documentos": _buscar_documentos_rag,
        "consultas_populares": _buscar_consultas_populares,
        "instancias": _buscar_instancias,
        "comisiones": _buscar_comisiones,
        "censo": _buscar_censo,
        "rendiciones": _buscar_rendiciones,
        "gaceta": _buscar_gaceta,
        "proyectos": _buscar_proyectos,
        "legal": _buscar_loc,
    }

    coros = {
        fuente: mapa_funciones[fuente](query)
        for fuente in scores_fuentes
        if fuente in mapa_funciones
    }

    resultados_por_fuente = {}
    if coros:
        resultados_lista = await asyncio.gather(*coros.values(), return_exceptions=True)
        for fuente, resultado in zip(coros.keys(), resultados_lista):
            if isinstance(resultado, Exception):
                logger.error(f"Fuente '{fuente}' falló: {resultado}")
                resultados_por_fuente[fuente] = []
            else:
                resultados_por_fuente[fuente] = resultado

        resultados_fusionados = _fusionar_resultados(
        resultados_por_fuente, scores_fuentes, limite=30
    )

    fuentes_con_datos = [f for f, r in resultados_por_fuente.items() if r]

    respuesta = await _generar_respuesta_ia(
        query,
        resultados_fusionados,
        history=history
    )
    ...
    
    if thread_id:
        await guardar_mensaje_chat(thread_id, "user", query)
        await guardar_mensaje_chat(thread_id, "assistant", respuesta)

    tiempo_ms = int((datetime.now() - inicio).total_seconds() * 1000)
    logger.info(
        f"[UniversalAgent] Completado en {tiempo_ms}ms. "
        f"Fuentes con datos: {fuentes_con_datos}. "
        f"Total hallazgos: {len(resultados_fusionados)}"
    )

    salida = {
        "respuesta": respuesta,
        "fuentes_usadas": fuentes_con_datos,
        "fuentes_consultadas": list(scores_fuentes.keys()),
        "total_hallazgos": len(resultados_fusionados),
        "tiempo_ms": tiempo_ms,
    }

    if incluir_raw:
        raw = [{k: v for k, v in r.items() if k != "_score"} for r in resultados_fusionados]
        salida["raw_results"] = raw

    return salida


# ─────────────────────────────────────────────────────────────────────────────
# BÚSQUEDA EN CARPETA (sin indexar)
# ─────────────────────────────────────────────────────────────────────────────

async def buscar_en_carpeta(
    query: str,
    carpeta: str,
    extensiones: Optional[list] = None,
) -> dict:
    from backend.indexer import (
        extraer_texto_pdf, extraer_texto_docx,
        extraer_texto_excel, extraer_texto_txt, extraer_texto_imagen,
    )

    carpeta_path = Path(carpeta)
    if not carpeta_path.exists():
        return {
            "respuesta": f"La carpeta `{carpeta}` no existe o no es accesible.",
            "archivos_revisados": 0,
            "coincidencias": [],
        }

    exts_soportadas = extensiones or [
        ".pdf", ".docx", ".doc", ".xlsx", ".xls",
        ".csv", ".txt", ".md", ".png", ".jpg", ".jpeg",
    ]

    extractores = {
        ".pdf":  extraer_texto_pdf,
        ".docx": extraer_texto_docx,
        ".doc":  extraer_texto_docx,
        ".xlsx": extraer_texto_excel,
        ".xls":  extraer_texto_excel,
        ".csv":  extraer_texto_excel,
        ".txt":  extraer_texto_txt,
        ".md":   extraer_texto_txt,
        ".png":  extraer_texto_imagen,
        ".jpg":  extraer_texto_imagen,
        ".jpeg": extraer_texto_imagen,
    }

    q_lower = query.lower()
    coincidencias = []
    archivos_revisados = 0

    for filepath in sorted(carpeta_path.rglob("*")):
        if not filepath.is_file():
            continue
        if filepath.suffix.lower() not in exts_soportadas:
            continue

        archivos_revisados += 1
        extractor = extractores.get(filepath.suffix.lower())
        if not extractor:
            continue

        try:
            paginas = await asyncio.to_thread(extractor, filepath)
            for pag in paginas:
                texto = pag.get("texto", "")
                if q_lower in texto.lower():
                    idx = texto.lower().find(q_lower)
                    inicio_ctx = max(0, idx - 100)
                    fin_ctx = min(len(texto), idx + 200)
                    fragmento = "..." + texto[inicio_ctx:fin_ctx].replace("\n", " ") + "..."
                    coincidencias.append({
                        "archivo": filepath.name,
                        "ruta": str(filepath),
                        "pagina": pag.get("pagina", 1),
                        "fragmento": fragmento,
                    })
                    break
        except Exception as e:
            logger.warning(f"No se pudo leer {filepath.name}: {e}")

    if coincidencias:
        contexto = "\n".join(
            f"- {c['archivo']} (pág. {c['pagina']}): {c['fragmento']}"
            for c in coincidencias[:10]
        )
        from backend.ai_router import generar_texto
        try:
            respuesta = await generar_texto(
                f"El usuario busca '{query}' en la carpeta '{carpeta_path.name}'.\n\n"
                f"Se encontraron coincidencias en estos archivos:\n{contexto}\n\n"
                f"Resume qué información encontraste y en qué archivos.",
                system_instruction=(
                    "Eres el Asistente de la Comuna. Responde en español, "
                    "citando los archivos donde encontraste la información."
                ),
            )
        except Exception:
            respuesta = (
                f"Se encontraron **{len(coincidencias)} archivos** con coincidencias "
                f"para '{query}' en `{carpeta_path.name}`."
            )
    else:
        respuesta = (
            f"No se encontró '{query}' en ninguno de los "
            f"{archivos_revisados} archivos revisados en `{carpeta_path.name}`."
        )

    return {
        "respuesta": respuesta,
        "archivos_revisados": archivos_revisados,
        "coincidencias": coincidencias,
    }
