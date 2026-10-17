# src/services/providers/types.py
from dataclasses import dataclass
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Tool canonical representation
# Passed from ToolManager to adapters. Each adapter converts to its native format.
# ---------------------------------------------------------------------------

@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object {"type": "object", "properties": {...}}


# ---------------------------------------------------------------------------
# Inference request
# Single object passed to BaseProvider.infer() instead of loose arguments.
# ---------------------------------------------------------------------------

@dataclass
class InferRequest:
    messages: list[dict[str, Any]]
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

@dataclass(frozen=True)
class ProviderCapabilities:
    tool_format: Literal["native", "xml", "anthropic_tool_use"]
    supports_streaming: bool = True
    supports_system_prompt: bool = True
