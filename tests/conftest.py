import pytest
import asyncio
from unittest.mock import AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_memory_manager():
    m = AsyncMock()
    m.save_message = AsyncMock()
    m.mark_conversation_error = AsyncMock()
    m.get_conversation_messages = AsyncMock(return_value=[])
    m.get_conversation = AsyncMock(return_value=None)
    m.get_client_config = AsyncMock(return_value=None)
    m.get_orchestrator_config = AsyncMock(return_value={
        "default_provider_id": "prov-test",
        "system_prompt": "Eres Jota.",
        "tool_followup_prompt": "Responde usando los resultados.",
    })
    m.get_providers = AsyncMock(return_value=[])
    return m


@pytest.fixture
def mock_provider():
    """A mock BaseProvider that yields a single token."""
    async def _infer(messages, model, params=None):
        yield "Hello world"

    p = AsyncMock()
    p.infer = _infer
    p.check_health = AsyncMock(return_value=True)
    return p


@pytest.fixture
def mock_provider_manager(mock_provider):
    pm = AsyncMock()
    pm.get_adapter = AsyncMock(return_value=mock_provider)
    pm.get_default = AsyncMock(return_value=("prov-test", "model-test"))
    pm.check_health = AsyncMock(return_value={"prov-test": True})
    return pm


@pytest.fixture
def mock_config_manager():
    from src.core.config_manager import OrchestratorConfig
    cm = AsyncMock()
    cm.config = OrchestratorConfig(
        default_provider_id="prov-test",
        system_prompt="Eres Jota.",
        tool_followup_prompt="Responde usando los resultados.",
    )
    return cm