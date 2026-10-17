# src/services/providers/manager.py
import logging
from .base import BaseProvider
from .openai_compatible import OpenAICompatibleAdapter
from .anthropic import AnthropicAdapter
from .gemini import GeminiAdapter

logger = logging.getLogger(__name__)

_ADAPTER_MAP = {
    "openai": OpenAICompatibleAdapter,
    "local": OpenAICompatibleAdapter,   # placeholder until jota-inference exposes HTTP API
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
}

# Types that use OpenAICompatibleAdapter and need base_url + api_key constructor args
_OPENAI_COMPATIBLE_TYPES = {"openai", "local", "openai_compatible"}


class ProviderNotFoundError(Exception):
    pass


class ProviderManager:
    """
    Manages inference provider adapters loaded from JotaDB.
    Must be initialized via init() before use.
    """

    def __init__(self):
        self._adapters: dict[str, BaseProvider] = {}
        self._providers_meta: dict[str, dict] = {}
        self._default_provider_id: str | None = None

    async def init(self, providers: list[dict], default_provider_id: str) -> None:
        """
        Instantiates one adapter per active provider based on its type.
        Unknown types are logged and skipped.
        """
        self._adapters = {}
        self._providers_meta = {}
        self._default_provider_id = default_provider_id

        for p in providers:
            provider_id = p["id"]                          # FIX: was p["name"]
            provider_type = p.get("type", "openai")
            adapter_class = _ADAPTER_MAP.get(provider_type)

            if not adapter_class:
                logger.warning(
                    f"Unknown provider type {provider_type!r} for provider {provider_id!r} — skipping"
                )
                continue

            if provider_type in _OPENAI_COMPATIBLE_TYPES:
                adapter = adapter_class(
                    base_url=p.get("base_url"),            # None means use SDK default (OpenAI)
                    api_key=p.get("api_key", ""),
                )
            else:
                adapter = adapter_class()

            self._adapters[provider_id] = adapter
            self._providers_meta[provider_id] = p
            logger.info(f"Provider registered: {provider_id!r} ({provider_type})")

    def get_adapter(self, provider_id: str) -> BaseProvider:
        if provider_id not in self._adapters:
            raise ProviderNotFoundError(f"Provider {provider_id!r} not registered")
        return self._adapters[provider_id]

    def get_default(self) -> tuple[str, str]:
        """Returns (default_provider_id, default_model_id)."""
        if self._default_provider_id is None:
            raise RuntimeError("ProviderManager not initialized. Call init() first.")
        meta = self._providers_meta.get(self._default_provider_id, {})
        return self._default_provider_id, meta.get("default_model_id", "")

    async def check_health(self) -> dict[str, bool]:
        """Returns health status for each registered provider."""
        result = {}
        for pid, adapter in self._adapters.items():
            result[pid] = await adapter.check_health()
        return result
