import json
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

from src.core.constants import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
from .base import BaseProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter(BaseProvider):
    """
    Adapter para cualquier provider con API compatible con OpenAI
    (jota-inference local, OpenAI, Ollama, Groq, Mistral, etc.).

    Tool calls se detectan como XML (<tool_call>...</tool_call>) en el
    stream de texto, de la misma forma que el sistema actual.
    """

    def __init__(self, base_url: str, api_key: str):
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key or "not-needed")

    async def infer(
        self,
        messages: list[dict],
        model: str,
        params: dict | None = None,
    ) -> AsyncGenerator[str | dict, None]:
        params = params or {}
        kwargs = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": params.get("temp", 0.7),
        }
        if "max_tokens" in params:
            kwargs["max_tokens"] = params["max_tokens"]

        response_buffer: list[str] = []
        yielded_len = 0

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta or not delta.content:
                continue

            response_buffer.append(delta.content)
            full_text = "".join(response_buffer)

            if TOOL_CALL_OPEN in full_text:
                start_idx = full_text.find(TOOL_CALL_OPEN)
                # Yield text before tool call
                if start_idx > yielded_len:
                    chunk_text = full_text[yielded_len:start_idx]
                    yielded_len += len(chunk_text)
                    yield chunk_text

                # Check if tool call is closed
                if TOOL_CALL_CLOSE in full_text[start_idx:]:
                    end_idx = full_text.find(TOOL_CALL_CLOSE, start_idx) + len(TOOL_CALL_CLOSE)
                    if end_idx > yielded_len:
                        yielded_len = end_idx
                        raw_json = full_text[start_idx + len(TOOL_CALL_OPEN):end_idx - len(TOOL_CALL_CLOSE)].strip()
                        try:
                            tool_data = json.loads(raw_json)
                            yield {"type": "tool_call", "payload": tool_data}
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse tool call JSON: {e}")
            else:
                # No tool call in buffer — yield safe portion
                safe_text = full_text
                last_lt = full_text.rfind("<")
                if last_lt != -1 and last_lt >= len(full_text) - len(TOOL_CALL_OPEN):
                    if TOOL_CALL_OPEN.startswith(full_text[last_lt:]):
                        safe_text = full_text[:last_lt]

                if len(safe_text) > yielded_len:
                    chunk_text = safe_text[yielded_len:]
                    yielded_len += len(chunk_text)
                    yield chunk_text

        # Yield any remaining text
        full_text = "".join(response_buffer)
        if len(full_text) > yielded_len:
            yield full_text[yielded_len:]

    async def list_models(self) -> list[str]:
        models = await self._client.models.list()
        return [m.id for m in models.data]

    async def check_health(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False