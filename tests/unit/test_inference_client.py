import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.services.inference import InferenceClient
from src.core.config import settings
import json

@pytest.mark.asyncio
async def test_inference_client_initialization(inference_config):
    """Test that the client initializes with provided config."""
    client = InferenceClient(**inference_config)

    assert client.url == inference_config["url"]
    assert client.client_id == settings.ORCHESTRATOR_ID
    assert client.api_key == settings.ORCHESTRATOR_API_KEY
    assert client.websocket is None
    assert client.active_sessions == {}

@pytest.mark.asyncio
async def test_inference_client_defaults(mock_memory_manager):
    """Test that the client uses settings when no URL is provided."""
    with patch("src.services.inference.client.settings") as mock_conf:
        mock_conf.INFERENCE_SERVICE_URL = "ws://default"
        mock_conf.ORCHESTRATOR_ID = "default_id"
        mock_conf.ORCHESTRATOR_API_KEY = "default_key"
        mock_conf.MODELS_CACHE_TTL = 300.0

        client = InferenceClient(memory_manager=mock_memory_manager)
        assert client.url == "ws://default"
        assert client.client_id == "default_id"

@pytest.mark.asyncio
async def test_connect_starts_background_task(inference_config):
    """Test that connect() starts the background connection loop task."""
    client = InferenceClient(**inference_config)
    assert client._connection_task is None

    with patch.object(client, '_connection_loop', new_callable=AsyncMock):
        await client.connect()
        assert client._connection_task is not None

    await client.invoke_shutdown()

@pytest.mark.asyncio
async def test_connect_idempotent(inference_config):
    """Test that calling connect() twice does not start a second task."""
    client = InferenceClient(**inference_config)

    with patch.object(client, '_connection_loop', new_callable=AsyncMock):
        await client.connect()
        task_after_first = client._connection_task

        await client.connect()
        assert client._connection_task is task_after_first

    await client.invoke_shutdown()

@pytest.mark.asyncio
async def test_is_connected_false_when_no_websocket(inference_config):
    """Test is_connected returns False when websocket is None."""
    client = InferenceClient(**inference_config)
    assert not client.is_connected

@pytest.mark.asyncio
async def test_create_session(inference_config):
    """Test that create_session sends the correct op and returns the session_id."""
    client = InferenceClient(**inference_config)
    client.websocket = AsyncMock()
    client.websocket.open = True

    with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait:
        mock_wait.return_value = "session_123"

        session_id = await client.create_session()

        assert session_id == "session_123"
        sent_msg = json.loads(client.websocket.send.call_args[0][0])
        assert sent_msg["op"] == "create_session"

@pytest.mark.asyncio
async def test_ensure_session_tracks_user(inference_config):
    """Test that ensure_session records the session under the user_id."""
    client = InferenceClient(**inference_config)
    client.websocket = AsyncMock()
    client.websocket.open = True

    with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait:
        mock_wait.return_value = "session_456"

        session_id = await client.ensure_session("user_1")

        assert session_id == "session_456"
        assert client._user_sessions["user_1"] == "session_456"

@pytest.mark.asyncio
async def test_ensure_session_closes_previous(inference_config):
    """Test that ensure_session closes the existing session before creating a new one."""
    client = InferenceClient(**inference_config)
    client.websocket = AsyncMock()
    client.websocket.open = True
    client._user_sessions["user_1"] = "old_session"

    with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait:
        mock_wait.return_value = "new_session"

        session_id = await client.ensure_session("user_1")

        assert session_id == "new_session"
        assert client._user_sessions["user_1"] == "new_session"

        # close_session op should have been sent for the old session
        sent_msgs = [json.loads(call[0][0]) for call in client.websocket.send.call_args_list]
        close_msgs = [m for m in sent_msgs if m.get("op") == "close_session"]
        assert len(close_msgs) == 1
        assert close_msgs[0]["session_id"] == "old_session"
