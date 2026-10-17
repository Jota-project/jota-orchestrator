# src/services/providers/anthropic.py
from typing import AsyncGenerator

from .base import BaseProvider
from .types import InferRequest, InferEvent, DoneEvent, ProviderCapabilities


class AnthropicAdapter(BaseProvider):
    """Placeholder — Anthropic adapter not yet implemented."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(tool_format="anthropic_tool_use")

    async def infer(self, request: InferRequest) -> AsyncGenerator[InferEvent, None]:
        raise NotImplementedError("Anthropic adapter not yet implemented")
        yield DoneEvent()  # makes this an async generator

    async def list_models(self) -> list[str]:
        raise NotImplementedError("Anthropic adapter not yet implemented")

    async def check_health(self) -> bool:
        return False
