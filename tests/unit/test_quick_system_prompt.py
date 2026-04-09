"""Tests: _quick_stream_generator builds system prompt correctly."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.quick import _quick_stream_generator, QUICK_SYSTEM_PROMPT_PREFIX, QuickRequest


async def _collect(gen) -> list[dict]:
    results = []
    async for line in gen:
        line = line.strip()
        if line:
            results.append(json.loads(line))
    return results


def _make_adapter(tokens=("hola",)):
    adapter = MagicMock()

    async def fake_infer(messages, model, params=None):
        for t in tokens:
            yield t

    adapter.infer = MagicMock(side_effect=fake_infer)
    return adapter


@pytest.fixture
def mock_config():
    with patch("src.api.quick.config_manager") as mock:
        mock.config.system_prompt = "Eres Jota."
        mock.config.tool_followup_prompt = "Usa los resultados."
        yield mock


@pytest.fixture
def mock_tools():
    with patch("src.api.quick.tool_manager") as mock:
        mock.get_system_prompt_addition = MagicMock(return_value=None)
        yield mock


@pytest.mark.asyncio
async def test_system_prompt_extra_appended_when_provided(mock_config, mock_tools):
    adapter = _make_adapter()
    request = QuickRequest(text="hola", system_prompt_extra="responde siempre en inglés")

    await _collect(_quick_stream_generator(adapter, "cid", "model-x", request))

    call_args = adapter.infer.call_args
    messages = call_args[0][0]
    system_content = messages[0]["content"]
    assert "responde siempre en inglés" in system_content


@pytest.mark.asyncio
async def test_system_prompt_extra_not_present_when_none(mock_config, mock_tools):
    adapter = _make_adapter()
    request = QuickRequest(text="hola", system_prompt_extra=None)

    await _collect(_quick_stream_generator(adapter, "cid", "model-x", request))

    call_args = adapter.infer.call_args
    messages = call_args[0][0]
    system_content = messages[0]["content"]
    assert QUICK_SYSTEM_PROMPT_PREFIX.strip() in system_content
    assert "responde siempre en inglés" not in system_content


@pytest.mark.asyncio
async def test_system_prompt_extra_empty_string_ignored(mock_config, mock_tools):
    adapter = _make_adapter()
    request = QuickRequest(text="hola", system_prompt_extra="")

    await _collect(_quick_stream_generator(adapter, "cid", "model-x", request))

    call_args = adapter.infer.call_args
    messages = call_args[0][0]
    system_content = messages[0]["content"]
    assert QUICK_SYSTEM_PROMPT_PREFIX.strip() in system_content
