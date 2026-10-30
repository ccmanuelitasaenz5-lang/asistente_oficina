import httpx
import logging
from datetime import date
from typing import Optional
from backend.config import (
    GROQ_API_KEY,
    GEMINI_API_KEY,
    COHERE_API_KEY,
    HUGGINGFACE_API_KEY,
    ZHIPU_API_KEY,
    NVIDIA_API_KEY,
    AI_PRIORITY,
    AI_QUOTAS
)

logger = logging.getLogger("ai_router")

# ── Persistencia de cuotas ──────────────────────────────────────────────────
async def _get_uso_hoy(proveedor: str) -> int:
    try:
        from backend.database import get_db
        hoy = date.today().isoformat()
        async with await get_db() as db:
            cursor = await db.execute(
                "SELECT llamadas FROM ai_usage WHERE fecha=? AND proveedor=?",
                (hoy, proveedor)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
    except Exception as e:
        logger.warning(f"No se pudo leer cuota de DB para {proveedor}: {e}")
        return AI_QUOTAS.get(proveedor, {}).get("used", 0)

async def _incrementar_uso(proveedor: str):
    try:
        from backend.database import get_db
        hoy = date.today().isoformat()
        async with await get_db() as db:
            await db.execute(
                """
                INSERT INTO ai_usage (fecha, proveedor, llamadas)
                VALUES (?, ?, 1)
                ON CONFLICT(fecha, proveedor)
                DO UPDATE SET llamadas = llamadas + 1
                """,
                (hoy, proveedor)
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"No se pudo guardar cuota en DB para {proveedor}: {e}")
    if proveedor in AI_QUOTAS:
        AI_QUOTAS[proveedor]["used"] += 1

API_STATUS = {provider: True for provider in AI_PRIORITY}

def _build_standard_messages(prompt: str, system: str, history: list) -> list:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    if history:
        msgs.extend(history)
    if prompt:
        msgs.append({"role": "user", "content": prompt})
    return msgs

async def call_groq(prompt: str, system: str, history: list = None) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    data = {
        "model": "openai/gpt-oss-20b",
        "messages": _build_standard_messages(prompt, system, history),
        "temperature": 0.3
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 200:
            AI_QUOTAS["groq"]["used"] += 1
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.error(f"Groq API Error: {response.status_code} - {response.text}")
            return None

async def call_gemini(prompt: str, system: str, history: list = None) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    modelos_gemini = ["gemini-2.5-flash", "gemini-2.0-flash"]
    
    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"Instrucción del sistema: {system}"}]})
        contents.append({"role": "model", "parts": [{"text": "Entendido."}]})
        
    if history:
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
            
    if prompt:
        contents.append({"role": "user", "parts": [{"text": prompt}]})
    
    for modelo in modelos_gemini:
        url = f"https://generativelanguage.googleapis.com/v1/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": contents,
            "generationConfig": {"temperature": 0.3}
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                AI_QUOTAS["gemini"]["used"] += 1
                try:
                    return response.json()["candidates"][0]["content"]["parts"][0]["text"]
                except Exception as e:
                    logger.error(f"Gemini parsing error: {e}")
                    return None
            else:
                logger.warning(f"Gemini API Error con {modelo}: {response.status_code}")
    
    return None

async def call_cohere(prompt: str, system: str, history: list = None) -> Optional[str]:
    if not COHERE_API_KEY:
        return None
    url = "https://api.cohere.com/v2/chat"
    headers = {"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"}
    
    data = {
        "model": "command-r",
        "messages": _build_standard_messages(prompt, system, history),
        "temperature": 0.3
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 200:
            AI_QUOTAS["cohere"]["used"] += 1
            return response.json()["message"]["content"][0]["text"]
        else:
            logger.error(f"Cohere API Error: {response.status_code} - {response.text}")
            return None

async def call_huggingface(prompt: str, system: str, history: list = None) -> Optional[str]:
    if not HUGGINGFACE_API_KEY:
        return None
    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}", "Content-Type": "application/json"}
    
    full_prompt = ""
    if system:
        full_prompt += f"<s>[INST] {system} [/INST] Entendido. </s>"
    if history:
        for msg in history:
            if msg["role"] == "user":
                full_prompt += f"[INST] {msg['content']} [/INST]"
            else:
                full_prompt += f" {msg['content']} </s>"
    if prompt:
        full_prompt += f"[INST] {prompt} [/INST]"
        
    data = {
        "inputs": full_prompt,
        "parameters": {"max_new_tokens": 1024, "temperature": 0.3}
    }
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 200:
            AI_QUOTAS["huggingface"]["used"] += 1
            res = response.json()
            if isinstance(res, list) and len(res) > 0:
                gen_text = res[0].get("generated_text", "")
                if gen_text.startswith(full_prompt):
                    gen_text = gen_text[len(full_prompt):]
                return gen_text.strip()
            return str(res)
        else:
            logger.error(f"HuggingFace API Error: {response.status_code} - {response.text}")
            return None
# ─────────────────────────────────────────────────────────────
# NVIDIA NIM (build.nvidia.com) — Cascada de modelos gratuitos
# ─────────────────────────────────────────────────────────────
# Rate limit: 40 RPM por modelo, sin costo.
# Estrategia: si un modelo falla (429, 410, 500), probar el siguiente.
NVIDIA_MODELOS = [
    "nvidia/nemotron-3-super-120b-a12b",     # Principal (el que ya funciona)
    "deepseek-ai/deepseek-v4-flash-0731",    # Fallback 1
    "moonshotai/kimi-k3",                    # Fallback 2
    "qwen/qwen3-next-80b",                   # Fallback 3
]

async def call_nvidia(prompt: str, system: str, history: list = None) -> Optional[str]:
    """
    Cascada de modelos de NVIDIA NIM.
    Prueba cada modelo en orden. Si uno falla, prueba el siguiente.
    """
    if not NVIDIA_API_KEY:
        return None

    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }

    for modelo in NVIDIA_MODELOS:
        data = {
            "model": modelo,
            "messages": _build_standard_messages(prompt, system, history),
            "temperature": 0.3,
            "max_tokens": 8192,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=data)

                if response.status_code == 200:
                    AI_QUOTAS["nvidia"]["used"] += 1
                    logger.info(f"NVIDIA NIM OK con modelo: {modelo}")
                    return response.json()["choices"][0]["message"]["content"]

                elif response.status_code in (429, 410, 500, 503):
                    logger.warning(
                        f"NVIDIA {modelo} falló ({response.status_code}), "
                        f"probando siguiente modelo..."
                    )
                    continue
                else:
                    logger.error(
                        f"NVIDIA {modelo} error {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                    continue
        except Exception as e:
            logger.error(f"NVIDIA {modelo} excepción: {e}")
            continue

    logger.error("Todos los modelos de NVIDIA fallaron")
    return None

async def call_zhipu(prompt: str, system: str, history: list = None) -> Optional[str]:
    if not ZHIPU_API_KEY:
        return None
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {"Authorization": f"Bearer {ZHIPU_API_KEY}", "Content-Type": "application/json"}
    
    data = {
        "model": "glm-4.7-flash",
        "messages": _build_standard_messages(prompt, system, history),
        "temperature": 0.3
    }
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 200:
            AI_QUOTAS["zhipu"]["used"] += 1
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.error(f"Zhipu API Error: {response.status_code} - {response.text}")
            return None

CALL_FUNCTIONS = {
    "nvidia": call_nvidia,
    "zhipu": call_zhipu,
    "groq": call_groq,
    "gemini": call_gemini,
    "cohere": call_cohere,
    "huggingface": call_huggingface
}

async def generar_texto(prompt: str, system_instruction: str = "", history: list = None) -> str:
    errores = []
    for provider in AI_PRIORITY:
        quota_config = AI_QUOTAS.get(provider, {"limit": 0})
        uso_hoy = await _get_uso_hoy(provider)
        if uso_hoy >= quota_config.get("limit", 0):
            logger.warning(f"Proveedor {provider} omitido: cuota.")
            continue

        logger.info(f"Intentando {provider} (uso: {uso_hoy})")
        try:
            func = CALL_FUNCTIONS[provider]
            resultado = await func(prompt, system_instruction, history)
            if resultado is not None:
                await _incrementar_uso(provider)
                return resultado
        except Exception as e:
            logger.error(f"Error {provider}: {str(e)}")
            errores.append(f"{provider}: {str(e)}")

    error_msg = f"Todos fallaron: {', '.join(errores)}"
    logger.critical(error_msg)
    raise RuntimeError(error_msg)
