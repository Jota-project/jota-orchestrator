import pytest
from unittest.mock import AsyncMock
from src.core.config_manager import ConfigManager, OrchestratorConfig


@pytest.fixture
def mock_memory():
    m = AsyncMock()
    m.get_orchestrator_config = AsyncMock(return_value={
        "default_provider_id": "prov-uuid",
        "system_prompt": "Eres Jota.",
        "tool_followup_prompt": "Usa los resultados para responder.",
    })
    return m


@pytest.mark.asyncio
async def test_load_parses_config(mock_memory):
    cm = ConfigManager(memory_manager=mock_memory)
    await cm.load()

    assert cm.config.default_provider_id == "prov-uuid"
    assert cm.config.system_prompt == "Eres Jota."
    assert cm.config.tool_followup_prompt == "Usa los resultados para responder."


@pytest.mark.asyncio
async def test_config_raises_before_load():
    mock_memory = AsyncMock()
    cm = ConfigManager(memory_manager=mock_memory)

    with pytest.raises(RuntimeError, match="not initialized"):
        _ = cm.config


@pytest.mark.asyncio
async def test_load_uses_defaults_for_missing_keys(mock_memory):
    mock_memory.get_orchestrator_config = AsyncMock(return_value={
        "default_provider_id": "prov-uuid",
        # system_prompt and tool_followup_prompt missing
    })
    cm = ConfigManager(memory_manager=mock_memory)
    await cm.load()

    assert "Jota" in cm.config.system_prompt
    assert cm.config.tool_followup_prompt != ""


@pytest.mark.asyncio
async def test_load_raises_if_default_provider_missing(mock_memory):
    mock_memory.get_orchestrator_config = AsyncMock(return_value={})
    cm = ConfigManager(memory_manager=mock_memory)

    with pytest.raises(RuntimeError, match="default_provider_id"):
        await cm.load()