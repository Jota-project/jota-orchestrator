"""
quick.py — Endpoint REST para clientes QUICK: comandos rápidos, stateless.
"""
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import logging
import json
import time

from src.core.services import memory_manager, provider_manager, config_manager
from src.core.tool_manager import tool_manager

logger = logging.getLogger(__name__)
router = APIRouter()

QUICK_SYSTEM_PROMPT_PREFIX = """REGLAS DE RESPUESTA (obligatorias):
1. Responde siempre en 1-2 frases MÁXIMO. Sin introducción, sin contexto extra.
2. PROHIBIDO usar markdown: ningún **, *, _, #, ni listas con guiones. El texto se dicta por voz.
3. Habla de forma directa y afirmativa. Omite fórmulas de cortesía innecesarias.

USO DE HERRAMIENTAS:
- Si necesitas buscar información, emite el bloque <tool_call> de forma INMEDIATA, sin ningún texto previo.
- Tras recibir el resultado de la herramienta, resume lo relevante en MÁXIMO 2 frases.
- No menciones que usaste una herramienta ni el proceso interno.
"""


class QuickRequest(BaseModel):
    text: str
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    system_prompt_extra: Optional[str] = None


async def _quick_stream_generator(
    adapter,
    client_id: str,
    model_id: str,
    request: QuickRequest,
) -> AsyncGenerator[str, None]:
    log_prefix = f"[QUICK][Client: {client_id}]"

    # Build system prompt
    tool_instructions = tool_manager.get_system_prompt_addition(client_id=client_id)
    base_prompt = config_manager.config.system_prompt
    full_prompt = f"{base_prompt}\n\n{QUICK_SYSTEM_PROMPT_PREFIX}"
    if tool_instructions:
        full_prompt += f"\n{tool_instructions}"
    if request.system_prompt_extra:
        full_prompt += f"\n{request.system_prompt_extra}"

    messages = [
        {"role": "system", "content": full_prompt},
        {"role": "user", "content": request.text},
    ]
    quick_params = {"temp": 0.3, "max_tokens": 150}
    quick_final_params = {"temp": 0.3, "max_tokens": 100}

    tool_executed = False
    tool_context: list[dict] = []

    try:
        async for token in adapter.infer(messages, model_id, quick_params):
            if isinstance(token, dict) and token.get("type") == "tool_call":
                tc_payload = token.get("payload", {})
                tool_name = tc_payload.get("name")
                tool_args = tc_payload.get("arguments", {})

                logger.info(f"{log_prefix} Tool call: {tool_name}")
                yield json.dumps({"type": "status", "content": f"Buscando información usando {tool_name}..."}) + "\n"

                try:
                    start_t = time.time()
                    result = await tool_manager.execute_tool(tool_name, client_id=client_id, **tool_args)
                    duration = f"{time.time() - start_t:.2f}s"
                    result_str = result if isinstance(result, str) else json.dumps(result)

                    tool_context = [
                        {"role": "user", "content": request.text},
                        {"role": "assistant", "content": f"<tool_call>{json.dumps(tc_payload)}</tool_call>"},
                        {"role": "tool", "content": result_str},
                    ]
                    yield json.dumps({"type": "status", "content": f"Búsqueda completada en {duration}. Generando respuesta..."}) + "\n"
                    tool_executed = True
                except Exception as e:
                    logger.error(f"{log_prefix} Tool {tool_name} failed: {e}")
                    yield json.dumps({"type": "status", "content": f"Error al usar {tool_name}: {e}"}) + "\n"
                    tool_executed = True
            else:
                if not tool_executed and isinstance(token, str):
                    yield json.dumps({"type": "token", "content": token}) + "\n"

        if tool_executed:
            yield json.dumps({"type": "status", "content": "Analizando resultados..."}) + "\n"
            followup_messages = [{"role": "system", "content": full_prompt}] + tool_context + [
                {"role": "user", "content": config_manager.config.tool_followup_prompt}
            ]
            async for token in adapter.infer(followup_messages, model_id, quick_final_params):
                if isinstance(token, str):
                    yield json.dumps({"type": "token", "content": token}) + "\n"

    except Exception as e:
        logger.error(f"{log_prefix} Error: {e}")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"


@router.post("/quick")
async def quick_endpoint(
    request: QuickRequest,
    x_client_key: str = Header(..., description="Client authentication key"),
):
    """
    Endpoint NDJSON stream para comandos rápidos y voz.
    Stateless — no guarda mensajes. Optimizado para TTS.
    """
    client_data = await memory_manager.validate_client_key(x_client_key)
    if not client_data:
        raise HTTPException(status_code=401, detail="Unauthorized")

    client_type = client_data.get("client_type", "CHAT")
    if client_type != "QUICK":
        raise HTTPException(
            status_code=403,
            detail=f"Client type '{client_type}' not allowed on /quick endpoint.",
        )

    client_id = client_data["id"]

    # Resolve provider + model
    client_config = await memory_manager.get_client_config(str(client_id))
    default_provider_id, default_model_id = provider_manager.get_default()

    provider_id = request.provider_id or default_provider_id
    model_id = (
        request.model_id
        or (client_config or {}).get("preferred_model_id")
        or default_model_id
    )
    adapter = provider_manager.get_adapter(provider_id)

    return StreamingResponse(
        _quick_stream_generator(adapter, client_id, model_id, request),
        media_type="application/x-ndjson",
    )
