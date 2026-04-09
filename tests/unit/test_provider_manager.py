import pytest
from unittest.mock import AsyncMock, patch
from src.services.providers.manager import ProviderManager, ProviderNotFoundError


PROVIDERS_FIXTURE = [
    {
        "id": "prov-local",
        "name": "Local LLM",
        "type": "openai_compatible",
        "base_url": "http://jota-inference:8002",
        "api_key": "local-key",
        "default_model_id": "llama-3.2-3b",
        "is_active": True,
    },
    {
        "id": "prov-openai",
        "name": "OpenAI",
        "type": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-abc",
        "default_model_id": "gpt-4o",
        "is_active": True,
    },
    {
        "id": "prov-anthropic",
        "name": "Anthropic",
        "type": "anthropic",
        "base_url": "",
        "api_key": "ant-key",
        "default_model_id": "claude-3-5-sonnet",
        "is_active": True,
    },
]


@pytest.mark.asyncio
async def test_init_creates_adapters_by_type():
    pm = ProviderManager()
    await pm.init(PROVIDERS_FIXTURE, default_provider_id="prov-local")

    from src.services.providers.openai_compatible import OpenAICompatibleAdapter
    from src.services.providers.anthropic import AnthropicAdapter
    assert isinstance(pm.get_adapter("prov-local"), OpenAICompatibleAdapter)
    assert isinstance(pm.get_adapter("prov-openai"), OpenAICompatibleAdapter)
    assert isinstance(pm.get_adapter("prov-anthropic"), AnthropicAdapter)


@pytest.mark.asyncio
async def test_get_adapter_raises_for_unknown_provider():
    pm = ProviderManager()
    await pm.init(PROVIDERS_FIXTURE, default_provider_id="prov-local")

    with pytest.raises(ProviderNotFoundError):
        pm.get_adapter("does-not-exist")


@pytest.mark.asyncio
async def test_get_default_returns_configured_provider():
    pm = ProviderManager()
    await pm.init(PROVIDERS_FIXTURE, default_provider_id="prov-local")

    provider_id, model_id = pm.get_default()
    assert provider_id == "prov-local"
    assert model_id == "llama-3.2-3b"


@pytest.mark.asyncio
async def test_get_default_raises_before_init():
    pm = ProviderManager()
    with pytest.raises(RuntimeError):
        pm.get_default()


@pytest.mark.asyncio
async def test_init_skips_unknown_types(caplog):
    providers_with_unknown = PROVIDERS_FIXTURE + [{
        "id": "prov-unknown",
        "type": "unknown_provider",
        "base_url": "",
        "api_key": "",
        "default_model_id": "",
    }]
    pm = ProviderManager()
    await pm.init(providers_with_unknown, default_provider_id="prov-local")

    with pytest.raises(ProviderNotFoundError):
        pm.get_adapter("prov-unknown")