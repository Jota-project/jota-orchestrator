# Provider Typed Protocol — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the untyped `AsyncGenerator[str | dict, None]` provider interface with a fully typed protocol (`InferRequest`, `InferEvent` union, `ToolSchema`, `ProviderCapabilities`), fix two bugs in `manager.py`, and wire OpenAI native function calling throughout the system.

**Architecture:** A new `types.py` module defines all shared data contracts. `BaseProvider` adopts these types as its interface. `OpenAICompatibleAdapter` replaces XML detection with structured delta parsing. The controller and quick endpoint become provider-agnostic by reading `adapter.capabilities.tool_format` to decide how tools are delivered.

**Tech Stack:** Python 3.12, FastAPI, openai SDK (`AsyncOpenAI`), pytest-asyncio, unittest.mock

---

## File Map

| Action | Path |
|--------|------|
| **CREATE** | `src/services/providers/types.py` |
| **MODIFY** | `src/services/providers/base.py` |
| **MODIFY** | `src/services/providers/anthropic.py` |
| **MODIFY** | `src/services/providers/gemini.py` |
| **MODIFY** | `src/services/providers/manager.py` |
| **MODIFY** | `src/services/providers/openai_compatible.py` |
| **MODIFY** | `src/core/tool_manager.py` |
| **MODIFY** | `src/core/controller/input.py` |
| **MODIFY** | `src/api/quick.py` |
| **MODIFY** | `tests/conftest.py` |
| **MODIFY** | `tests/unit/test_provider_manager.py` |
| **MODIFY** | `tests/unit/test_openai_adapter.py` |
| **CREATE** | `tests/unit/test_controller_input.py` |
| **MODIFY** | `tests/unit/test_quick_system_prompt.py` |

---

## Task 1: Create `src/services/providers/types.py`

This file is the foundation — every other task depends on it. No tests needed (pure dataclasses with no logic).

**Files:**
- Create: `src/services/providers/types.py`

- [ ] **Step 1: Create the file**

```python
# src/services/providers/types.py
from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Tool canonical representation
# Passed from ToolManager to adapters. Each adapter converts to its native format.
# ---------------------------------------------------------------------------

@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict  # JSON Schema object {"type": "object", "properties": {...}}


# ---------------------------------------------------------------------------
# Inference request
# Single object passed to BaseProvider.infer() instead of loose arguments.
# ---------------------------------------------------------------------------

@dataclass
class InferRequest:
    messages: list[dict]
    model: str
    tools: list[ToolSchema] | None = None
    temperature: float = 0.7
    max_tokens: int | None = None


# ---------------------------------------------------------------------------
# Streaming events
# Every adapter yields a sequence of these. The stream ends with DoneEvent.
# ---------------------------------------------------------------------------

@dataclass
class TextDelta:
    """A chunk of generated text. content passes through unmodified (UTF-8, markdown, etc.)."""
    content: str


@dataclass
class ToolCallEvent:
    """A fully assembled tool call. arguments are already parsed from JSON."""
    name: str
    arguments: dict


@dataclass
class ErrorEvent:
    """A recoverable stream error. The adapter yields this instead of raising."""
    message: str


@dataclass
class DoneEvent:
    """Terminal event. Every adapter MUST yield this as the last event."""
    pass


# Union type used in type hints.
InferEvent = TextDelta | ToolCallEvent | ErrorEvent | DoneEvent


# ---------------------------------------------------------------------------
# Provider capabilities
# Each adapter declares these as a class-level property.
# The controller reads tool_format to decide how to deliver tools.
# ---------------------------------------------------------------------------

@dataclass
class ProviderCapabilities:
    tool_format: Literal["native", "xml", "anthropic_tool_use"]
    supports_streaming: bool = True
    supports_system_prompt: bool = True
```

- [ ] **Step 2: Commit**

```bash
git add src/services/providers/types.py
git commit -m "feat(providers): add typed protocol — InferRequest, InferEvent, ToolSchema, ProviderCapabilities"
```

---

## Task 2: Update `src/services/providers/base.py`

Replace the loose abstract interface with one that uses the new types.

**Files:**
- Modify: `src/services/providers/base.py`

- [ ] **Step 1: Replace the file content**

```python
# src/services/providers/base.py
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from .types import InferRequest, InferEvent, ProviderCapabilities


class BaseProvider(ABC):
    """
    Common interface for all inference adapters.

    Each adapter must:
    - Declare its capabilities via the `capabilities` property.
    - Implement `infer()` yielding InferEvent instances.
    - Always yield DoneEvent as the final event.
    - Yield ErrorEvent for recoverable stream errors; raise for unrecoverable ones.
    """

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @abstractmethod
    async def infer(
        self, request: InferRequest
    ) -> AsyncGenerator[InferEvent, None]: ...

    @abstractmethod
    async def list_models(self) -> list[str]: ...

    @abstractmethod
    async def check_health(self) -> bool: ...
```

- [ ] **Step 2: Commit**

```bash
git add src/services/providers/base.py
git commit -m "refactor(providers): BaseProvider adopts InferRequest/InferEvent interface"
```

---

## Task 3: Update stubs — `anthropic.py` and `gemini.py`

Both are unimplemented placeholders. Update them to satisfy the new `BaseProvider` signature. Functionality stays `NotImplementedError`.

**Files:**
- Modify: `src/services/providers/anthropic.py`
- Modify: `src/services/providers/gemini.py`

- [ ] **Step 1: Replace `anthropic.py`**

```python
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
```

- [ ] **Step 2: Replace `gemini.py`**

```python
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
```

- [ ] **Step 3: Commit**

```bash
git add src/services/providers/anthropic.py src/services/providers/gemini.py
git commit -m "refactor(providers): update Anthropic and Gemini stubs to new interface"
```

---

## Task 4: Fix `manager.py` bugs + update its tests

Two bugs to fix:
1. `p["name"]` should be `p["id"]` — JotaDB uses `id` as the identifier key (e.g. `"openai"`), and `default_provider_id` in the config also refers to the `id` field.
2. `_ADAPTER_MAP` keys must match what JotaDB actually sends: `"openai"` and `"local"`, not `"openai_compatible"`.

Also update `manager.py` to pass `base_url=p.get("base_url")` (which may be `None` for OpenAI) instead of `base_url=p.get("base_url", "")`.

**Files:**
- Modify: `src/services/providers/manager.py`
- Modify: `tests/unit/test_provider_manager.py`

- [ ] **Step 1: Update the test fixture to match real JotaDB structure**

Replace the entire `PROVIDERS_FIXTURE` in `tests/unit/test_provider_manager.py`. The `type` values now match what JotaDB sends (`"openai"`, `"local"`, `"anthropic"`). The adapter keys in assertions remain `p["id"]` values.

```python
# tests/unit/test_provider_manager.py
import pytest
from unittest.mock import AsyncMock, patch
from src.services.providers.manager import ProviderManager, ProviderNotFoundError


PROVIDERS_FIXTURE = [
    {
        "id": "prov-local",
        "name": "Local LLM",
        "type": "local",
        "base_url": "http://jota-inference:8002",
        "api_key": "local-key",
        "default_model_id": "llama-3.2-3b",
        "is_active": True,
    },
    {
        "id": "prov-openai",
        "name": "OpenAI",
        "type": "openai",
        "base_url": None,
        "api_key": "sk-abc",
        "default_model_id": "gpt-4o",
        "is_active": True,
    },
    {
        "id": "prov-anthropic",
        "name": "Anthropic",
        "type": "anthropic",
        "base_url": None,
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
        "name": "Unknown",
        "type": "unknown_provider",
        "base_url": None,
        "api_key": "",
        "default_model_id": "",
    }]
    pm = ProviderManager()
    await pm.init(providers_with_unknown, default_provider_id="prov-local")

    with pytest.raises(ProviderNotFoundError):
        pm.get_adapter("prov-unknown")
```

- [ ] **Step 2: Run the tests — they must FAIL now (before fixing manager.py)**

```bash
.venv/bin/pytest tests/unit/test_provider_manager.py -v
```

Expected: FAIL — `test_init_creates_adapters_by_type` fails because `_ADAPTER_MAP` doesn't have `"local"` or `"openai"`.

- [ ] **Step 3: Fix `manager.py`**

```python
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
```

- [ ] **Step 4: Run the tests — they must PASS**

```bash
.venv/bin/pytest tests/unit/test_provider_manager.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/providers/manager.py tests/unit/test_provider_manager.py
git commit -m "fix(providers): use p[\"id\"] as adapter key, fix _ADAPTER_MAP for JotaDB types"
```

---

## Task 5: Add `ToolManager.get_typed_tool_schemas()`

Adds a method that returns `list[ToolSchema]` — the canonical representation passed to adapters. The existing `get_tool_schemas()` (returns `list[dict]`) is preserved for backward compatibility.

**Files:**
- Modify: `src/core/tool_manager.py`
- (No new test file — add to existing tool_manager tests or add inline)

- [ ] **Step 1: Write the failing test**

Add this to a new file `tests/unit/test_tool_manager_typed.py`:

```python
# tests/unit/test_tool_manager_typed.py
import pytest
from src.core.tool_manager import ToolManager
from src.services.providers.types import ToolSchema


def test_get_typed_tool_schemas_returns_tool_schema_instances():
    tm = ToolManager()

    def search(query: str) -> str:
        """Search the web."""
        return ""

    tm.register(search)

    schemas = tm.get_typed_tool_schemas()

    assert len(schemas) == 1
    assert isinstance(schemas[0], ToolSchema)
    assert schemas[0].name == "search"
    assert schemas[0].description == "Search the web."
    assert schemas[0].parameters["type"] == "object"
    assert "query" in schemas[0].parameters["properties"]


def test_get_typed_tool_schemas_filters_by_client_role():
    from src.core.tool_manager import ROLE_ADMIN
    tm = ToolManager()

    def public_tool() -> str:
        """Public tool."""
        return ""

    def admin_tool() -> str:
        """Admin tool."""
        return ""

    tm.register(public_tool)
    tm.register(admin_tool, required_role=ROLE_ADMIN)

    # Client with no role (public) — only sees public_tool
    schemas = tm.get_typed_tool_schemas(client_id="guest")
    assert len(schemas) == 1
    assert schemas[0].name == "public_tool"


def test_get_typed_tool_schemas_empty_when_no_tools():
    tm = ToolManager()
    assert tm.get_typed_tool_schemas() == []
```

- [ ] **Step 2: Run — must FAIL**

```bash
.venv/bin/pytest tests/unit/test_tool_manager_typed.py -v
```

Expected: FAIL — `AttributeError: 'ToolManager' object has no attribute 'get_typed_tool_schemas'`

- [ ] **Step 3: Add the method to `ToolManager`**

In `src/core/tool_manager.py`, add `get_typed_tool_schemas` after the existing `get_tool_schemas` method (around line 130). Do not remove or change any existing method.

```python
def get_typed_tool_schemas(self, client_id: Any = None) -> list:
    """Returns accessible tools as ToolSchema dataclasses.

    For use by provider adapters — provides the canonical tool representation
    that each adapter converts to its native format.
    """
    from src.services.providers.types import ToolSchema
    return [
        ToolSchema(
            name=s["name"],
            description=s["description"],
            parameters=s["parameters"],
        )
        for s in self.get_tool_schemas(client_id)
    ]
```

Place it directly after `get_tool_schemas` ends (before `execute_tool`).

- [ ] **Step 4: Run — must PASS**

```bash
.venv/bin/pytest tests/unit/test_tool_manager_typed.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/tool_manager.py tests/unit/test_tool_manager_typed.py
git commit -m "feat(tools): add get_typed_tool_schemas() returning list[ToolSchema]"
```

---

## Task 6: Rewrite `OpenAICompatibleAdapter` with native function calling

Replace the entire XML detection implementation with OpenAI's structured delta API. Tool calls come from `delta.tool_calls` fields, not from pattern matching in text.

**Files:**
- Modify: `src/services/providers/openai_compatible.py`
- Modify: `tests/unit/test_openai_adapter.py`

- [ ] **Step 1: Write the new tests first**

Replace the entire content of `tests/unit/test_openai_adapter.py`:

```python
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
```

- [ ] **Step 2: Run — must FAIL**

```bash
.venv/bin/pytest tests/unit/test_openai_adapter.py -v
```

Expected: multiple FAILs — `test_capabilities_tool_format_is_native`, `test_infer_yields_text_delta_events`, `test_infer_yields_tool_call_event_from_structured_delta`, etc.

- [ ] **Step 3: Replace `openai_compatible.py`**

```python
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
```

- [ ] **Step 4: Run — must PASS**

```bash
.venv/bin/pytest tests/unit/test_openai_adapter.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/providers/openai_compatible.py tests/unit/test_openai_adapter.py
git commit -m "feat(providers): OpenAICompatibleAdapter — native function calling, typed InferEvent stream"
```

---

## Task 7: Update `conftest.py` + rewrite `controller/input.py` + add controller tests

The controller is the core integration point. It reads `adapter.capabilities.tool_format`, builds `InferRequest`, and consumes `InferEvent` types. The conftest fixtures must also be updated so they yield `InferEvent` instead of raw strings.

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/unit/test_controller_input.py`
- Modify: `src/core/controller/input.py`

- [ ] **Step 1: Update `tests/conftest.py`**

Replace the entire file:

```python
# tests/conftest.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_memory_manager():
    m = AsyncMock()
    m.save_message = AsyncMock()
    m.mark_conversation_error = AsyncMock()
    m.get_conversation_messages = AsyncMock(return_value=[])
    m.get_conversation = AsyncMock(return_value=None)
    m.get_client_config = AsyncMock(return_value=None)
    m.get_orchestrator_config = AsyncMock(return_value={
        "default_provider_id": "prov-test",
        "system_prompt": "Eres Jota.",
        "tool_followup_prompt": "Responde usando los resultados.",
    })
    m.get_providers = AsyncMock(return_value=[])
    return m


@pytest.fixture
def mock_provider():
    """A mock BaseProvider that yields TextDelta + DoneEvent."""
    from src.services.providers.types import TextDelta, DoneEvent, ProviderCapabilities

    async def _infer(request):
        yield TextDelta(content="Hello world")
        yield DoneEvent()

    p = MagicMock()
    p.infer = _infer
    p.capabilities = ProviderCapabilities(tool_format="native")
    p.check_health = AsyncMock(return_value=True)
    return p


@pytest.fixture
def mock_provider_manager(mock_provider):
    pm = MagicMock()
    pm.get_adapter = MagicMock(return_value=mock_provider)
    pm.get_default = MagicMock(return_value=("prov-test", "model-test"))
    pm.check_health = AsyncMock(return_value={"prov-test": True})
    return pm


@pytest.fixture
def mock_config_manager():
    from src.core.config_manager import OrchestratorConfig
    cm = MagicMock()
    cm.config = OrchestratorConfig(
        default_provider_id="prov-test",
        system_prompt="Eres Jota.",
        tool_followup_prompt="Responde usando los resultados.",
    )
    return cm
```

- [ ] **Step 2: Write the controller tests**

Create `tests/unit/test_controller_input.py`:

```python
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

    async def _infer(request):
        yield TextDelta(content="ok")
        yield DoneEvent()

    xml_provider.infer = _infer
    xml_provider.capabilities = ProviderCapabilities(tool_format="xml")
    mock_provider_manager.get_adapter = MagicMock(return_value=xml_provider)

    controller = _make_controller(mock_memory_manager, mock_provider_manager, mock_config_manager)

    captured_request = None

    async def capturing_infer(request):
        nonlocal captured_request
        captured_request = request
        yield TextDelta(content="ok")
        yield DoneEvent()

    xml_provider.infer = capturing_infer

    tool = ToolSchema(name="search", description="Search", parameters={"type": "object", "properties": {}})

    with patch("src.core.controller.input.tool_manager") as mock_tm:
        mock_tm.get_typed_tool_schemas.return_value = [tool]
        mock_tm.get_system_prompt_addition.return_value = "USE TOOLS LIKE THIS: <tool_call>"
        _ = [t async for t in controller.handle_input(_base_payload())]

    # XML provider: tools must NOT be in InferRequest, XML instructions in system prompt
    assert captured_request.tools is None
    assert "USE TOOLS LIKE THIS" in captured_request.messages[0]["content"]
```

- [ ] **Step 3: Run — must FAIL**

```bash
.venv/bin/pytest tests/unit/test_controller_input.py -v
```

Expected: FAIL — the controller still uses the old `adapter.infer(messages, model, params)` signature.

- [ ] **Step 4: Replace `src/core/controller/input.py`**

```python
"""
Input handling logic for the Orchestrator Controller.

Builds the messages array, resolves provider, streams inference tokens,
handles tool calls and DB persistence.
"""
import logging
import json as _json
import time as _time
from typing import AsyncGenerator, TYPE_CHECKING

from src.services.providers.types import (
    InferRequest, TextDelta, ToolCallEvent, ErrorEvent, DoneEvent,
)

if TYPE_CHECKING:
    from src.core.memory import MemoryManager
    from src.core.config_manager import ConfigManager
    from src.services.providers import ProviderManager

logger = logging.getLogger(__name__)


class JotaInputMixin:

    async def handle_input(self, payload: dict) -> AsyncGenerator[str | dict, None]:
        """
        Main inference flow:
          1. Resolve provider + model for this conversation.
          2. Build messages array (system + history + user).
          3. Build InferRequest — tools delivered natively or via XML in system prompt,
             depending on adapter.capabilities.tool_format.
          4. Stream events from provider adapter.
          5. Handle tool calls: execute, save, re-infer.
          6. Persist assistant response to DB.
        """
        content = payload.get("content")
        conversation_id = payload.get("conversation_id")
        client_id = payload.get("client_id")
        stateless = payload.get("stateless", False)
        system_prompt_override = payload.get("system_prompt_override")

        if not conversation_id or not client_id:
            logger.error("Missing conversation_id or client_id in payload")
            yield " [Error: Internal Context Missing]"
            return

        logger.info(f"Controller processing input for conversation {conversation_id}")

        try:
            # 1. Resolve provider + model
            provider_id, model_id = await self._resolve_provider(
                conversation_id, client_id, stateless
            )
            adapter = self.provider_manager.get_adapter(provider_id)

            # 2. Resolve tools
            from src.core.tool_manager import tool_manager
            tools = tool_manager.get_typed_tool_schemas(client_id=client_id)

            # 3. Build system prompt
            base_prompt = system_prompt_override or self.config_manager.config.system_prompt
            system_prompt = base_prompt
            # XML providers receive tool instructions in the system prompt instead of as API params
            if adapter.capabilities.tool_format == "xml" and tools:
                system_prompt += "\n\n" + tool_manager.get_system_prompt_addition(client_id=client_id)

            # 4. Build messages array
            messages = [{"role": "system", "content": system_prompt}]
            if not stateless:
                history = await self.memory_manager.get_conversation_messages(
                    conversation_id, client_id
                )
                messages.extend(history)
            messages.append({"role": "user", "content": content})

            # 5. Build InferRequest
            request = InferRequest(
                messages=messages,
                model=model_id,
                # Native providers receive tools as API params; XML providers receive None here
                tools=tools if adapter.capabilities.tool_format == "native" else None,
                temperature=0.7,
            )

            # 6. First inference pass
            tool_executed = False
            pre_tool_thinking: list[str] = []
            response_buffer: list[str] = []

            async for event in adapter.infer(request):
                if isinstance(event, ToolCallEvent):
                    tool_name = event.name
                    tool_args = event.arguments

                    # Save pre-tool thinking to DB (not streamed to user)
                    if pre_tool_thinking and not stateless:
                        thinking_text = "".join(pre_tool_thinking)
                        await self.memory_manager.save_message(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=thinking_text,
                            client_id=client_id,
                            metadata={"model_id": model_id, "thinking": True},
                        )
                    pre_tool_thinking.clear()
                    response_buffer.clear()

                    yield {"type": "status", "content": f"Buscando información usando {tool_name}..."}

                    try:
                        start_t = _time.time()
                        result = await tool_manager.execute_tool(
                            tool_name, client_id=client_id, **tool_args
                        )
                        duration = f"{_time.time() - start_t:.2f}s"
                        result_str = result if isinstance(result, str) else _json.dumps(result)

                        if not stateless:
                            await self.memory_manager.save_message(
                                conversation_id=conversation_id,
                                role="tool",
                                content=result_str,
                                client_id=client_id,
                                metadata={"tool_name": tool_name, "execution_time": duration},
                            )
                        yield {"type": "status", "content": f"Búsqueda completada en {duration}. Generando respuesta..."}
                        tool_executed = True
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        if not stateless:
                            await self.memory_manager.save_message(
                                conversation_id=conversation_id,
                                role="tool",
                                content=f"Error executing tool {tool_name}: {e}",
                                client_id=client_id,
                                metadata={"tool_name": tool_name, "error": True},
                            )
                        yield {"type": "status", "content": f"Error al ejecutar {tool_name}: {e}"}
                        tool_executed = True

                elif isinstance(event, TextDelta):
                    if not tool_executed:
                        pre_tool_thinking.append(event.content)
                        response_buffer.append(event.content)

                elif isinstance(event, ErrorEvent):
                    logger.error(f"Provider error during first pass: {event.message}")
                    yield f" [Error: {event.message}]"
                    return

                elif isinstance(event, DoneEvent):
                    break

            # No tool call — flush buffered text to client and save
            if not tool_executed:
                for chunk in pre_tool_thinking:
                    yield chunk
                if not stateless and response_buffer:
                    full_text = "".join(response_buffer)
                    await self.memory_manager.save_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=full_text,
                        client_id=client_id,
                        metadata={"model_id": model_id},
                    )
                return

            # 7. Re-inference after tool execution
            yield {"type": "status", "content": "Analizando resultados..."}

            followup_messages = [{"role": "system", "content": system_prompt}]
            if not stateless:
                updated_history = await self.memory_manager.get_conversation_messages(
                    conversation_id, client_id
                )
                followup_messages.extend(updated_history)
            followup_messages.append({
                "role": "user",
                "content": self.config_manager.config.tool_followup_prompt,
            })

            followup_request = InferRequest(
                messages=followup_messages,
                model=model_id,
                tools=tools if adapter.capabilities.tool_format == "native" else None,
                temperature=0.7,
            )

            final_buffer: list[str] = []
            async for event in adapter.infer(followup_request):
                if isinstance(event, ToolCallEvent):
                    logger.warning("Nested tool call attempted — ignoring.")
                elif isinstance(event, TextDelta):
                    final_buffer.append(event.content)
                    yield event.content
                elif isinstance(event, ErrorEvent):
                    logger.error(f"Provider error during re-inference: {event.message}")
                    yield f" [Error: {event.message}]"
                    return
                elif isinstance(event, DoneEvent):
                    break

            if not stateless and final_buffer:
                await self.memory_manager.save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content="".join(final_buffer),
                    client_id=client_id,
                    metadata={"model_id": model_id},
                )

            logger.info("Inference stream complete.")

        except Exception as e:
            logger.error(f"Error during inference flow: {e}")
            await self.memory_manager.mark_conversation_error(conversation_id, client_id)
            yield f" [Error: {str(e)}]"

    async def _resolve_provider(
        self,
        conversation_id: str,
        client_id,
        stateless: bool,
    ) -> tuple[str, str]:
        """
        Resolves (provider_id, model_id) with this priority:
          1. conversation.provider_id + conversation.model_id  (DB, highest priority)
          2. client_config.preferred_model_id + default provider
          3. Global default provider + default model
        """
        # 1. Conversation-level provider
        if not stateless:
            conv = await self.memory_manager.get_conversation(conversation_id, client_id)
            if conv and conv.get("provider_id") and conv.get("model_id"):
                return conv["provider_id"], conv["model_id"]

        # 2. Client preferred model
        client_config = await self.memory_manager.get_client_config(str(client_id))
        default_provider_id, default_model_id = self.provider_manager.get_default()
        if client_config and client_config.get("preferred_model_id"):
            return default_provider_id, client_config["preferred_model_id"]

        # 3. Global default
        return default_provider_id, default_model_id
```

- [ ] **Step 5: Run — must PASS**

```bash
.venv/bin/pytest tests/unit/test_controller_input.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/unit/test_controller_input.py src/core/controller/input.py
git commit -m "refactor(controller): consume InferEvent types, capabilities-aware tool injection"
```

---

## Task 8: Update `quick.py` + `test_quick_system_prompt.py`

The quick endpoint also calls `adapter.infer()` directly. Update it to use `InferRequest` and consume `InferEvent` types.

**Files:**
- Modify: `src/api/quick.py`
- Modify: `tests/unit/test_quick_system_prompt.py`

- [ ] **Step 1: Update `test_quick_system_prompt.py`**

The test's `_make_adapter` currently yields raw strings and calls `infer(messages, model, params)`. Update it to yield `TextDelta`/`DoneEvent` and accept `InferRequest`. The assertions change from `call_args[0][0]` (the messages list) to `call_args[0][0].messages` (the `InferRequest` object).

```python
# tests/unit/test_quick_system_prompt.py
"""Tests: _quick_stream_generator builds system prompt correctly."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.quick import _quick_stream_generator, QUICK_SYSTEM_PROMPT_PREFIX, QuickRequest
from src.services.providers.types import TextDelta, DoneEvent, ProviderCapabilities


async def _collect(gen) -> list[dict]:
    results = []
    async for line in gen:
        line = line.strip()
        if line:
            results.append(json.loads(line))
    return results


def _make_adapter(tokens=("hola",)):
    adapter = MagicMock()

    async def fake_infer(request):
        for t in tokens:
            yield TextDelta(content=t)
        yield DoneEvent()

    adapter.infer = MagicMock(side_effect=fake_infer)
    adapter.capabilities = ProviderCapabilities(tool_format="native")
    return adapter


@pytest.fixture
def mock_config():
    with patch("src.api.quick.config_manager") as mock:
        mock.config.system_prompt = "Eres Jota."
        mock.config.tool_followup_prompt = "Usa los resultados."
        yield mock


@pytest.fixture
def mock_tools():
    with patch("src.api.quick.tool_manager") as mock:
        mock.get_typed_tool_schemas.return_value = []
        mock.get_system_prompt_addition.return_value = None
        yield mock


@pytest.mark.asyncio
async def test_system_prompt_extra_appended_when_provided(mock_config, mock_tools):
    adapter = _make_adapter()
    request = QuickRequest(text="hola", system_prompt_extra="responde siempre en inglés")

    await _collect(_quick_stream_generator(adapter, "cid", "model-x", request))

    call_args = adapter.infer.call_args
    infer_request = call_args[0][0]
    system_content = infer_request.messages[0]["content"]
    assert "responde siempre en inglés" in system_content


@pytest.mark.asyncio
async def test_system_prompt_extra_not_present_when_none(mock_config, mock_tools):
    adapter = _make_adapter()
    request = QuickRequest(text="hola", system_prompt_extra=None)

    await _collect(_quick_stream_generator(adapter, "cid", "model-x", request))

    call_args = adapter.infer.call_args
    infer_request = call_args[0][0]
    system_content = infer_request.messages[0]["content"]
    assert QUICK_SYSTEM_PROMPT_PREFIX.strip() in system_content
    assert "responde siempre en inglés" not in system_content


@pytest.mark.asyncio
async def test_system_prompt_extra_empty_string_ignored(mock_config, mock_tools):
    adapter = _make_adapter()
    request = QuickRequest(text="hola", system_prompt_extra="")

    await _collect(_quick_stream_generator(adapter, "cid", "model-x", request))

    call_args = adapter.infer.call_args
    infer_request = call_args[0][0]
    system_content = infer_request.messages[0]["content"]
    assert QUICK_SYSTEM_PROMPT_PREFIX.strip() in system_content
```

- [ ] **Step 2: Run — must FAIL**

```bash
.venv/bin/pytest tests/unit/test_quick_system_prompt.py -v
```

Expected: FAIL — `_quick_stream_generator` still uses the old interface.

- [ ] **Step 3: Replace `src/api/quick.py`**

```python
# src/api/quick.py
"""
quick.py — Endpoint REST para clientes QUICK: comandos rápidos, stateless.
"""
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import logging
import json
import time

from src.core.services import memory_manager, provider_manager, config_manager
from src.core.tool_manager import tool_manager
from src.services.providers.types import (
    InferRequest, TextDelta, ToolCallEvent, ErrorEvent, DoneEvent,
)

logger = logging.getLogger(__name__)
router = APIRouter()

QUICK_SYSTEM_PROMPT_PREFIX = """REGLAS DE RESPUESTA (obligatorias):
1. Responde siempre en 1-2 frases MÁXIMO. Sin introducción, sin contexto extra.
2. PROHIBIDO usar markdown: ningún **, *, _, #, ni listas con guiones. El texto se dicta por voz.
3. Habla de forma directa y afirmativa. Omite fórmulas de cortesía innecesarias.

USO DE HERRAMIENTAS:
- Si necesitas buscar información, emite el bloque <tool_call> de forma INMEDIATA, sin ningún texto previo.
- Tras recibir el resultado de la herramienta, resume lo relevante en MÁXIMO 2 frases.
- No menciones que usaste una herramienta ni el proceso interno.
"""


class QuickRequest(BaseModel):
    text: str
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    system_prompt_extra: Optional[str] = None


async def _quick_stream_generator(
    adapter,
    client_id: str,
    model_id: str,
    request: QuickRequest,
) -> AsyncGenerator[str, None]:
    log_prefix = f"[QUICK][Client: {client_id}]"

    # Resolve tools
    tools = tool_manager.get_typed_tool_schemas(client_id=client_id)

    # Build system prompt
    base_prompt = config_manager.config.system_prompt
    full_prompt = f"{base_prompt}\n\n{QUICK_SYSTEM_PROMPT_PREFIX}"
    if adapter.capabilities.tool_format == "xml" and tools:
        tool_instructions = tool_manager.get_system_prompt_addition(client_id=client_id)
        if tool_instructions:
            full_prompt += f"\n{tool_instructions}"
    if request.system_prompt_extra:
        full_prompt += f"\n{request.system_prompt_extra}"

    messages = [
        {"role": "system", "content": full_prompt},
        {"role": "user", "content": request.text},
    ]

    infer_request = InferRequest(
        messages=messages,
        model=model_id,
        tools=tools if adapter.capabilities.tool_format == "native" else None,
        temperature=0.3,
        max_tokens=150,
    )

    tool_executed = False
    tool_context: list[dict] = []

    try:
        async for event in adapter.infer(infer_request):
            if isinstance(event, ToolCallEvent):
                tool_name = event.name
                tool_args = event.arguments

                logger.info(f"{log_prefix} Tool call: {tool_name}")
                yield json.dumps({"type": "status", "content": f"Buscando información usando {tool_name}..."}) + "\n"

                try:
                    start_t = time.time()
                    result = await tool_manager.execute_tool(tool_name, client_id=client_id, **tool_args)
                    duration = f"{time.time() - start_t:.2f}s"
                    result_str = result if isinstance(result, str) else json.dumps(result)

                    tool_context = [
                        {"role": "user", "content": request.text},
                        {"role": "assistant", "content": json.dumps({"name": tool_name, "arguments": tool_args})},
                        {"role": "tool", "content": result_str},
                    ]
                    yield json.dumps({"type": "status", "content": f"Búsqueda completada en {duration}. Generando respuesta..."}) + "\n"
                    tool_executed = True
                except Exception as e:
                    logger.error(f"{log_prefix} Tool {tool_name} failed: {e}")
                    yield json.dumps({"type": "status", "content": f"Error al usar {tool_name}: {e}"}) + "\n"
                    tool_executed = True

            elif isinstance(event, TextDelta):
                if not tool_executed:
                    yield json.dumps({"type": "token", "content": event.content}) + "\n"

            elif isinstance(event, ErrorEvent):
                yield json.dumps({"type": "error", "content": event.message}) + "\n"
                return

            elif isinstance(event, DoneEvent):
                break

        if tool_executed:
            yield json.dumps({"type": "status", "content": "Analizando resultados..."}) + "\n"
            followup_messages = (
                [{"role": "system", "content": full_prompt}]
                + tool_context
                + [{"role": "user", "content": config_manager.config.tool_followup_prompt}]
            )
            followup_request = InferRequest(
                messages=followup_messages,
                model=model_id,
                tools=tools if adapter.capabilities.tool_format == "native" else None,
                temperature=0.3,
                max_tokens=100,
            )
            async for event in adapter.infer(followup_request):
                if isinstance(event, TextDelta):
                    yield json.dumps({"type": "token", "content": event.content}) + "\n"
                elif isinstance(event, DoneEvent):
                    break

    except Exception as e:
        logger.error(f"{log_prefix} Error: {e}")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"


@router.post("/quick")
async def quick_endpoint(
    request: QuickRequest,
    x_client_key: str = Header(..., description="Client authentication key"),
):
    """
    Endpoint NDJSON stream para comandos rápidos y voz.
    Stateless — no guarda mensajes. Optimizado para TTS.
    """
    client_data = await memory_manager.validate_client_key(x_client_key)
    if not client_data:
        raise HTTPException(status_code=401, detail="Unauthorized")

    client_type = client_data.get("client_type", "CHAT")
    if client_type != "QUICK":
        raise HTTPException(
            status_code=403,
            detail=f"Client type '{client_type}' not allowed on /quick endpoint.",
        )

    client_id = client_data["id"]

    # Resolve provider + model
    client_config = await memory_manager.get_client_config(str(client_id))
    default_provider_id, default_model_id = provider_manager.get_default()

    provider_id = request.provider_id or default_provider_id
    model_id = (
        request.model_id
        or (client_config or {}).get("preferred_model_id")
        or default_model_id
    )
    adapter = provider_manager.get_adapter(provider_id)

    return StreamingResponse(
        _quick_stream_generator(adapter, client_id, model_id, request),
        media_type="application/x-ndjson",
    )
```

- [ ] **Step 4: Run — must PASS**

```bash
.venv/bin/pytest tests/unit/test_quick_system_prompt.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/quick.py tests/unit/test_quick_system_prompt.py
git commit -m "refactor(quick): adopt InferRequest/InferEvent interface, capabilities-aware tool delivery"
```

---

## Task 9: Full test suite

Run all unit and integration tests to confirm nothing is broken.

**Files:** none

- [ ] **Step 1: Run full test suite**

```bash
.venv/bin/pytest tests/unit/ tests/integration/ -v
```

Expected: all tests PASS. If any fail, read the error before changing anything — the most likely cause is a test file that still mocks `adapter.infer` with the old signature.

- [ ] **Step 2: Commit if there were any fixes**

Only if Step 1 required small fixes:

```bash
git add <files>
git commit -m "fix(tests): update remaining mocks to InferRequest/InferEvent interface"
```
