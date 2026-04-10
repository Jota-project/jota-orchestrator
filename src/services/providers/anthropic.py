from .base import BaseProvider


class AnthropicAdapter(BaseProvider):
    """Placeholder — Anthropic adapter not yet implemented."""

    async def infer(self, messages, model, params=None):
        raise NotImplementedError("Anthropic adapter not yet implemented")
        yield  # make it an async generator

    async def list_models(self) -> list[str]:
        raise NotImplementedError("Anthropic adapter not yet implemented")

    async def check_health(self) -> bool:
        return False