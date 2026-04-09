from .base import BaseProvider


class GeminiAdapter(BaseProvider):
    """Placeholder — Gemini adapter not yet implemented."""

    async def infer(self, messages, model, params=None):
        raise NotImplementedError("Gemini adapter not yet implemented")
        yield

    async def list_models(self) -> list[str]:
        raise NotImplementedError("Gemini adapter not yet implemented")

    async def check_health(self) -> bool:
        return False