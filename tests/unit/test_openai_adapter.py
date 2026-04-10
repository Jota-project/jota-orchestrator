import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.providers.openai_compatible import OpenAICompatibleAdapter


def _make_chunk(content: str):
    """Creates a mock OpenAI stream chunk with text content."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta = MagicMock()
    chunk.choices[0].delta.content = content
    return chunk


async def _async_gen(*chunks):
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_infer_yields_text_tokens():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")

    mock_stream = _async_gen(
        _make_chunk("Hello"),
        _make_chunk(" world"),
        _make_chunk("!"),
    )

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        tokens = []
        async for token in adapter.infer(
            messages=[{"role": "user", "content": "Hi"}],
            model="test-model",
        ):
            tokens.append(token)

    assert all(isinstance(t, str) for t in tokens)
    assert "".join(tokens) == "Hello world!"


@pytest.mark.asyncio
async def test_infer_detects_xml_tool_call():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")

    tool_json = '{"name": "search", "arguments": {"query": "python"}}'
    mock_stream = _async_gen(
        _make_chunk(f'<tool_call>{tool_json}</tool_call>'),
    )

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        results = []
        async for item in adapter.infer(
            messages=[{"role": "user", "content": "search python"}],
            model="test-model",
        ):
            results.append(item)

    tool_calls = [r for r in results if isinstance(r, dict) and r.get("type") == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["payload"]["name"] == "search"
    assert tool_calls[0]["payload"]["arguments"]["query"] == "python"


@pytest.mark.asyncio
async def test_infer_skips_empty_chunks():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")

    empty_chunk = MagicMock()
    empty_chunk.choices = []

    mock_stream = _async_gen(empty_chunk, _make_chunk("Hi"))

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        tokens = []
        async for token in adapter.infer(
            messages=[{"role": "user", "content": "test"}],
            model="test-model",
        ):
            tokens.append(token)

    assert "".join(tokens) == "Hi"


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