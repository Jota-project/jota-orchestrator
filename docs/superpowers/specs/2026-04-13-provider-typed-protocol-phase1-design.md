# Provider Typed Protocol — Phase 1 Design

**Date:** 2026-04-13
**Branch:** `feat/multiprovider-openai`
**Phase 2 tracking:** [Jota-project/jota-orchestrator#23](https://github.com/Jota-project/jota-orchestrator/issues/23)

---

## Context

JotaOrchestrator has a `ProviderManager` that routes inference requests to typed adapters loaded from JotaDB. The current implementation has several problems:

1. **Type recognition bug**: `_ADAPTER_MAP` uses `"openai_compatible"` but JotaDB sends `"openai"` and `"local"`.
2. **ID bug**: `manager.py` uses `p["name"]` (human-readable) as the adapter key, but `default_provider_id` from JotaDB uses `p["id"]` (e.g. `"openai"`).
3. **Weak streaming contract**: `BaseProvider.infer()` returns `AsyncGenerator[str | dict, None]` — untyped, requires `isinstance` + dict key checks in the controller.
4. **Tool format coupling**: The controller hardcodes XML tool injection into the system prompt, with no awareness of provider capabilities. Real OpenAI API supports native function calling.
5. **Loose infer() signature**: `infer(messages, model, params)` — raw dicts, no validation, fragile to extend.

This spec defines Phase 1: a full typed protocol that fixes all of the above while setting clean extension points for Phase 2 (provider registry, resolution service, error hierarchy).

---

## Goals

- Fix the immediate bugs (type map, ID field).
- Replace `str | dict` streaming with typed `InferEvent` union.
- Replace the loose `infer()` signature with an `InferRequest` dataclass.
- Introduce `ToolSchema` as the canonical tool representation passed from `ToolManager` to adapters.
- Declare per-adapter capabilities so the controller is provider-agnostic.
- Implement OpenAI native function calling in `OpenAICompatibleAdapter`.
- Leave the controller clean: no format-specific logic, no `isinstance(token, dict)` checks.

---

## Non-Goals (deferred to Phase 2)

- `ProviderRegistry` with factory registration pattern.
- `ProviderResolutionService` extracted from the controller.
- Typed error hierarchy (`ProviderRateLimitError`, etc.).
- Model catalog per provider sourced from JotaDB.

---

## Architecture

### New file: `src/services/providers/types.py`

All shared data types live here. Imported by adapters, the controller, and `ToolManager`.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


# --- Tool canonical representation ---

@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict  # JSON Schema object


# --- Inference request ---

@dataclass
class InferRequest:
    messages: list[dict]
    model: str
    tools: list[ToolSchema] | None = None
    temperature: float = 0.7
    max_tokens: int | None = None


# --- Streaming events ---

@dataclass
class TextDelta:
    content: str

@dataclass
class ToolCallEvent:
    name: str
    arguments: dict

@dataclass
class ErrorEvent:
    message: str

@dataclass
class DoneEvent:
    pass

InferEvent = TextDelta | ToolCallEvent | ErrorEvent | DoneEvent


# --- Provider capabilities ---

@dataclass
class ProviderCapabilities:
    tool_format: Literal["native", "xml", "anthropic_tool_use"]
    supports_streaming: bool = True
    supports_system_prompt: bool = True
```

**Notes on InferEvent:**
- `TextDelta.content` is a raw Python string — UTF-8, markdown, special characters all pass through unmodified.
- `ToolCallEvent` carries the already-parsed tool name and arguments, not raw JSON.
- `ErrorEvent` is yielded by the adapter on recoverable stream errors; unrecoverable errors raise exceptions.
- `DoneEvent` is the terminal event — adapters yield it when the stream is complete.

---

### Modified: `src/services/providers/base.py`

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from .types import InferRequest, InferEvent, ProviderCapabilities


class BaseProvider(ABC):

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

---

### Modified: `src/services/providers/manager.py`

**Bug fixes:**
- `p["id"]` replaces `p["name"]` as the adapter key (matches `default_provider_id` from JotaDB).
- `_ADAPTER_MAP` updated to match actual JotaDB `type` values.

```python
_ADAPTER_MAP = {
    "openai": OpenAICompatibleAdapter,
    "local": OpenAICompatibleAdapter,   # placeholder — local uses XML until jota-inference exposes HTTP API
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
}
```

The `"local"` adapter will declare `tool_format="xml"` so the controller falls back to XML injection even though it's mapped to `OpenAICompatibleAdapter`. When jota-inference exposes an HTTP OpenAI-compatible API, a dedicated `LocalAdapter` will be introduced.

---

### Modified: `src/services/providers/openai_compatible.py`

Implements native function calling. Tool schemas are converted internally from `ToolSchema` to OpenAI's `{"type": "function", "function": {...}}` format.

Key changes:
- `capabilities` property returns `ProviderCapabilities(tool_format="native")`.
- `infer(request: InferRequest)` replaces the old signature.
- If `request.tools` is set: passes `tools` + `tool_choice="auto"` to the OpenAI API.
- Tool call events are parsed from `delta.tool_calls` (structured fields), not from XML pattern matching in text.
- Text content passes through as `TextDelta(content=chunk)` — no transformation.
- Stream ends with `yield DoneEvent()`.

**Private helper:**
```python
def _to_openai_tool(self, tool: ToolSchema) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
    }
```

---

### Modified: `src/core/tool_manager.py`

Add `get_typed_tool_schemas(client_id) -> list[ToolSchema]` alongside the existing `get_tool_schemas()`.

The existing `get_tool_schemas()` method is preserved for backward compatibility (used by `get_system_prompt_addition()`). The new method returns `list[ToolSchema]` — the canonical representation passed to adapters.

```python
def get_typed_tool_schemas(self, client_id: Any = None) -> list[ToolSchema]:
    """Returns accessible tools as ToolSchema dataclasses (for provider adapters)."""
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

---

### Modified: `src/core/controller/input.py`

The controller becomes provider-agnostic. It reads the adapter's `capabilities.tool_format` to decide how to handle tools:

```python
adapter = self.provider_manager.get_adapter(provider_id)
tools = tool_manager.get_typed_tool_schemas(client_id=client_id)

# Build system prompt — inject XML instructions only for XML-format providers
system_prompt = system_prompt_override or self.config_manager.config.system_prompt
if adapter.capabilities.tool_format == "xml" and tools:
    system_prompt += "\n\n" + tool_manager.get_system_prompt_addition(client_id=client_id)

request = InferRequest(
    messages=messages,
    model=model_id,
    tools=tools if adapter.capabilities.tool_format == "native" else None,
    temperature=0.7,
)

async for event in adapter.infer(request):
    if isinstance(event, TextDelta):
        yield event.content
    elif isinstance(event, ToolCallEvent):
        # handle tool execution
        ...
    elif isinstance(event, ErrorEvent):
        logger.error(f"Provider error: {event.message}")
        yield f" [Error: {event.message}]"
    elif isinstance(event, DoneEvent):
        break
```

No more `isinstance(token, dict) and token.get("type") == "tool_call"`. The type checker can verify all branches are handled.

---

### Stubs: `anthropic.py` and `gemini.py`

Updated to implement the new `BaseProvider` signature. Both remain unimplemented (`raise NotImplementedError`) but are now type-correct placeholders.

---

## File Structure Summary

```
src/services/providers/
├── types.py                  NEW  — InferRequest, InferEvent union, ToolSchema, ProviderCapabilities
├── base.py                   MOD  — BaseProvider uses new types
├── openai_compatible.py      MOD  — native function calling, _to_openai_tool(), capabilities property
├── anthropic.py              MOD  — updated stub with new signature
├── gemini.py                 MOD  — updated stub with new signature
└── manager.py                MOD  — _ADAPTER_MAP fixed, p["id"] fix

src/core/
├── tool_manager.py           MOD  — adds get_typed_tool_schemas()
└── controller/input.py       MOD  — capabilities-aware, consumes InferEvent
```

---

## Invariants

The following **do not change** in Phase 1:

- `ProviderManager.init()`, `get_adapter()`, `get_default()` — interfaces unchanged.
- `ToolManager.get_tool_schemas()`, `get_system_prompt_addition()` — preserved.
- Startup sequence in `src/main.py` and `src/core/services.py` — unchanged.
- WebSocket and quick endpoint handlers — unchanged (they call `handle_input()` which is the boundary).
- `_resolve_provider()` logic — unchanged. (Extracted to `ProviderResolutionService` in Phase 2.)

---

## Testing

Each new unit has clear, isolated behavior:

- `types.py` — no tests needed (pure dataclasses).
- `OpenAICompatibleAdapter` — mock `AsyncOpenAI`, test that `ToolSchema` list is correctly converted to OpenAI format and that `ToolCallEvent` is yielded from structured delta fields.
- `ToolManager.get_typed_tool_schemas()` — unit test: registered tools → correct `ToolSchema` list.
- Controller — mock adapter yielding each `InferEvent` type, verify controller response for each branch.

---

## Phase 2 Reference

See [Jota-project/jota-orchestrator#23](https://github.com/Jota-project/jota-orchestrator/issues/23) for the next iteration:
- `ProviderRegistry` with factory registration
- `ProviderResolutionService` extracted from controller
- Typed error hierarchy
- Model catalog per provider
