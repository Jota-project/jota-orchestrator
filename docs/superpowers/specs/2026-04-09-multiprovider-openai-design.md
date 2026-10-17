# Design: Refactor Multi-Provider con estándar OpenAI API

**Fecha:** 2026-04-09  
**Estado:** En revisión  
**Scope:** jota-orchestrator (cambios en jota-db indicados pero no implementados aquí)

---

## Contexto y motivación

El orchestrator está actualmente acoplado a un único backend de inferencia (`jota-inference`) mediante un protocolo WebSocket propio con gestión explícita de sesiones, carga de modelos y reconexión. El objetivo es evolucionar a una filosofía **multi-provider** donde el orchestrator pueda hablar con cualquier proveedor de inferencia (local, OpenAI, Anthropic, Ollama, etc.) a través de un adaptador común.

JotaDB pasa a ser la **única fuente de verdad** para la configuración operativa: providers disponibles, credenciales, modelo por defecto, system prompt base, etc. El orchestrator arranca en modo bloqueante hasta tener esta configuración cargada.

---

## Decisiones de diseño

| Decisión | Elección | Motivo |
|---|---|---|
| Protocolo común | OpenAI API estándar (`POST /v1/chat/completions`) | Cubre la mayoría de providers; jota-inference migrará a este formato |
| Library para adapter OpenAI-compatible | `openai` Python SDK con `base_url` dinámico | Maneja streaming SSE, reintentos y parsing sin código propio |
| Providers no-compatibles (Anthropic, Gemini) | Mock (`NotImplementedError`) hasta implementar | Permite construir la abstracción sin bloquear |
| Tool calls | Mantener XML via system prompt (sin cambios) | Compatible con cualquier modelo; migración a native tool_calls es trabajo aparte |
| Fuente de verdad de config | JotaDB `internal/` endpoints | Permite cambiar config en caliente sin redeployar |
| Startup | Bloqueante en DB — falla duro si no hay config | Evita arrancar en estado inconsistente |
| Credenciales de providers | Vienen de DB (campo `api_key` en `InferenceProvider`) | No exponer secrets en `.env` |

---

## Arquitectura general

### Startup (bloqueante)

```
lifespan() en main.py
  │
  ├─ MemoryManager.load_orchestrator_config()
  │    └─ GET /internal/service-config/orchestrator
  │         → default_provider_id, system_prompt, tool_followup_prompt, ...
  │
  ├─ MemoryManager.get_providers()
  │    └─ GET /internal/providers
  │         → lista de InferenceProvider activos (con base_url, api_key, type, ...)
  │
  ├─ ProviderManager.init(providers, orchestrator_config)
  │    └─ instancia un adapter por provider según provider.type:
  │         "openai_compatible" → OpenAICompatibleAdapter(base_url, api_key)
  │         "anthropic"         → AnthropicAdapter()  [mock]
  │         "gemini"            → GeminiAdapter()     [mock]
  │
  └─ Si cualquier paso falla → retry con backoff → SystemExit si no recupera
```

### Request flow

```
WebSocket /api/chat  ó  POST /api/quick
  │
  ├─ Autenticar client → memory_manager.validate_client_key()
  │
  ├─ Resolver provider + modelo:
  │    1. conversation.provider_id + conversation.model_id   (de DB, prioridad máxima)
  │    2. client_config.preferred_model_id                   (de DB, por cliente)
  │    3. ConfigManager.default_provider_id + provider.default_model_id  (fallback global)
  │
  ├─ Cargar historial → memory_manager.get_conversation_messages()
  │    → lista de {role, content} para construir el array messages[]
  │
  ├─ Construir messages[] = [system_msg] + historial + [user_msg]
  │
  ├─ provider = ProviderManager.get_adapter(provider_id)
  │
  └─ provider.infer(messages, model, params) → AsyncGenerator[token | tool_call]
```

---

## Componentes nuevos

### `src/core/config_manager.py` — ConfigManager

Singleton que cachea la configuración del orchestrator leída de DB. Se inicializa en el lifespan y se pasa a los servicios que lo necesiten.

```python
@dataclass
class OrchestratorConfig:
    default_provider_id: str
    system_prompt: str
    tool_followup_prompt: str
    # otros campos de service-config/orchestrator

class ConfigManager:
    def __init__(self, memory_manager: MemoryManager): ...
    async def load(self) -> None: ...           # llamado en startup, bloqueante
    @property
    def config(self) -> OrchestratorConfig: ... # raises si no cargado
```

---

### `src/services/providers/base.py` — BaseProvider

Interfaz común que todos los adapters implementan.

```python
class BaseProvider(ABC):
    @abstractmethod
    async def infer(
        self,
        messages: list[dict],
        model: str,
        params: dict | None = None,
    ) -> AsyncGenerator[str | dict, None]: ...
    # str → token de texto
    # dict → {"type": "tool_call", "payload": {...}}

    @abstractmethod
    async def list_models(self) -> list[str]: ...

    @abstractmethod
    async def check_health(self) -> bool: ...
```

---

### `src/services/providers/openai_compatible.py` — OpenAICompatibleAdapter

Usa `openai.AsyncOpenAI(base_url=..., api_key=...)`. Soporta streaming SSE nativo. El system prompt con instrucciones de tools se inyecta como primer mensaje `role: system`.

Parseo de tool calls: igual que ahora — el modelo genera XML `<tool_call>` en el texto y el parser existente lo detecta. No se usan `tools: [...]` de la API por ahora.

```python
class OpenAICompatibleAdapter(BaseProvider):
    def __init__(self, base_url: str, api_key: str): ...
    async def infer(self, messages, model, params) -> AsyncGenerator: ...
    async def list_models(self) -> list[str]: ...
    async def check_health(self) -> bool: ...
```

---

### `src/services/providers/anthropic.py` / `gemini.py` — Mocks

```python
class AnthropicAdapter(BaseProvider):
    async def infer(self, *args, **kwargs):
        raise NotImplementedError("Anthropic adapter not yet implemented")

    async def list_models(self):
        raise NotImplementedError

    async def check_health(self):
        return False
```

---

### `src/services/providers/manager.py` — ProviderManager

Gestiona el registro de adapters y resuelve el provider correcto por `provider_id`.

```python
_ADAPTER_MAP = {
    "openai_compatible": OpenAICompatibleAdapter,
    "anthropic":         AnthropicAdapter,
    "gemini":            GeminiAdapter,
}

class ProviderManager:
    def __init__(self): ...

    async def init(self, providers: list[dict], config: OrchestratorConfig) -> None:
        # instancia un adapter por provider activo

    def get_adapter(self, provider_id: str) -> BaseProvider:
        # raises ProviderNotFoundError si no existe

    def get_default_adapter(self) -> tuple[str, str, BaseProvider]:
        # returns (provider_id, default_model_id, adapter)

    async def check_health(self) -> dict[str, bool]:
        # health de todos los providers
```

---

## Cambios en componentes existentes

### `src/core/memory.py` — Métodos nuevos

```python
# Config del orchestrator
async def get_orchestrator_config(self) -> dict: ...
    # GET /internal/service-config/orchestrator

# Providers disponibles
async def get_providers(self) -> list[dict]: ...
    # GET /internal/providers

# Config de cliente (preferred_model_id, system_prompt_extra, ...)
async def get_client_config(self, client_id: str) -> dict | None: ...
    # GET /internal/client-config/{client_id}

# Conversaciones — soporte a provider_id
async def create_conversation(self, client_id, model_id=None, provider_id=None) -> dict: ...
async def get_conversation(self, conversation_id, client_id) -> dict | None: ...
    # respuesta ya incluye provider_id
```

---

### `src/core/controller/input.py` — Flujo de inferencia

- Desaparece `_ensure_model_loaded()` — ya no hay carga explícita de modelo.
- La llamada a `infer()` pasa de `(prompt, session_id)` a `(messages[], model, provider_id)`.
- El array `messages[]` se construye aquí: `[system] + historial + [user_msg actual]`.
- La resolución de provider/modelo se delega a un helper `_resolve_provider()`.

---

### `src/core/controller/models.py`

Archivo eliminado o vaciado — la lógica de carga de modelo (`load_model`, `ensure_model_loaded`) desaparece. El provider gestiona qué modelo está activo internamente.

---

### `src/core/config.py` — Variables eliminadas

```python
# ELIMINAR:
INFERENCE_SERVICE_URL: str
AGENT_BASE_SYSTEM_PROMPT: str
TOOL_FOLLOWUP_PROMPT: str
INFERENCE_DEFAULT_TEMP: float
INFERENCE_TOKEN_TIMEOUT: float
INFERENCE_LOAD_MODEL_TIMEOUT: float
INFERENCE_LIST_MODELS_TIMEOUT: float
INFERENCE_SESSION_TIMEOUT: float
MODELS_CACHE_TTL: float

# MANTENER:
ORCHESTRATOR_ID, ORCHESTRATOR_API_KEY  # auth con JotaDB
JOTA_DB_URL, JOTA_DB_SK, JOTA_DB_TIMEOUT
CORS_ORIGINS, SSL_VERIFY
TAVILY_API_KEY, TAVILY_*, TOOL_MAX_OUTPUT_CHARS, MEMORY_TOOL_OUTPUT_CAP
APP_NAME, APP_ENV, DEBUG
```

---

### `src/core/services.py`

```python
# Antes:
memory_manager = MemoryManager()
inference_client = InferenceClient(memory_manager=memory_manager)
jota_controller = JotaController(inference_client=..., memory_manager=...)

# Después:
memory_manager = MemoryManager()
config_manager = ConfigManager(memory_manager=memory_manager)
provider_manager = ProviderManager()
jota_controller = JotaController(provider_manager=provider_manager, memory_manager=memory_manager, config_manager=config_manager)
```

---

### `src/main.py` — Lifespan

```python
# Startup bloqueante:
await config_manager.load()                          # 1. Config orchestrator
providers = await memory_manager.get_providers()     # 2. Providers de DB
await provider_manager.init(providers, config_manager.config)  # 3. Init adapters
# Si algo falla → retry con backoff → sys.exit(1) si no recupera
```

---

### `src/api/quick.py`

- Eliminar gestión de sesión efímera (`create_session`, `close_session`).
- Añadir resolución de provider/modelo vía `client_config.preferred_model_id`.
- El system prompt base viene de `config_manager`, no de `settings`.

---

## Archivos eliminados

```
src/services/inference/
  ├── connection.py       (WebSocket loop, reconexión, auth handshake)
  ├── session_manager.py  (create/ensure/release sessions)
  ├── client.py           (facade: infer, list_models, load_model)
  ├── exceptions.py       (InferenceEngineBusyError, ModelNotFoundError)
  └── __init__.py
```

---

## Archivos añadidos

```
src/services/providers/
  ├── __init__.py
  ├── base.py
  ├── openai_compatible.py
  ├── anthropic.py         (mock)
  ├── gemini.py            (mock)
  └── manager.py

src/core/config_manager.py
```

---

## Impacto en dependencias

### `requirements.txt`

| Paquete | Cambio |
|---|---|
| `websockets` | **ELIMINAR** |
| `openai` | **AÑADIR** |
| `anthropic` | Opcional por ahora (solo mock) |

---

## Impacto en Docker

`docker-compose.yml` sin cambios estructurales. El servicio ya no mantiene una conexión WebSocket persistente hacia jota-inference en startup — las llamadas son HTTP por petición. `network_mode: host` sigue siendo válido.

Variables de entorno que **desaparecen del `.env`**:
- `INFERENCE_SERVICE_URL`
- (Los provider credentials ya no van en `.env` — vienen de DB)

---

## Impacto en jota-db (cambios necesarios en esa repo)

1. **Conversations**: añadir campo `provider_id` (UUID, FK a `InferenceProvider`, nullable para compatibilidad).
2. **InferenceProvider**: confirmar/añadir campo `api_key` — no aparece en los docs actuales de la API pero es necesario para que el orchestrator pueda autenticarse con cada provider.

---

## Flujo de resolución de provider por request

```
1. ¿La conversación tiene provider_id?
     SÍ → usar conversation.provider_id + conversation.model_id
     NO → siguiente

2. ¿client_config tiene preferred_model_id?
     SÍ → usar config_manager.default_provider_id + client_config.preferred_model_id
     NO → siguiente

3. Usar config_manager.default_provider_id + provider.default_model_id
```

---

## Lo que NO cambia

- El protocolo WebSocket hacia el **cliente** (browser/app) en `/api/chat/ws` — sigue igual.
- El sistema de tools (registro con `@tool`, `ToolManager`, XML `<tool_call>` parsing).
- Auth de clientes via `X-Client-Key` → `validate_client_key()`.
- El endpoint `/api/quick` en su interfaz externa.
- Tests unitarios de `tool_parser`, `tool_manager` — no se tocan.
