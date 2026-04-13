# src/services/providers/gemini.py
from typing import AsyncGenerator

from .base import BaseProvider
from .types import InferRequest, InferEvent, DoneEvent, ProviderCapabilities


class GeminiAdapter(BaseProvider):
    """Placeholder — Gemini adapter not yet implemented."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(tool_format="native")

    async def infer(self, request: InferRequest) -> AsyncGenerator[InferEvent, None]:
        raise NotImplementedError("Gemini adapter not yet implemented")
        yield DoneEvent()  # makes this an async generator

    async def list_models(self) -> list[str]:
        raise NotImplementedError("Gemini adapter not yet implemented")

    async def check_health(self) -> bool:
        return False
