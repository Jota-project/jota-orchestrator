import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.memory import MemoryManager


@pytest.fixture
def manager():
    with patch("src.core.memory.settings") as mock_cfg:
        mock_cfg.JOTA_DB_URL = "http://testdb"
        mock_cfg.JOTA_DB_SK = "sk_test"
        mock_cfg.JOTA_DB_TIMEOUT = 10.0
        mock_cfg.SSL_VERIFY = True
        mock_cfg.ORCHESTRATOR_ID = "jota_orchestrator"
        mock_cfg.ORCHESTRATOR_API_KEY = "test_api_key"
        m = MemoryManager()
        m.mock_cfg = mock_cfg
        yield m


@pytest.mark.asyncio
async def test_get_orchestrator_config_calls_correct_endpoint(manager):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"key": "default_provider_id", "value": "uuid-123"},
        {"key": "system_prompt", "value": "Eres Jota"},
        {"key": "tool_followup_prompt", "value": "Responde usando los resultados."},
    ]
    mock_response.raise_for_status = MagicMock()
    manager.client.get = AsyncMock(return_value=mock_response)

    result = await manager.get_orchestrator_config()

    manager.client.get.assert_called_once()
    call_url = manager.client.get.call_args[0][0]
    assert f"/internal/service-config/{manager.mock_cfg.ORCHESTRATOR_ID}" in call_url
    assert result == {
        "default_provider_id": "uuid-123",
        "system_prompt": "Eres Jota",
        "tool_followup_prompt": "Responde usando los resultados.",
    }


@pytest.mark.asyncio
async def test_get_providers_calls_correct_endpoint(manager):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "id": "prov-uuid",
            "name": "Local LLM",
            "type": "openai_compatible",
            "base_url": "http://jota-inference:8002",
            "api_key": "local-key",
            "default_model_id": "llama-3.2-3b",
            "is_active": True,
        }
    ]
    mock_response.raise_for_status = MagicMock()
    manager.client.get = AsyncMock(return_value=mock_response)

    result = await manager.get_providers()

    call_url = manager.client.get.call_args[0][0]
    assert "/internal/providers" in call_url
    assert len(result) == 1
    assert result[0]["id"] == "prov-uuid"


@pytest.mark.asyncio
async def test_get_client_config_returns_none_on_404(manager):
    mock_response = MagicMock()
    mock_response.status_code = 404
    manager.client.get = AsyncMock(return_value=mock_response)

    result = await manager.get_client_config("client-abc")
    assert result is None


@pytest.mark.asyncio
async def test_create_conversation_sends_provider_id(manager):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "conv-1", "provider_id": "prov-uuid", "model_id": "llama-3b"}
    mock_response.raise_for_status = MagicMock()
    manager.client.post = AsyncMock(return_value=mock_response)

    result = await manager.create_conversation(
        client_id="client-1",
        model_id="llama-3b",
        provider_id="prov-uuid"
    )

    payload = manager.client.post.call_args[1]["json"]
    assert payload["provider_id"] == "prov-uuid"
    assert result["id"] == "conv-1"