"""
WebSocket API endpoints for chat operations.

This module handles persistent bi-directional communication with client
applications, allowing real-time token streaming, mid-session control 
messages (e.g., model switching), and context management over a single connection.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.core.services import jota_controller, memory_manager
import json as _json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/chat/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handles a full WebSocket chat session.

    Performs sequential actions:
    1. Authenticate client connection.
    2. Manage or create conversation context.
    4. Recover database context and inject it.
    5. Listen to text inputs and control streams via JSON envelopes.
    """
    # 1. Authentication
    # Allow passing auth token via query params for simpler WebSocket clients
    client_key = websocket.headers.get("x-client-key") or websocket.query_params.get("x_client_key") or websocket.query_params.get("client_key")
    if not client_key:
        logger.warning("Missing Client Key header or query param")
        await websocket.close(code=4001, reason="Unauthorized")
        return

    client_data = await memory_manager.validate_client_key(client_key)
    if not client_data:
        logger.warning("Unauthorized access attempt")
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # 2. Validar tipo de cliente
    client_type = client_data.get("client_type", "CHAT")
    if client_type == "QUICK":
        logger.warning(f"QUICK client {client_data['id']} attempted WS connection")
        await websocket.close(code=4003, reason="Client type 'QUICK' not allowed on WebSocket")
        return

    client_id = client_data["id"]

    await websocket.accept()
    logger.info(f"WebSocket connected for client {client_id}")

    try:
        # 2. Conversation Management
        conversation_id = websocket.query_params.get("conversation_id")
        model_id = websocket.query_params.get("model_id") or None
        provider_id = websocket.query_params.get("provider_id") or None
        if not conversation_id:
            conversation = await memory_manager.create_conversation(
                client_id=client_id,
                model_id=model_id,
                provider_id=provider_id,
            )
            conversation_id = conversation["id"]
            logger.info(
                f"[TRACE][Conv: {conversation_id}] New conversation created "
                f"for client={client_id} model_id={model_id!r}"
            )
        elif model_id or provider_id:
           # Update conversation model/provider in DB
            update: dict = {}
            if model_id:
                update["model_id"] = model_id
            if provider_id:
                update["provider_id"] = provider_id
            await memory_manager.set_conversation_model(
                conversation_id, client_id, model_id or ""
            )

        log_prefix = f"[Conv: {conversation_id}]"
        logger.info(f"{log_prefix} Session ready. Waiting for messages...")

        while True:
            data = await websocket.receive_text()
            logger.info(f"{log_prefix} Received via WS: {data}")

            # -- Control message: JSON envelope with "type" field --
            # Allows mid-session operations without reconnecting.
            try:
                ctrl = _json.loads(data)
                if isinstance(ctrl, dict) and "type" in ctrl:
                    msg_type = ctrl["type"]

                    if msg_type == "switch_model":
                        new_model = ctrl.get("model_id", "").strip()
                        new_provider = ctrl.get("provider_id", "").strip() or None
                        if not new_model:
                            await websocket.send_text(_json.dumps({
                                "type": "error",
                                "message": "switch_model requires a non-empty model_id",
                            }))
                            continue
                        await memory_manager.set_conversation_model(
                            conversation_id, client_id, new_model
                        )
                        await websocket.send_text(_json.dumps({
                            "type": "model_switched",
                            "model_id": new_model,
                        }))
                        continue

                    logger.warning(f"{log_prefix} Unknown control type: {msg_type!r}")
                    await websocket.send_text(_json.dumps({
                        "type": "error",
                        "message": f"Unknown control type: {msg_type!r}",
                    }))
                    continue
            except _json.JSONDecodeError:
                pass  # plain text prompt

            # Save user message
            await memory_manager.save_message(
                conversation_id=conversation_id,
                role="user",
                content=data,
                client_id=client_id,
            )

            payload = {
                "content": data,
                "conversation_id": conversation_id,
                "client_id": client_id,
            }

            # Stream tokens back
            async for token in jota_controller.handle_input(payload):
                if isinstance(token, dict):
                    await websocket.send_text(_json.dumps(token))
                else:
                    await websocket.send_text(_json.dumps({"type": "token", "content": token}))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for client {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        await websocket.close(code=1011)

