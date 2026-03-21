# Visión Técnica: Jota - El Cerebro Centralizado

Este documento define la arquitectura, los estándares y la hoja de ruta para **Jota**, un ecosistema de asistente virtual diseñado para la persistencia, la conciencia contextual y la eficiencia.

---

## 1. Resumen de Infraestructura

Jota funciona como una **arquitectura backend distribuida** orquestada centralmente.

### Módulos Núcleo (Core)
* **Jota-Orchestrator (Python/FastAPI):** El centro nervioso. Actúa como un **Enrutador Cognitivo** que gestiona la lógica de negocio, la memoria y la orquestación.
* **Inference Center (C++):** Motor de inferencia remoto (`llama.cpp`).
* **Transcription API (C++):** Servidor de streaming STT.

---

## 2. Arquitectura de Orquestación

### Flujo de Inferencia End-to-End

El orquestador actúa como un proxy inteligente y gestor de estado:

1. **Entrada de Usuario**: Recibida vía WebSocket (`/ws/chat/{user_id}`) o REST.
2. **Controlador (`JotaController`)**:
   - Verifica que el modelo correcto esté cargado en el Engine (`_ensure_model_loaded`).
   - Construye el system prompt combinando `AGENT_BASE_SYSTEM_PROMPT` + instrucciones de tools filtradas por rol del cliente.
   - Invoca al cliente de inferencia.
   - Procesa el stream con detección dual de tool calls (ver abajo).
3. **Cliente de Inferencia (`InferenceClient`)**:
   - Gestiona la conexión WebSocket persistente con el motor C++.
   - **Stateless**: Delega el estado de la sesión en `MemoryManager` (JotaDB).
   - Autentica, crea sesiones y las cierra explícitamente bajo demanda.
   - Despacha streams de tokens concurrentes usando colas asíncronas (`asyncio.Queue`).
   - Soporta **Exponential Backoff** para reconexión automática.
   - **Detección primaria de `<tool_call>`**: Intercepta tokens del stream que contienen el tag XML de tool calling, parsea el JSON embebido y emite un dict estructurado `{"type": "tool_call", "payload": {...}}` al controlador.
4. **Streaming**: Los tokens fluyen en tiempo real de `InferenceCenter` → `Orchestrator` → `User` sin bloqueo.
5. **Tool Execution Loop**:
   - El controlador detecta un tool call (vía dict del parser o vía text fallback).
   - Ejecuta la herramienta, guarda el resultado en JotaDB con `role="tool"`.
   - Recarga el contexto completo e inicia una re-inferencia con el historial actualizado.

### Detección Dual de Tool Calls

```
InferenceEngine → [token stream] → InferenceClient
                                        │
                          ┌─────────────┴─────────────────┐
                          │ ¿token contiene <tool_call>?   │
                          │                                 │
                     sí ──┤                                 ├── no
                          │                                 │
                   yield dict                         yield str token
                {"type":"tool_call"}                        │
                          │                          JotaController
                          │                          acumula en buffer
                          │                          extract_tool_calls()
                          │                                 │
                          └─────────────┬───────────────────┘
                                  tool_executed
                                  re-inference
```

**Path primario** (`inference.py`): opera a nivel de token, intercepta el bloque completo antes de que llegue al controlador. Más eficiente — elimina el tag del stream antes de enviarlo.

**Path fallback** (`controller.py`): acumula texto en `pre_tool_thinking[]` y ejecuta `extract_tool_calls()` en cada nuevo chunk. Captura bloques que el parser de streaming partiera entre tokens en casos edge.

### Gestión de Memoria Unificada (JotaDB)

* **Persistencia Externa**: El orquestador no almacena estado. Todo reside en JotaDB.
* **Roles de mensaje**: `user`, `assistant`, `tool`, `system`.
  - `assistant` con `metadata.thinking=true` → pensamiento pre-herramienta (guardado, no visible al usuario).
  - `tool` con `metadata.tool_name` + `metadata.execution_time` → trazabilidad completa.
* **Cap de contexto**: Los mensajes `tool` se truncan a `MEMORY_TOOL_OUTPUT_CAP` (default 1500 chars) al inyectarse como contexto para evitar saturación del modelo.

---

## 3. Arquitectura de Configuración

### Capas de abstracción

```
src/core/constants.py     ← Constantes de protocolo (no env-overridable)
                             TOOL_CALL_OPEN/CLOSE, INTERRUPTED_MARKER, etc.
                             Única fuente de verdad para tags y markers de texto.

src/core/config.py        ← Settings operacionales (pydantic-settings, override via .env)
                             Prompts, timeouts, límites, parámetros de tools.

src/tools/*.py            ← Implementaciones concretas de tools (@tool decorator)
src/utils/tool_parser.py  ← Utilidades de parseo reutilizables
```

**Principio**: Ningún string literal operacional aparece fuera de `constants.py` o `config.py`. Los módulos solo referencian constantes/settings.

### `src/core/constants.py`

| Constante | Valor | Usada en |
|-----------|-------|---------|
| `TOOL_CALL_OPEN` | `<tool_call>` | `inference.py`, `tool_manager.py`, `tool_parser.py` |
| `TOOL_CALL_CLOSE` | `</tool_call>` | idem |
| `INTERRUPTED_MARKER` | `" [INTERRUPTED]"` | `inference.py` |
| `TOOL_OUTPUT_TRUNCATED_MARKER` | `"\n...[OUTPUT TRUNCATED]"` | `tool_manager.py` |
| `CONTEXT_TRUNCATED_MARKER` | `"\n...[TRUNCATED TO PREVENT CONTEXT SATURATION]"` | `memory.py` |

### `src/utils/tool_parser.py`

| Función | Descripción |
|---------|-------------|
| `extract_tool_calls(text)` | Parsea todos los bloques `<tool_call>` del texto. Valida nombre y arguments. Retorna `list[dict]`. |
| `validate_tool_call(tc, tools)` | Valida que el nombre existe en tools disponibles y arguments es dict. |
| `remove_tool_calls_from_text(text)` | Elimina todos los bloques `<tool_call>` y colapsa blancos sobrantes. |

---

## 4. Plan de Implementación

### Fase 1: El Puente de Datos (✅ Completado)
* [x] Configurar `InferenceClient` con protocolo asíncrono y autenticación.
* [x] Implementar streaming de tokens en tiempo real (Async Generators).
* [x] API WebSocket para clientes finales.

### Fase 2: Lógica de Decisión y Tool Calling (✅ Completado)
* [x] Implementar `ToolManager` con decorador `@tool` y generación automática de esquemas JSON.
* [x] Integrar Tavily Web Search como herramienta asíncrona.
* [x] Integrar cliente MCP (Model Context Protocol) para herramientas externas.
* [x] Implementar bucle de re-inferencia recursivo (modelo → herramienta → re-inferencia).
* [x] Tokens de estado (`{"type": "status"}`) por WebSocket para indicadores de progreso.
* [x] Filtrado de "pensamientos" pre-herramienta (guardados en DB, ocultos al usuario).

### Fase 2.5: Seguridad y Sandboxing (✅ Completado)
* [x] Sistema de permisos por rol (`public` / `user` / `admin`) integrado con `client_id`.
* [x] Truncado de salida de herramientas (`TOOL_MAX_OUTPUT_CHARS`) para prevención de Context Overflow.
* [x] Filtrado dinámico: el modelo solo ve herramientas accesibles al cliente actual.
* [x] Cap de contexto para resultados de tools (`MEMORY_TOOL_OUTPUT_CAP`).

### Fase 2.6: Migración a System Prompt + Hardening (✅ Completado)
* [x] Migrar tool calling de gramáticas GBNF a system prompt estructurado.
* [x] Deprecar `generate_gbnf_grammar()` — disponible como escape hatch con `force_grammar=True`.
* [x] Registro automático de tools en startup vía `src/tools/__init__.py`.
* [x] Detección dual: parser de streaming (primario) + text fallback con `tool_parser` (secundario).
* [x] Extraer todos los magic strings a `constants.py` (protocolo) y `config.py` (operacional).
* [x] `src/utils/tool_parser.py`: utilidades reutilizables de parseo y validación.
* [x] Fix bug: `TAVILY_API_KEY` opcional para no romper startup sin key configurada.
* [x] Fix bug: `basicConfig` logging para que logs de `src.*` lleguen a gunicorn.
* [x] Dockerfile: workers=1 (múltiples workers rompen el WebSocket compartido con InferenceEngine).

### Fase 3: Interfaz y Observabilidad
* [ ] Web Dashboard para control y métricas.
* [ ] Soporte multi-tool por inferencia (actualmente se procesa el primero detectado).

---

## 5. Estándares

* **WebSockets (WS/WSS):** Estándar de comunicación streaming.
* **AsyncIO:** Núcleo de concurrencia en Python para manejar I/O intenso sin bloquear.
* **Seguridad:** Autenticación por tokens en capa de transporte + permisos por rol en herramientas.
* **System Prompt:** Mecanismo primario de tool calling. El modelo recibe instrucciones estructuradas con lista de tools disponibles, formato exacto y ejemplos reales.
* **Sin magic strings:** Toda constante de protocolo en `constants.py`, toda variable operacional en `config.py`.
* ~~GBNF Grammars~~ *(deprecated)* — Reemplazado por system prompt.
