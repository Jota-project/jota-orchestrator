# tests/unit/test_openai_adapter.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.providers.openai_compatible import OpenAICompatibleAdapter
from src.services.providers.types import (
    InferRequest, ToolSchema,
    TextDelta, ToolCallEvent, DoneEvent, ProviderCapabilities,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_text_chunk(content: str, finish_reason=None):
    """Chunk carrying plain text content."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    choice = chunk.choices[0]
    choice.finish_reason = finish_reason
    choice.delta = MagicMock()
    choice.delta.content = content
    choice.delta.tool_calls = None
    return chunk


def _make_tool_chunk(index: int, name: str = "", arguments: str = "", finish_reason=None):
    """Chunk carrying a partial tool call delta."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    choice = chunk.choices[0]
    choice.finish_reason = finish_reason
    choice.delta = MagicMock()
    choice.delta.content = None

    tc = MagicMock()
    tc.index = index
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    choice.delta.tool_calls = [tc]
    return chunk


def _make_empty_chunk():
    """Chunk with no choices (should be skipped)."""
    chunk = MagicMock()
    chunk.choices = []
    return chunk


async def _async_gen(*chunks):
    for c in chunks:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_capabilities_tool_format_is_native():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")
    assert adapter.capabilities.tool_format == "native"
    assert isinstance(adapter.capabilities, ProviderCapabilities)


@pytest.mark.asyncio
async def test_infer_yields_text_delta_events():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")
    mock_stream = _async_gen(
        _make_text_chunk("Hello"),
        _make_text_chunk(" world"),
        _make_text_chunk("!"),
    )

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        request = InferRequest(messages=[{"role": "user", "content": "Hi"}], model="test-model")
        events = [e async for e in adapter.infer(request)]

    text_events = [e for e in events if isinstance(e, TextDelta)]
    assert "".join(e.content for e in text_events) == "Hello world!"


@pytest.mark.asyncio
async def test_infer_ends_with_done_event():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")
    mock_stream = _async_gen(_make_text_chunk("Hi"))

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        request = InferRequest(messages=[{"role": "user", "content": "Hi"}], model="test-model")
        events = [e async for e in adapter.infer(request)]

    assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_infer_yields_tool_call_event_from_structured_delta():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")

    # Simulate OpenAI streaming: name arrives in first chunk, arguments chunked across two
    mock_stream = _async_gen(
        _make_tool_chunk(index=0, name="web_search", arguments=""),
        _make_tool_chunk(index=0, name="", arguments='{"query": "py'),
        _make_tool_chunk(index=0, name="", arguments='thon"}', finish_reason="tool_calls"),
    )

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        request = InferRequest(messages=[{"role": "user", "content": "search"}], model="test-model")
        events = [e async for e in adapter.infer(request)]

    tool_events = [e for e in events if isinstance(e, ToolCallEvent)]
    assert len(tool_events) == 1
    assert tool_events[0].name == "web_search"
    assert tool_events[0].arguments == {"query": "python"}


@pytest.mark.asyncio
async def test_infer_skips_empty_chunks():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")
    mock_stream = _async_gen(_make_empty_chunk(), _make_text_chunk("Hi"))

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        request = InferRequest(messages=[{"role": "user", "content": "test"}], model="test-model")
        events = [e async for e in adapter.infer(request)]

    text_events = [e for e in events if isinstance(e, TextDelta)]
    assert "".join(e.content for e in text_events) == "Hi"


@pytest.mark.asyncio
async def test_infer_passes_tools_to_openai_api():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")
    mock_stream = _async_gen(_make_text_chunk("ok"))
    create_mock = AsyncMock(return_value=mock_stream)

    tool = ToolSchema(
        name="search",
        description="Search the web",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )

    with patch.object(adapter._client.chat.completions, "create", new=create_mock):
        request = InferRequest(
            messages=[{"role": "user", "content": "hi"}],
            model="test-model",
            tools=[tool],
        )
        _ = [e async for e in adapter.infer(request)]

    call_kwargs = create_mock.call_args.kwargs
    assert "tools" in call_kwargs
    assert call_kwargs["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the web",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            },
        }
    ]
    assert call_kwargs["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_infer_does_not_pass_tools_when_none():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")
    mock_stream = _async_gen(_make_text_chunk("ok"))
    create_mock = AsyncMock(return_value=mock_stream)

    with patch.object(adapter._client.chat.completions, "create", new=create_mock):
        request = InferRequest(
            messages=[{"role": "user", "content": "hi"}],
            model="test-model",
            tools=None,
        )
        _ = [e async for e in adapter.infer(request)]

    call_kwargs = create_mock.call_args.kwargs
    assert "tools" not in call_kwargs
    assert "tool_choice" not in call_kwargs


@pytest.mark.asyncio
async def test_check_health_returns_true_on_success():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")
    mock_models = MagicMock()
    mock_models.data = [MagicMock(id="model-1")]
    adapter._client.models.list = AsyncMock(return_value=mock_models)

    assert await adapter.check_health() is True


@pytest.mark.asyncio
async def test_check_health_returns_false_on_exception():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")
    adapter._client.models.list = AsyncMock(side_effect=Exception("connection refused"))

    assert await adapter.check_health() is False
