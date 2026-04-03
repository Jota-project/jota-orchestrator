"""
rest.py
~~~~~~~
Router REST de datos y configuración para clientes del orquestador.

Agrupa todos los endpoints de consulta y ajuste que no requieren
WebSocket ni streaming. Escalable: añade nuevos recursos como
secciones independientes dentro de este fichero o en sub-routers
incluídos aquí.

Rutas base (todas bajo el prefijo /api definido en main.py):
  GET    /api/models
  GET    /api/conversations
  GET    /api/conversations/{conversation_id}/messages
  PATCH  /api/conversations/{conversation_id}/model
"""
from fastapi import APIRouter, Query, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.core.services import inference_client, memory_manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["data"])


# ===========================================================================
# Auth helper
# ===========================================================================

async def _require_client(x_client_key: str) -> dict:
    """Valida la clave de cliente y devuelve su registro. Lanza 401 si falla."""
    client_data = await memory_manager.validate_client_key(x_client_key)
    if not client_data:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return client_data


# ===========================================================================
# Models
# ===========================================================================

@router.get("/models", summary="Lista modelos disponibles en el Engine")
async def get_models(
    x_client_key: str = Header(..., description="Client authentication key"),
):
    """
    Devuelve la lista de modelos cargados en el InferenceCenter.
    La respuesta se cachea en el InferenceClient (TTL configurable en settings).
    """
    await _require_client(x_client_key)
    try:
        models = await inference_client.list_models()
        return {"status": "success", "models": models}
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=503, detail=f"Engine unavailable: {e}")


# ===========================================================================
# Conversations
# ===========================================================================

@router.get(
    "/conversations",
    summary="Lista las últimas N conversaciones del cliente autenticado",
)
async def get_conversations(
    x_client_key: str = Header(..., description="Client authentication key"),
    limit: int = Query(10, ge=1, le=100, description="Número de conversaciones a devolver"),
):
    client_data = await _require_client(x_client_key)
    client_id = client_data["id"]

    try:
        conversations = await memory_manager.get_user_conversations(client_id, limit=limit)
        return {"status": "success", "conversations": conversations}
    except Exception as e:
        logger.error(f"Error listing conversations for client {client_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/conversations/{conversation_id}/messages",
    summary="Devuelve los mensajes de una conversación",
)
async def get_conversation_messages(
    conversation_id: str,
    x_client_key: str = Header(..., description="Client authentication key"),
    limit: int = Query(50, ge=1, le=1000, description="Número de mensajes a devolver"),
):
    client_data = await _require_client(x_client_key)
    client_id = client_data["id"]

    try:
        messages = await memory_manager.get_conversation_messages(
            conversation_id, client_id, limit=limit
        )
        return {"status": "success", "messages": messages}
    except Exception as e:
        logger.error(f"Error retrieving messages for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Conversation configuration
# ===========================================================================

class ConversationModelUpdate(BaseModel):
    model_id: str


@router.patch(
    "/conversations/{conversation_id}/model",
    summary="Actualiza el modelo asignado a una conversación",
)
async def update_conversation_model(
    conversation_id: str,
    body: ConversationModelUpdate,
    x_client_key: str = Header(..., description="Client authentication key"),
):
    """
    Persiste el modelo preferido en la BD para esta conversación.
    Valida que el model_id exista en el Engine antes de guardar.
    """
    client_data = await _require_client(x_client_key)
    client_id = client_data["id"]

    # Validar que el modelo existe (usa caché TTL del InferenceClient)
    try:
        available_models = await inference_client.list_models()
        model_ids = (
            [m.get("id") or m.get("model_id") or m for m in available_models]
            if isinstance(available_models, list)
            else []
        )
        if model_ids and body.model_id not in model_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Modelo '{body.model_id}' no encontrado. Disponibles: {model_ids}",
            )
    except HTTPException:
        raise
    except Exception as e:
        # Si el Engine no responde, permitimos el update igualmente
        logger.warning(f"No se pudo validar el modelo en el Engine: {e}")

    ok = await memory_manager.set_conversation_model(conversation_id, client_id, body.model_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Error al actualizar el modelo en BD")

    return {
        "status": "success",
        "conversation_id": conversation_id,
        "model_id": body.model_id,
    }
