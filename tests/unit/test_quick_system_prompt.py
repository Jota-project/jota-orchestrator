"""Tests: _quick_stream_generator appends system_prompt_extra to full_prompt."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def _collect(gen) -> list[dict]:
    results = []
    async for line in gen:
        line = line.strip()
        if line:
            results.append(json.loads(line))
    return results


@pytest.fixture
def mock_inference():
    with patch("src.api.quick.inference_client") as mock:
        mock.create_session = AsyncMock(return_value="sess-1")
        mock.close_session = AsyncMock()
        mock.set_context = AsyncMock()

        async def fake_infer(*args, **kwargs):
            yield "hola"

        mock.infer = MagicMock(side_effect=fake_infer)
        yield mock


@pytest.fixture
def mock_tools():
    with patch("src.api.quick.tool_manager") as mock:
        mock.get_system_prompt_addition = MagicMock(return_value=None)
        yield mock


@pytest.mark.asyncio
async def test_system_prompt_extra_appended_when_provided(mock_inference, mock_tools):
    from src.api.quick import _quick_stream_generator

    await _collect(
        _quick_stream_generator(
            client_id="cid",
            session_id="sess-1",
            text="hola",
            model_id=None,
            system_prompt_extra="responde siempre en inglés",
        )
    )

    call_kwargs = mock_inference.infer.call_args.kwargs
    assert "responde siempre en inglés" in call_kwargs["params"]["system_prompt"]


@pytest.mark.asyncio
async def test_system_prompt_extra_not_present_when_none(mock_inference, mock_tools):
    from src.api.quick import _quick_stream_generator, QUICK_SYSTEM_PROMPT

    await _collect(
        _quick_stream_generator(
            client_id="cid",
            session_id="sess-1",
            text="hola",
            model_id=None,
            system_prompt_extra=None,
        )
    )

    call_kwargs = mock_inference.infer.call_args.kwargs
    system_prompt = call_kwargs["params"]["system_prompt"]
    assert system_prompt.strip().startswith(QUICK_SYSTEM_PROMPT.strip())


@pytest.mark.asyncio
async def test_system_prompt_extra_empty_string_ignored(mock_inference, mock_tools):
    from src.api.quick import _quick_stream_generator, QUICK_SYSTEM_PROMPT

    await _collect(
        _quick_stream_generator(
            client_id="cid",
            session_id="sess-1",
            text="hola",
            model_id=None,
            system_prompt_extra="",
        )
    )

    call_kwargs = mock_inference.infer.call_args.kwargs
    system_prompt = call_kwargs["params"]["system_prompt"]
    assert system_prompt.strip().startswith(QUICK_SYSTEM_PROMPT.strip())
