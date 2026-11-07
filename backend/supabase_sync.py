"""
backend/supabase_sync.py
Módulo de integración y sincronización de datos con Supabase Cloud.
Permite mantener la réplica en la nube para la PWA móvil y evitar la pausa del Free Tier.
"""

import os
import logging
from typing import Dict, Any, List
from backend.database import get_db

logger = logging.getLogger("supabase_sync")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def get_supabase_client():
    """Retorna un cliente de Supabase si las credenciales están configuradas."""
    if not SUPABASE_URL or not SUPABASE_KEY or SUPABASE_URL == "tu_supabase_url":
        logger.warning("Credenciales de Supabase no configuradas en .env. Modo local activo.")
        return None
    try:
        from supabase import create_client, Client
        client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return client
    except ImportError:
        logger.warning("Librería 'supabase' no instalada. Ejecute: pip install supabase")
        return None
    except Exception as e:
        logger.error(f"Error conectando a Supabase: {e}")
        return None


async def ping_supabase_keepalive() -> bool:
    """Envía un ping periódico a Supabase para evitar que el Free Tier pause el proyecto."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        # Consulta liviana para mantener la base de datos despierta
        res = client.table("instancias_gobierno").select("id").limit(1).execute()
        logger.info("Ping keepalive a Supabase completado exitosamente.")
        return True
    except Exception as e:
        logger.error(f"Error en ping keepalive de Supabase: {e}")
        return False


async def sincronizar_hacia_nube() -> Dict[str, Any]:
    """
    Sincroniza tablas maestras desde SQLite local hacia Supabase Cloud.
    Estrategia: Upsert de instancias, comisiones, proyectos y gaceta.
    """
    client = get_supabase_client()
    if not client:
        return {"status": "skipped", "message": "Supabase no configurado"}

    reporte = {"tablas_sincronizadas": [], "errores": []}

    tablas = [
        ("instancias_gobierno", "id"),
        ("comisiones_gestion", "id"),
        ("gaceta_comunal", "id"),
        ("proyectos_aca", "id"),
    ]

    async with await get_db() as db:
        for tabla, pk in tablas:
            try:
                cursor = await db.execute(f"SELECT * FROM {tabla}")
                rows = [dict(r) for r in await cursor.fetchall()]
                if rows:
                    # Enviar en bloques a Supabase
                    client.table(tabla).upsert(rows).execute()
                    reporte["tablas_sincronizadas"].append(f"{tabla} ({len(rows)} registros)")
            except Exception as e:
                logger.error(f"Error sincronizando tabla {tabla}: {e}")
                reporte["errores"].append({tabla: str(e)})

    return {"status": "success", "reporte": reporte}

