# tests/unit/test_controller_input.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.controller.core import JotaController
from src.services.providers.types import (
    TextDelta, ToolCallEvent, DoneEvent, ErrorEvent, ProviderCapabilities,
)


def _make_controller(memory_manager, provider_manager, config_manager):
    return JotaController(
        provider_manager=provider_manager,
        memory_manager=memory_manager,
        config_manager=config_manager,
    )


def _make_provider(*events):
    """Returns a mock provider that yields the given events from infer()."""
    async def _infer(request):
        for e in events:
            yield e

    p = MagicMock()
    p.infer = _infer
    p.capabilities = ProviderCapabilities(tool_format="native")
    return p


def _base_payload():
    return {
        "content": "hola",
        "conversation_id": "conv-1",
        "client_id": "client-1",
        "stateless": True,
    }


@pytest.mark.asyncio
async def test_handle_input_streams_text_delta_to_client(
    mock_memory_manager, mock_provider_manager, mock_config_manager
):
    provider = _make_provider(TextDelta(content="Hola"), TextDelta(content=" mundo"), DoneEvent())
    mock_provider_manager.get_adapter = MagicMock(return_value=provider)

    controller = _make_controller(mock_memory_manager, mock_provider_manager, mock_config_manager)

    with patch("src.core.controller.input.tool_manager") as mock_tm:
        mock_tm.get_typed_tool_schemas.return_value = []
        mock_tm.get_system_prompt_addition.return_value = ""
        tokens = [t async for t in controller.handle_input(_base_payload())]

    assert "Hola" in tokens
    assert " mundo" in tokens


@pytest.mark.asyncio
async def test_handle_input_executes_tool_and_re_infers(
    mock_memory_manager, mock_provider_manager, mock_config_manager
):
    # First pass: tool call. Second pass: final text.
    first_pass = [ToolCallEvent(name="web_search", arguments={"query": "python"}), DoneEvent()]
    second_pass = [TextDelta(content="Python es un lenguaje."), DoneEvent()]

    call_count = 0

    async def _infer(request):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            for e in first_pass:
                yield e
        else:
            call_count += 1
            for e in second_pass:
                yield e

    provider = MagicMock()
    provider.infer = _infer
    provider.capabilities = ProviderCapabilities(tool_format="native")
    mock_provider_manager.get_adapter = MagicMock(return_value=provider)

    controller = _make_controller(mock_memory_manager, mock_provider_manager, mock_config_manager)

    with patch("src.core.controller.input.tool_manager") as mock_tm:
        mock_tm.get_typed_tool_schemas.return_value = []
        mock_tm.get_system_prompt_addition.return_value = ""
        mock_tm.execute_tool = AsyncMock(return_value="Python result")

        tokens = [t async for t in controller.handle_input(_base_payload())]

    # Second pass text must be in output
    assert "Python es un lenguaje." in tokens
    # Tool was executed
    mock_tm.execute_tool.assert_called_once_with("web_search", client_id="client-1", query="python")


@pytest.mark.asyncio
async def test_handle_input_yields_error_on_error_event(
    mock_memory_manager, mock_provider_manager, mock_config_manager
):
    provider = _make_provider(ErrorEvent(message="timeout"), DoneEvent())
    mock_provider_manager.get_adapter = MagicMock(return_value=provider)

    controller = _make_controller(mock_memory_manager, mock_provider_manager, mock_config_manager)

    with patch("src.core.controller.input.tool_manager") as mock_tm:
        mock_tm.get_typed_tool_schemas.return_value = []
        mock_tm.get_system_prompt_addition.return_value = ""
        tokens = [t async for t in controller.handle_input(_base_payload())]

    assert any("[Error:" in str(t) for t in tokens)


@pytest.mark.asyncio
async def test_handle_input_injects_xml_instructions_for_xml_provider(
    mock_memory_manager, mock_provider_manager, mock_config_manager
):
    from src.services.providers.types import ToolSchema

    xml_provider = MagicMock()

    captured_request = None

    async def capturing_infer(request):
        nonlocal captured_request
        captured_request = request
        yield TextDelta(content="ok")
        yield DoneEvent()

    xml_provider.infer = capturing_infer
    xml_provider.capabilities = ProviderCapabilities(tool_format="xml")
    mock_provider_manager.get_adapter = MagicMock(return_value=xml_provider)

    controller = _make_controller(mock_memory_manager, mock_provider_manager, mock_config_manager)

    tool = ToolSchema(name="search", description="Search", parameters={"type": "object", "properties": {}})

    with patch("src.core.controller.input.tool_manager") as mock_tm:
        mock_tm.get_typed_tool_schemas.return_value = [tool]
        mock_tm.get_system_prompt_addition.return_value = "USE TOOLS LIKE THIS: <tool_call>"
        _ = [t async for t in controller.handle_input(_base_payload())]

    # XML provider: tools must NOT be in InferRequest, XML instructions in system prompt
    assert captured_request.tools is None
    assert "USE TOOLS LIKE THIS" in captured_request.messages[0]["content"]
