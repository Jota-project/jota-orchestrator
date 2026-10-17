# Multi-Provider OpenAI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el `InferenceClient` WebSocket monolítico por un sistema de providers multi-backend donde JotaDB es la única fuente de verdad de configuración, y todos los providers hablan OpenAI API estándar.

**Architecture:** Un `ProviderManager` carga adapters desde la DB en startup bloqueante. Cada adapter implementa `BaseProvider.infer(messages[], model, params)`. El controller construye el array de mensajes y delega al adapter correcto según la conversación. Las tool calls se detectan vía XML en el stream de texto (sin cambios en ese mecanismo).

**Tech Stack:** `openai` Python SDK (con `base_url` dinámico), `httpx`, FastAPI, pytest + AsyncMock.

---

## File Map

### Archivos nuevos
- `src/core/config_manager.py` — carga y cachea config del orchestrator desde DB
- `src/services/providers/__init__.py`
- `src/services/providers/base.py` — ABC `BaseProvider`
- `src/services/providers/openai_compatible.py` — adapter real (openai SDK)
- `src/services/providers/anthropic.py` — mock (`NotImplementedError`)
- `src/services/providers/gemini.py` — mock (`NotImplementedError`)
- `src/services/providers/manager.py` — `ProviderManager` + `ProviderNotFoundError`
- `tests/unit/test_config_manager.py`
- `tests/unit/test_provider_manager.py`
- `tests/unit/test_openai_adapter.py`

### Archivos modificados significativamente
- `requirements.txt` — `openai` in, `websockets` out
- `src/core/config.py` — eliminar 9 settings
- `src/core/memory.py` — 3 métodos nuevos para `internal/`, actualizar `create_conversation`
- `src/core/services.py` — singletons nuevos
- `src/core/controller/core.py` — cambiar herencia y constructor
- `src/core/controller/input.py` — flujo de inferencia completamente nuevo
- `src/api/chat/websocket.py` — eliminar gestión de sesiones
- `src/api/quick.py` — eliminar sesiones, usar provider resolution
- `src/main.py` — startup bloqueante
- `tests/conftest.py` — fixtures actualizadas

### Archivos eliminados
- `src/services/inference/connection.py`
- `src/services/inference/session_manager.py`
- `src/services/inference/client.py`
- `src/services/inference/exceptions.py`
- `src/services/inference/__init__.py`
- `src/core/controller/models.py`
- `tests/unit/test_inference_client.py`
- `tests/test_inference_connection.py`
- `tests/integration/test_inference_flow.py`

---

## Task 1: Actualizar dependencias (HECHO)

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Actualizar requirements.txt**

```
fastapi
uvicorn[standard]
pydantic-settings
httpx
pytest
pytest-asyncio
gunicorn
tavily-python
mcp
openai
```

(Eliminar `websockets`, añadir `openai`)

- [ ] **Step 2: Instalar**

```bash
pip install openai && pip uninstall websockets -y
```

- [ ] **Step 3: Commit** (ya esta commiteado)

```bash
git checkout -b feat/multiprovider-openai
git add requirements.txt
git commit -m "chore: swap websockets for openai SDK in dependencies"
```

---

## Task 2: Limpiar config.py (HECHO)

**Files:**
- Modify: `src/core/config.py`

- [ ] **Step 1: Eliminar settings obsoletas**

Sustituir el contenido de `src/core/config.py` por:

```python
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "JotaOrchestrator"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # Internal Services Authentication
    ORCHESTRATOR_ID: str
    ORCHESTRATOR_API_KEY: str

    # ---------------------------------------------------------------------------
    # Tool output limits
    # ---------------------------------------------------------------------------
    TOOL_MAX_OUTPUT_CHARS: int = 4000
    MEMORY_TOOL_OUTPUT_CAP: int = 1000

    # ---------------------------------------------------------------------------
    # Tool Config
    # ---------------------------------------------------------------------------
    TAVILY_API_KEY: Optional[str] = None
    TAVILY_SEARCH_DEPTH: str = "basic"
    TAVILY_MAX_RESULTS: int = 5
    TAVILY_TIMEOUT: float = 6.0
    ENABLE_GBNF_GRAMMAR: bool = False

    # ---------------------------------------------------------------------------
    # JotaDB Integration
    # ---------------------------------------------------------------------------
    JOTA_DB_URL: str
    JOTA_DB_SK: str
    JOTA_DB_TIMEOUT: float = 10.0

    # ---------------------------------------------------------------------------
    # CORS
    # ---------------------------------------------------------------------------
    CORS_ORIGINS: list[str] = ["*"]

    # SSL/TLS
    SSL_VERIFY: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 2: Verificar que el módulo importa sin errores**

```bash
TRANSCRIPTION_SERVICE_URL=x ORCHESTRATOR_ID=x ORCHESTRATOR_API_KEY=x \
JOTA_DB_URL=x JOTA_DB_SK=x \
python -c "from src.core.config import settings; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/core/config.py
git commit -m "refactor: remove inference and prompt settings from config — moved to DB"
```

---

## Task 3: Añadir métodos internos al MemoryManager (HECHO)

**Files:**
- Modify: `src/core/memory.py`
- Create: `tests/unit/test_memory_manager_internal.py`

- [ ] **Step 1: Escribir tests**

Crear `tests/unit/test_memory_manager_internal.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.memory import MemoryManager


@pytest.fixture
def manager():
    with patch("src.core.memory.settings") as mock_cfg:
        mock_cfg.JOTA_DB_URL = "http://testdb"
        mock_cfg.JOTA_DB_SK = "sk_test"
        mock_cfg.JOTA_DB_TIMEOUT = 10.0
        mock_cfg.SSL_VERIFY = True
        m = MemoryManager()
    return m


@pytest.mark.asyncio
async def test_get_orchestrator_config_calls_correct_endpoint(manager):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"key": "default_provider_id", "value": "uuid-123"},
        {"key": "system_prompt", "value": "Eres Jota"},
        {"key": "tool_followup_prompt", "value": "Responde usando los resultados."},
    ]
    mock_response.raise_for_status = MagicMock()
    manager.client.get = AsyncMock(return_value=mock_response)

    result = await manager.get_orchestrator_config()

    manager.client.get.assert_called_once()
    call_url = manager.client.get.call_args[0][0]
    assert "/internal/service-config/orchestrator" in call_url
    assert result == {
        "default_provider_id": "uuid-123",
        "system_prompt": "Eres Jota",
        "tool_followup_prompt": "Responde usando los resultados.",
    }


@pytest.mark.asyncio
async def test_get_providers_calls_correct_endpoint(manager):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "id": "prov-uuid",
            "name": "Local LLM",
            "type": "openai_compatible",
            "base_url": "http://jota-inference:8002",
            "api_key": "local-key",
            "default_model_id": "llama-3.2-3b",
            "is_active": True,
        }
    ]
    mock_response.raise_for_status = MagicMock()
    manager.client.get = AsyncMock(return_value=mock_response)

    result = await manager.get_providers()

    call_url = manager.client.get.call_args[0][0]
    assert "/internal/providers" in call_url
    assert len(result) == 1
    assert result[0]["id"] == "prov-uuid"


@pytest.mark.asyncio
async def test_get_client_config_returns_none_on_404(manager):
    mock_response = MagicMock()
    mock_response.status_code = 404
    manager.client.get = AsyncMock(return_value=mock_response)

    result = await manager.get_client_config("client-abc")
    assert result is None


@pytest.mark.asyncio
async def test_create_conversation_sends_provider_id(manager):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "conv-1", "provider_id": "prov-uuid", "model_id": "llama-3b"}
    mock_response.raise_for_status = MagicMock()
    manager.client.post = AsyncMock(return_value=mock_response)

    result = await manager.create_conversation(
        client_id="client-1",
        model_id="llama-3b",
        provider_id="prov-uuid"
    )

    payload = manager.client.post.call_args[1]["json"]
    assert payload["provider_id"] == "prov-uuid"
    assert result["id"] == "conv-1"
```

- [ ] **Step 2: Ejecutar tests — verificar que fallan**

```bash
.venv/bin/pytest tests/unit/test_memory_manager_internal.py -v
```

Expected: FAIL — `get_orchestrator_config` no existe.

- [ ] **Step 3: Implementar los métodos en MemoryManager**

Añadir al final de la clase `MemoryManager` en `src/core/memory.py` (antes del `mark_conversation_error`):

```python
async def get_orchestrator_config(self) -> dict:
    """
    Fetches orchestrator service-config from JotaDB internal endpoint.
    Returns a flat dict {key: value} parsed from the list response.
    Returns empty dict on error.
    """
    try:
        response = await self.client.get(
            f"{self.base_url}/internal/service-config/orchestrator",
            headers={
                **self.base_headers,
                "X-API-Key": settings.ORCHESTRATOR_API_KEY,
            },
        )
        response.raise_for_status()
        raw = response.json()
        return {item["key"]: item["value"] for item in raw}
    except Exception as e:
        logger.error(f"Failed to fetch orchestrator config: {e}")
        return {}

async def get_providers(self) -> list[dict]:
    """
    Fetches active InferenceProviders from JotaDB internal endpoint.
    Returns empty list on error.
    """
    try:
        response = await self.client.get(
            f"{self.base_url}/internal/providers",
            headers={
                **self.base_headers,
                "X-API-Key": settings.ORCHESTRATOR_API_KEY,
            },
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch providers: {e}")
        return []

async def get_client_config(self, client_id: str) -> dict | None:
    """
    Fetches ClientConfig for a given client from JotaDB internal endpoint.
    Returns None if not found or on error.
    """
    try:
        response = await self.client.get(
            f"{self.base_url}/internal/client-config/{client_id}",
            headers={
                **self.base_headers,
                "X-API-Key": settings.ORCHESTRATOR_API_KEY,
            },
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch client config for {client_id}: {e}")
        return None
```

También actualizar `create_conversation` para aceptar `provider_id`:

```python
async def create_conversation(self, client_id: Any, model_id: Optional[str] = None, provider_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        service_headers = {
            **self.base_headers,
            "X-API-Key": settings.ORCHESTRATOR_API_KEY,
            "X-Client-ID": str(client_id)
        }

        payload: Dict[str, Any] = {"client_id": client_id, "status": "active"}
        if model_id:
            payload["model_id"] = model_id
        if provider_id:
            payload["provider_id"] = provider_id

        create_response = await self.client.post(
            f"{self.base_url}/chat/conversations",
            json=payload,
            headers=service_headers,
        )
        create_response.raise_for_status()
        return create_response.json()

    except Exception as e:
        logger.error(f"Error managing conversation for client {client_id}: {e}")
        raise e
```

- [ ] **Step 4: Ejecutar tests — verificar que pasan**

```bash
.venv/bin/pytest tests/unit/test_memory_manager_internal.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/core/memory.py tests/unit/test_memory_manager_internal.py
git commit -m "feat: add internal/ endpoint methods to MemoryManager (providers, orchestrator config, client config)"
```

---

## Task 4: ConfigManager (HECHO)

**Files:**
- Create: `src/core/config_manager.py`
- Create: `tests/unit/test_config_manager.py`

- [ ] **Step 1: Escribir tests**

Crear `tests/unit/test_config_manager.py`:

```python
import pytest
from unittest.mock import AsyncMock
from src.core.config_manager import ConfigManager, OrchestratorConfig


@pytest.fixture
def mock_memory():
    m = AsyncMock()
    m.get_orchestrator_config = AsyncMock(return_value={
        "default_provider_id": "prov-uuid",
        "system_prompt": "Eres Jota.",
        "tool_followup_prompt": "Usa los resultados para responder.",
    })
    return m


@pytest.mark.asyncio
async def test_load_parses_config(mock_memory):
    cm = ConfigManager(memory_manager=mock_memory)
    await cm.load()

    assert cm.config.default_provider_id == "prov-uuid"
    assert cm.config.system_prompt == "Eres Jota."
    assert cm.config.tool_followup_prompt == "Usa los resultados para responder."


@pytest.mark.asyncio
async def test_config_raises_before_load():
    mock_memory = AsyncMock()
    cm = ConfigManager(memory_manager=mock_memory)

    with pytest.raises(RuntimeError, match="not initialized"):
        _ = cm.config


@pytest.mark.asyncio
async def test_load_uses_defaults_for_missing_keys(mock_memory):
    mock_memory.get_orchestrator_config = AsyncMock(return_value={
        "default_provider_id": "prov-uuid",
        # system_prompt and tool_followup_prompt missing
    })
    cm = ConfigManager(memory_manager=mock_memory)
    await cm.load()

    assert "Jota" in cm.config.system_prompt
    assert cm.config.tool_followup_prompt != ""


@pytest.mark.asyncio
async def test_load_raises_if_default_provider_missing(mock_memory):
    mock_memory.get_orchestrator_config = AsyncMock(return_value={})
    cm = ConfigManager(memory_manager=mock_memory)

    with pytest.raises(RuntimeError, match="default_provider_id"):
        await cm.load()
```

- [ ] **Step 2: Ejecutar — verificar que fallan**

```bash
.venv/bin/pytest tests/unit/test_config_manager.py -v
```

Expected: FAIL — `ConfigManager` no existe.

- [ ] **Step 3: Implementar ConfigManager**

Crear `src/core/config_manager.py`:

```python
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.memory import MemoryManager

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are Jota, a helpful and friendly AI assistant. "
    "Respond concisely and naturally. Keep answers short — "
    "use a few sentences unless the user explicitly asks for detail. "
    "Match the language the user writes in."
)

_DEFAULT_TOOL_FOLLOWUP = (
    "The tool has provided the results. "
    "Please answer the original user query using this information."
)


@dataclass
class OrchestratorConfig:
    default_provider_id: str
    system_prompt: str
    tool_followup_prompt: str


class ConfigManager:
    """
    Loads and caches orchestrator configuration from JotaDB.
    Must be initialized via load() before config is accessible.
    """

    def __init__(self, memory_manager: "MemoryManager"):
        self._memory_manager = memory_manager
        self._config: OrchestratorConfig | None = None

    async def load(self) -> None:
        """
        Fetches orchestrator service-config from DB and parses it.
        Raises RuntimeError if required key default_provider_id is missing.
        """
        raw = await self._memory_manager.get_orchestrator_config()

        default_provider_id = raw.get("default_provider_id")
        if not default_provider_id:
            raise RuntimeError(
                "Missing required config key 'default_provider_id' in JotaDB service-config/orchestrator"
            )

        self._config = OrchestratorConfig(
            default_provider_id=default_provider_id,
            system_prompt=raw.get("system_prompt", _DEFAULT_SYSTEM_PROMPT),
            tool_followup_prompt=raw.get("tool_followup_prompt", _DEFAULT_TOOL_FOLLOWUP),
        )
        logger.info(f"ConfigManager loaded — default_provider={default_provider_id!r}")

    @property
    def config(self) -> OrchestratorConfig:
        if self._config is None:
            raise RuntimeError("ConfigManager not initialized. Call load() first.")
        return self._config
```

- [ ] **Step 4: Ejecutar tests — verificar que pasan**

```bash
.venv/bin/pytest tests/unit/test_config_manager.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/core/config_manager.py tests/unit/test_config_manager.py
git commit -m "feat: add ConfigManager — loads orchestrator config from JotaDB on startup"
```

---

## Task 5: BaseProvider y adapters mock (HECHO)

**Files:**
- Create: `src/services/providers/__init__.py`
- Create: `src/services/providers/base.py`
- Create: `src/services/providers/anthropic.py`
- Create: `src/services/providers/gemini.py`

- [ ] **Step 1: Crear el paquete y la interfaz base**

Crear `src/services/providers/__init__.py` (solo base por ahora — manager se añade en Task 7):
```python
from .base import BaseProvider

__all__ = ["BaseProvider"]
```

Crear `src/services/providers/base.py`:

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseProvider(ABC):
    """
    Interfaz común para todos los adapters de inferencia.
    Cada yield del generador es un str (token de texto) o un dict
    con {"type": "tool_call", "payload": {...}}.
    """

    @abstractmethod
    async def infer(
        self,
        messages: list[dict],
        model: str,
        params: dict | None = None,
    ) -> AsyncGenerator[str | dict, None]:
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        ...
```

- [ ] **Step 2: Crear adapters mock**

Crear `src/services/providers/anthropic.py`:

```python
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
```

Crear `src/services/providers/gemini.py`:

```python
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
```

- [ ] **Step 3: Verificar que el paquete importa**

```bash
python -c "from src.services.providers.base import BaseProvider; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/services/providers/
git commit -m "feat: add BaseProvider interface and mock Anthropic/Gemini adapters"
```

---

## Task 6: OpenAICompatibleAdapter (HECHO)

**Files:**
- Create: `src/services/providers/openai_compatible.py`
- Create: `tests/unit/test_openai_adapter.py`

- [ ] **Step 1: Escribir tests**

Crear `tests/unit/test_openai_adapter.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.providers.openai_compatible import OpenAICompatibleAdapter


def _make_chunk(content: str):
    """Creates a mock OpenAI stream chunk with text content."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta = MagicMock()
    chunk.choices[0].delta.content = content
    return chunk


async def _async_gen(*chunks):
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_infer_yields_text_tokens():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")

    mock_stream = _async_gen(
        _make_chunk("Hello"),
        _make_chunk(" world"),
        _make_chunk("!"),
    )

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        tokens = []
        async for token in adapter.infer(
            messages=[{"role": "user", "content": "Hi"}],
            model="test-model",
        ):
            tokens.append(token)

    assert all(isinstance(t, str) for t in tokens)
    assert "".join(tokens) == "Hello world!"


@pytest.mark.asyncio
async def test_infer_detects_xml_tool_call():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")

    tool_json = '{"name": "search", "arguments": {"query": "python"}}'
    mock_stream = _async_gen(
        _make_chunk(f'<tool_call>{tool_json}</tool_call>'),
    )

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        results = []
        async for item in adapter.infer(
            messages=[{"role": "user", "content": "search python"}],
            model="test-model",
        ):
            results.append(item)

    tool_calls = [r for r in results if isinstance(r, dict) and r.get("type") == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["payload"]["name"] == "search"
    assert tool_calls[0]["payload"]["arguments"]["query"] == "python"


@pytest.mark.asyncio
async def test_infer_skips_empty_chunks():
    adapter = OpenAICompatibleAdapter(base_url="http://test", api_key="key")

    empty_chunk = MagicMock()
    empty_chunk.choices = []

    mock_stream = _async_gen(empty_chunk, _make_chunk("Hi"))

    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=mock_stream)):
        tokens = []
        async for token in adapter.infer(
            messages=[{"role": "user", "content": "test"}],
            model="test-model",
        ):
            tokens.append(token)

    assert "".join(tokens) == "Hi"


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

- [ ] **Step 2: Ejecutar — verificar que fallan**

```bash
.venv/bin/pytest tests/unit/test_openai_adapter.py -v
```

Expected: FAIL — `OpenAICompatibleAdapter` no existe.

- [ ] **Step 3: Implementar OpenAICompatibleAdapter**

Crear `src/services/providers/openai_compatible.py`:

```python
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
```

- [ ] **Step 4: Ejecutar tests — verificar que pasan**

```bash
.venv/bin/pytest tests/unit/test_openai_adapter.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/providers/openai_compatible.py tests/unit/test_openai_adapter.py
git commit -m "feat: add OpenAICompatibleAdapter with XML tool call detection"
```

---

## Task 7: ProviderManager (HECHO)

**Files:**
- Create: `src/services/providers/manager.py`
- Create: `tests/unit/test_provider_manager.py`

- [ ] **Step 1: Escribir tests**

Crear `tests/unit/test_provider_manager.py`:

```python
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
```

- [ ] **Step 2: Ejecutar — verificar que fallan**

```bash
.venv/bin/pytest tests/unit/test_provider_manager.py -v
```

Expected: FAIL — `ProviderManager` no existe.

- [ ] **Step 3: Implementar ProviderManager**

Crear `src/services/providers/manager.py`:

```python
import logging
from .base import BaseProvider
from .openai_compatible import OpenAICompatibleAdapter
from .anthropic import AnthropicAdapter
from .gemini import GeminiAdapter

logger = logging.getLogger(__name__)

_ADAPTER_MAP = {
    "openai_compatible": OpenAICompatibleAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
}


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
            provider_id = p["id"]
            provider_type = p.get("type", "openai_compatible")
            adapter_class = _ADAPTER_MAP.get(provider_type)

            if not adapter_class:
                logger.warning(f"Unknown provider type {provider_type!r} for provider {provider_id!r} — skipping")
                continue

            if provider_type == "openai_compatible":
                adapter = adapter_class(base_url=p.get("base_url", ""), api_key=p.get("api_key", ""))
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

- [ ] **Step 4: Actualizar `src/services/providers/__init__.py`**

```python
from .base import BaseProvider
from .manager import ProviderManager, ProviderNotFoundError

__all__ = ["BaseProvider", "ProviderManager", "ProviderNotFoundError"]
```

- [ ] **Step 5: Ejecutar tests — verificar que pasan**

```bash
.venv/bin/pytest tests/unit/test_provider_manager.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add src/services/providers/ tests/unit/test_provider_manager.py
git commit -m "feat: add ProviderManager — routes requests to typed adapters loaded from DB"
```

---

## Task 8: Actualizar services.py y controller core

**Files:**
- Modify: `src/core/services.py`
- Modify: `src/core/controller/core.py`

- [ ] **Step 1: Actualizar services.py**

Reemplazar el contenido de `src/core/services.py`:

```python
import logging
from src.core.memory import MemoryManager
from src.core.config_manager import ConfigManager
from src.services.providers import ProviderManager
from src.core.controller import JotaController
import src.tools  # noqa: F401 — triggers @tool decorator registrations

logger = logging.getLogger(__name__)

# Singleton services — initialized at import time.
# provider_manager and config_manager are populated during lifespan startup.
memory_manager = MemoryManager()
config_manager = ConfigManager(memory_manager=memory_manager)
provider_manager = ProviderManager()
jota_controller = JotaController(
    provider_manager=provider_manager,
    memory_manager=memory_manager,
    config_manager=config_manager,
)


async def shutdown_services():
    logger.info("Shutting down services...")
    await memory_manager.close()
    logger.info("Services shut down.")
```

- [ ] **Step 2: Actualizar controller/core.py**

Reemplazar el contenido de `src/core/controller/core.py`:

```python
"""
Core controller for the Orchestrator.
"""
import logging
from typing import TYPE_CHECKING

from src.core.events import event_bus
from .input import JotaInputMixin

if TYPE_CHECKING:
    from src.core.memory import MemoryManager
    from src.core.config_manager import ConfigManager
    from src.services.providers import ProviderManager

logger = logging.getLogger(__name__)


class JotaController(JotaInputMixin):
    """
    Controlador principal del Orchestrator.

    Args:
        provider_manager: Gestiona los adapters de inferencia por provider.
        memory_manager:   Acceso a JotaDB.
        config_manager:   Configuración del orchestrator cargada desde DB.
    """

    def __init__(
        self,
        provider_manager: "ProviderManager",
        memory_manager: "MemoryManager",
        config_manager: "ConfigManager",
    ):
        self.provider_manager = provider_manager
        self.memory_manager = memory_manager
        self.config_manager = config_manager
        event_bus.subscribe(self.process_event_async)

    async def process_event_async(self, event: dict):
        async for _ in self.handle_input(event):
            pass
```

- [ ] **Step 3: Verificar que el paquete importa**

```bash
ORCHESTRATOR_ID=x ORCHESTRATOR_API_KEY=x JOTA_DB_URL=x JOTA_DB_SK=x \
python -c "from src.core.services import jota_controller; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/core/services.py src/core/controller/core.py
git commit -m "refactor: wire ProviderManager and ConfigManager into services and controller"
```

---

## Task 9: Refactorizar controller/input.py

**Files:**
- Modify: `src/core/controller/input.py`
- Delete: `src/core/controller/models.py`

- [ ] **Step 1: Eliminar models.py**

```bash
rm src/core/controller/models.py
```

- [ ] **Step 2: Reemplazar controller/input.py completo**

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
          3. Stream tokens from provider adapter.
          4. Handle tool calls: execute, save, re-infer.
          5. Persist assistant response to DB.
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

            # 2. Build system prompt
            from src.core.tool_manager import tool_manager
            tool_instructions = tool_manager.get_system_prompt_addition(client_id=client_id)
            base_prompt = system_prompt_override or self.config_manager.config.system_prompt
            system_prompt = base_prompt
            if tool_instructions:
                system_prompt += "\n\n" + tool_instructions

            # 3. Build messages array
            messages = [{"role": "system", "content": system_prompt}]
            if not stateless:
                history = await self.memory_manager.get_conversation_messages(
                    conversation_id, client_id
                )
                messages.extend(history)
            messages.append({"role": "user", "content": content})

            infer_params = {"temp": 0.7}

            # 4. First inference pass
            tool_executed = False
            pre_tool_thinking: list[str] = []
            response_buffer: list[str] = []

            async for token in adapter.infer(messages, model_id, infer_params):
                if isinstance(token, dict) and token.get("type") == "tool_call":
                    tc_payload = token.get("payload", {})
                    tool_name = tc_payload.get("name")
                    tool_args = tc_payload.get("arguments", {})

                    # Save pre-tool thinking to DB (not shown to user)
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
                else:
                    if not tool_executed:
                        pre_tool_thinking.append(token)
                        response_buffer.append(token)

            # Flush buffered thinking if no tool call happened
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

            # 5. Re-inference after tool execution
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

            final_buffer: list[str] = []
            async for token in adapter.infer(followup_messages, model_id, infer_params):
                if isinstance(token, dict) and token.get("type") == "tool_call":
                    logger.warning("Nested tool call attempted — ignoring.")
                else:
                    final_buffer.append(token)
                    yield token

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

- [ ] **Step 3: Actualizar `src/core/controller/__init__.py`**

Verificar que no importa `JotaModelMixin` ni `models`:

```python
from .core import JotaController

__all__ = ["JotaController"]
```

- [ ] **Step 4: Verificar import**

```bash
ORCHESTRATOR_ID=x ORCHESTRATOR_API_KEY=x JOTA_DB_URL=x JOTA_DB_SK=x \
python -c "from src.core.controller import JotaController; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/core/controller/
git commit -m "refactor: replace WebSocket inference flow with provider adapter pattern in controller"
```

---

## Task 10: Refactorizar websocket.py

**Files:**
- Modify: `src/api/chat/websocket.py`

- [ ] **Step 1: Reemplazar websocket.py**

```python
"""
WebSocket API endpoints for chat operations.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.core.services import jota_controller, memory_manager, provider_manager
import json as _json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/chat/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handles a full WebSocket chat session.

    1. Authenticate client.
    2. Resolve or create conversation.
    3. Stream responses via handle_input.
    """
    # 1. Authentication
    client_key = (
        websocket.headers.get("x-client-key")
        or websocket.query_params.get("x_client_key")
        or websocket.query_params.get("client_key")
    )
    if not client_key:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    client_data = await memory_manager.validate_client_key(client_key)
    if not client_data:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    client_type = client_data.get("client_type", "CHAT")
    if client_type == "QUICK":
        await websocket.close(code=4003, reason="Client type 'QUICK' not allowed on WebSocket")
        return

    client_id = client_data["id"]
    await websocket.accept()
    logger.info(f"WebSocket connected for client {client_id}")

    try:
        # 2. Conversation management
        conversation_id = websocket.query_params.get("conversation_id")
        model_id = websocket.query_params.get("model_id") or None
        provider_id = websocket.query_params.get("provider_id") or None

        if not conversation_id:
            conversation = await memory_manager.create_conversation(
                client_id=client_id,
                model_id=model_id,
                provider_id=provider_id,
            )
            conversation_id = conversation["id"]
            logger.info(f"New conversation {conversation_id} for client {client_id}")
        elif model_id or provider_id:
            # Update conversation model/provider in DB
            update: dict = {}
            if model_id:
                update["model_id"] = model_id
            if provider_id:
                update["provider_id"] = provider_id
            await memory_manager.set_conversation_model(
                conversation_id, client_id, model_id or ""
            )

        log_prefix = f"[Conv: {conversation_id}]"
        logger.info(f"{log_prefix} Session ready. Waiting for messages...")

        while True:
            data = await websocket.receive_text()
            logger.info(f"{log_prefix} Received: {data[:80]}")

            # Control messages
            try:
                ctrl = _json.loads(data)
                if isinstance(ctrl, dict) and "type" in ctrl:
                    msg_type = ctrl["type"]

                    if msg_type == "switch_model":
                        new_model = ctrl.get("model_id", "").strip()
                        new_provider = ctrl.get("provider_id", "").strip() or None
                        if not new_model:
                            await websocket.send_text(_json.dumps({
                                "type": "error",
                                "message": "switch_model requires a non-empty model_id",
                            }))
                            continue
                        await memory_manager.set_conversation_model(
                            conversation_id, client_id, new_model
                        )
                        await websocket.send_text(_json.dumps({
                            "type": "model_switched",
                            "model_id": new_model,
                        }))
                        continue

                    logger.warning(f"{log_prefix} Unknown control type: {msg_type!r}")
                    await websocket.send_text(_json.dumps({
                        "type": "error",
                        "message": f"Unknown control type: {msg_type!r}",
                    }))
                    continue
            except _json.JSONDecodeError:
                pass  # plain text prompt

            # Save user message
            await memory_manager.save_message(
                conversation_id=conversation_id,
                role="user",
                content=data,
                client_id=client_id,
            )

            payload = {
                "content": data,
                "conversation_id": conversation_id,
                "client_id": client_id,
            }

            # Stream tokens back
            async for token in jota_controller.handle_input(payload):
                if isinstance(token, dict):
                    await websocket.send_text(_json.dumps(token))
                else:
                    await websocket.send_text(_json.dumps({"type": "token", "content": token}))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for client {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        await websocket.close(code=1011)
```

- [ ] **Step 2: Commit**

```bash
git add src/api/chat/websocket.py
git commit -m "refactor: remove session management from WebSocket handler — stateless per-message flow"
```

---

## Task 11: Refactorizar quick.py

**Files:**
- Modify: `src/api/quick.py`

- [ ] **Step 1: Reemplazar quick.py**

```python
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

    # Build system prompt
    tool_instructions = tool_manager.get_system_prompt_addition(client_id=client_id)
    base_prompt = config_manager.config.system_prompt
    full_prompt = f"{base_prompt}\n\n{QUICK_SYSTEM_PROMPT_PREFIX}"
    if tool_instructions:
        full_prompt += f"\n{tool_instructions}"
    if request.system_prompt_extra:
        full_prompt += f"\n{request.system_prompt_extra}"

    messages = [
        {"role": "system", "content": full_prompt},
        {"role": "user", "content": request.text},
    ]
    quick_params = {"temp": 0.3, "max_tokens": 150}
    quick_final_params = {"temp": 0.3, "max_tokens": 100}

    tool_executed = False
    tool_context: list[dict] = []

    try:
        async for token in adapter.infer(messages, model_id, quick_params):
            if isinstance(token, dict) and token.get("type") == "tool_call":
                tc_payload = token.get("payload", {})
                tool_name = tc_payload.get("name")
                tool_args = tc_payload.get("arguments", {})

                logger.info(f"{log_prefix} Tool call: {tool_name}")
                yield json.dumps({"type": "status", "content": f"Buscando información usando {tool_name}..."}) + "\n"

                try:
                    start_t = time.time()
                    result = await tool_manager.execute_tool(tool_name, client_id=client_id, **tool_args)
                    duration = f"{time.time() - start_t:.2f}s"
                    result_str = result if isinstance(result, str) else json.dumps(result)

                    tool_context = [
                        {"role": "user", "content": request.text},
                        {"role": "assistant", "content": f"<tool_call>{json.dumps(tc_payload)}</tool_call>"},
                        {"role": "tool", "content": result_str},
                    ]
                    yield json.dumps({"type": "status", "content": f"Búsqueda completada en {duration}. Generando respuesta..."}) + "\n"
                    tool_executed = True
                except Exception as e:
                    logger.error(f"{log_prefix} Tool {tool_name} failed: {e}")
                    yield json.dumps({"type": "status", "content": f"Error al usar {tool_name}: {e}"}) + "\n"
                    tool_executed = True
            else:
                if not tool_executed and isinstance(token, str):
                    yield json.dumps({"type": "token", "content": token}) + "\n"

        if tool_executed:
            yield json.dumps({"type": "status", "content": "Analizando resultados..."}) + "\n"
            followup_messages = [{"role": "system", "content": full_prompt}] + tool_context + [
                {"role": "user", "content": config_manager.config.tool_followup_prompt}
            ]
            async for token in adapter.infer(followup_messages, model_id, quick_final_params):
                if isinstance(token, str):
                    yield json.dumps({"type": "token", "content": token}) + "\n"

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

- [ ] **Step 2: Commit**

```bash
git add src/api/quick.py
git commit -m "refactor: quick endpoint uses ProviderManager — no session management"
```

---

## Task 12: Startup bloqueante en main.py

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Reemplazar el lifespan y health check**

```python
from fastapi import FastAPI, Response, status
from contextlib import asynccontextmanager
import asyncio
import logging
import sys

from src.core.config import settings
from src.api.chat import router as chat_router
from src.api.quick import router as quick_router
from src.core.services import (
    memory_manager,
    config_manager,
    provider_manager,
    shutdown_services,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)
logger = logging.getLogger("uvicorn")

_MAX_STARTUP_RETRIES = 5
_STARTUP_RETRY_BASE_DELAY = 2  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO JOTA ORCHESTRATOR")
    logger.info("=" * 60)

    for attempt in range(1, _MAX_STARTUP_RETRIES + 1):
        try:
            logger.info(f"📊 Cargando configuración desde JotaDB (intento {attempt}/{_MAX_STARTUP_RETRIES})...")

            # 1. Verify DB connection
            if not await memory_manager.verify_connection():
                raise RuntimeError("JotaDB connection or authentication failed")

            # 2. Load orchestrator config (blocking)
            await config_manager.load()
            logger.info(f"✅ Config cargada — default_provider={config_manager.config.default_provider_id!r}")

            # 3. Load providers and initialize adapters (blocking)
            providers = await memory_manager.get_providers()
            if not providers:
                raise RuntimeError("No active providers returned from JotaDB")

            await provider_manager.init(
                providers=providers,
                default_provider_id=config_manager.config.default_provider_id,
            )
            logger.info(f"✅ {len(providers)} provider(s) registrado(s)")
            break

        except Exception as e:
            if attempt == _MAX_STARTUP_RETRIES:
                logger.error(f"❌ Startup failed after {_MAX_STARTUP_RETRIES} attempts: {e}")
                sys.exit(1)
            delay = _STARTUP_RETRY_BASE_DELAY ** attempt
            logger.warning(f"⚠️  Startup attempt {attempt} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)

    logger.info("=" * 60)
    logger.info("✨ JotaOrchestrator listo para recibir peticiones")
    logger.info("=" * 60)

    yield

    logger.info("🛑 Cerrando servicios...")
    await shutdown_services()
    logger.info("👋 JotaOrchestrator detenido")


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

_cors_origins = settings.CORS_ORIGINS
_allow_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(quick_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "environment": settings.APP_ENV,
        "status": "online",
    }


@app.get("/health")
async def health_check(response: Response):
    """
    Deep Health Check. Verifies JotaDB and all registered providers.
    """
    db_ok = await memory_manager.check_health()
    provider_health = await provider_manager.check_health()

    all_ok = db_ok and all(provider_health.values())

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if all_ok else "degraded",
        "components": {
            "jota_db": "connected" if db_ok else "disconnected",
            "providers": {pid: ("ok" if ok else "degraded") for pid, ok in provider_health.items()},
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: Commit**

```bash
git add src/main.py
git commit -m "feat: blocking startup — loads config and providers from JotaDB before accepting requests"
```

---

## Task 13: Eliminar src/services/inference/

**Files:**
- Delete: `src/services/inference/` (directorio completo)

- [ ] **Step 1: Buscar cualquier import restante de inference**

```bash
grep -r "services.inference\|from src.services.inference\|inference_client" src/ --include="*.py"
```

Expected: ningún resultado (o solo comentarios).

- [ ] **Step 2: Eliminar el directorio**

```bash
rm -rf src/services/inference/
```

- [ ] **Step 3: Verificar que la app arranca sin errores de import**

```bash
ORCHESTRATOR_ID=x ORCHESTRATOR_API_KEY=x JOTA_DB_URL=x JOTA_DB_SK=x \
python -c "import src.main; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete WebSocket InferenceClient — replaced by ProviderManager"
```

---

## Task 14: Actualizar tests

**Files:**
- Delete: `tests/unit/test_inference_client.py`
- Delete: `tests/test_inference_connection.py`
- Delete: `tests/integration/test_inference_flow.py`
- Modify: `tests/conftest.py`
- Modify: `tests/unit/test_quick_system_prompt.py`

- [ ] **Step 1: Eliminar tests obsoletos**

```bash
rm tests/unit/test_inference_client.py
rm tests/test_inference_connection.py
rm tests/integration/test_inference_flow.py
```

- [ ] **Step 2: Actualizar conftest.py**

Reemplazar `tests/conftest.py`:

```python
import pytest
import asyncio
from unittest.mock import AsyncMock


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
    """A mock BaseProvider that yields a single token."""
    async def _infer(messages, model, params=None):
        yield "Hello world"

    p = AsyncMock()
    p.infer = _infer
    p.check_health = AsyncMock(return_value=True)
    return p


@pytest.fixture
def mock_provider_manager(mock_provider):
    pm = AsyncMock()
    pm.get_adapter = AsyncMock(return_value=mock_provider)
    pm.get_default = AsyncMock(return_value=("prov-test", "model-test"))
    pm.check_health = AsyncMock(return_value={"prov-test": True})
    return pm


@pytest.fixture
def mock_config_manager():
    from src.core.config_manager import OrchestratorConfig
    cm = AsyncMock()
    cm.config = OrchestratorConfig(
        default_provider_id="prov-test",
        system_prompt="Eres Jota.",
        tool_followup_prompt="Responde usando los resultados.",
    )
    return cm
```

- [ ] **Step 3: Actualizar test_quick_system_prompt.py si importa del inference viejo**

```bash
grep -n "inference\|InferenceClient\|websocket" tests/unit/test_quick_system_prompt.py
```

Actualizar cualquier import obsoleto que aparezca.

- [ ] **Step 4: Ejecutar toda la suite de tests unitarios**

```bash
.venv/bin/pytest tests/unit/ -v
```

Expected: todos los tests pasan (los obsoletos ya eliminados, los nuevos de Tasks 3-7 pasan).

- [ ] **Step 5: Commit final**

```bash
git add -A
git commit -m "test: update test suite for multi-provider refactor — remove WS tests, add provider/config tests"
```

---

## Task 15: PR y verificación final

- [ ] **Step 1: Ejecutar suite completa**

```bash
.venv/bin/pytest tests/unit/ tests/integration/ -v
```

Expected: todos pasan.

- [ ] **Step 2: Verificar import completo del sistema**

```bash
ORCHESTRATOR_ID=x ORCHESTRATOR_API_KEY=x JOTA_DB_URL=x JOTA_DB_SK=x \
python -c "
from src.core.services import memory_manager, config_manager, provider_manager, jota_controller
from src.services.providers import ProviderManager, ProviderNotFoundError
from src.core.config_manager import ConfigManager
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: Abrir PR**

```bash
git push -u origin feat/multiprovider-openai
gh pr create \
  --title "feat: multi-provider inference with OpenAI API standard" \
  --body "$(cat <<'EOF'
## Summary
- Replaces monolithic WebSocket InferenceClient with a ProviderManager + adapter pattern
- JotaDB is now the single source of truth for provider config, credentials and system prompt
- Blocking startup: orchestrator fails fast if DB is unreachable or config is missing
- OpenAICompatibleAdapter covers jota-inference, OpenAI, Ollama, Groq, etc.
- Anthropic and Gemini adapters stubbed (NotImplementedError) for future implementation

## Test plan
- [ ] Unit tests pass: `pytest tests/unit/ -v`
- [ ] Integration tests pass: `pytest tests/integration/ -v`
- [ ] App starts with real JotaDB connected (verify blocking startup logs)
- [ ] `/health` returns provider health status
- [ ] WebSocket chat works end-to-end
- [ ] `/api/quick` works with tool call

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Notas de implementación

- **jota-db changes needed:** Conversations table needs `provider_id` field. `InferenceProvider` needs `api_key` field. These must be deployed before this orchestrator version.
- **Tool calls:** XML `<tool_call>` format is preserved — no changes to `tool_manager.py` or `tool_parser.py`.
- **`TRANSCRIPTION_SERVICE_URL`:** No longer referenced in orchestrator code (it was never used directly). Remove from `.env` if desired.
- **`src/services/mcp_client.py`:** Not touched — MCP tools remain unchanged.
