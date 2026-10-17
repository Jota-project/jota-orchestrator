# src/services/providers/openai_compatible.py
import json
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

from .base import BaseProvider
from .types import (
    InferRequest, InferEvent,
    TextDelta, ToolCallEvent, DoneEvent, ErrorEvent,
    ProviderCapabilities, ToolSchema,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter(BaseProvider):
    """
    Adapter for any OpenAI-compatible API (OpenAI, Groq, Mistral, local HTTP, etc.).

    Tool calls are delivered via OpenAI's native function calling protocol:
    structured delta fields, not XML pattern matching.
    """

    def __init__(self, base_url: str | None, api_key: str):
        self._client = AsyncOpenAI(
            base_url=base_url or None,   # None → SDK uses api.openai.com
            api_key=api_key or "not-needed",
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(tool_format="native")

    async def infer(self, request: InferRequest) -> AsyncGenerator[InferEvent, None]:
        kwargs: dict = {
            "model": request.model,
            "messages": request.messages,
            "stream": True,
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.tools:
            kwargs["tools"] = [self._to_openai_tool(t) for t in request.tools]
            kwargs["tool_choice"] = "auto"

        # Accumulate tool call deltas: index → {"name": str, "arguments": str}
        tool_call_chunks: dict[int, dict] = {}

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            # Text tokens
            if delta.content:
                yield TextDelta(content=delta.content)

            # Tool call delta chunks — accumulate by index
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_chunks:
                        tool_call_chunks[idx] = {"name": "", "arguments": ""}
                    if tc.function and tc.function.name:
                        tool_call_chunks[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_call_chunks[idx]["arguments"] += tc.function.arguments

            # finish_reason == "tool_calls" means all chunks for this call are in
            if choice.finish_reason == "tool_calls":
                for idx in sorted(tool_call_chunks.keys()):
                    tc = tool_call_chunks[idx]
                    try:
                        arguments = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse tool call arguments for '{tc['name']}': {e}")
                        arguments = {}
                    yield ToolCallEvent(name=tc["name"], arguments=arguments)
                tool_call_chunks.clear()

        yield DoneEvent()

    def _to_openai_tool(self, tool: ToolSchema) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    async def list_models(self) -> list[str]:
        models = await self._client.models.list()
        return [m.id for m in models.data]

    async def check_health(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
