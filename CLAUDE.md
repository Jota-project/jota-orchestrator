# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git Workflow

**`main` does not accept direct pushes.** All work must go through a PR:

1. Create a branch for your changes: `git checkout -b feat/my-change`
2. Commit and push the branch: `git push -u origin feat/my-change`
3. Open a PR to `main` via `gh pr create`
4. After the PR is merged, delete the branch: `git branch -d feat/my-change && git push origin --delete feat/my-change`

Commits follow Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`, etc.) — semantic-release uses them to auto-generate versions and CHANGELOG.

## Commands

```bash
# Run all tests (unit + integration only — stress tests are excluded from CI)
.venv/bin/pytest tests/unit/ tests/integration/ -v

# Run a single test file
.venv/bin/pytest tests/unit/test_tool_parser.py -v

# Run a single test by name
.venv/bin/pytest tests/unit/test_inference_client.py::test_create_session -v

# Start dev server
python3 -m uvicorn src.main:app --reload

# Docker
docker compose up --build
```

Tests require these env vars (can be dummies for unit/integration tests):
`TRANSCRIPTION_SERVICE_URL`, `INFERENCE_SERVICE_URL`, `ORCHESTRATOR_ID`, `ORCHESTRATOR_API_KEY`, `JOTA_DB_URL`, `JOTA_DB_SK`

## Architecture

JotaOrchestrator is the central hub of the Jota ecosystem. It sits between clients (WebSocket, HTTP) and two external services: **jota-inference** (llama.cpp engine, WebSocket) and **jota-transcription** (STT server). Persistence is handled by **JotaDB** (external REST service).

### Request flows

**WebSocket chat** (`/api/chat/ws/{user_id}`): Client connects → `JotaController.handle_input()` orchestrates the inference loop → streams tokens back. The controller publishes events to `event_bus` for decoupled processing.

**Quick/voice** (`POST /api/quick`): Stateless, single-turn. Returns NDJSON stream optimized for TTS (no markdown, max 2 sentences). Supports tool calls inline.

**REST data** (`/api/*`): Read-only — lists models, conversations, messages. PATCH to change a conversation's model.

### Singleton services (`src/core/services.py`)

Three singletons are instantiated at import time and shared across all requests:
- `memory_manager` — wraps JotaDB HTTP calls
- `inference_client` — persistent WebSocket to jota-inference with auto-reconnect
- `jota_controller` — orchestration logic, subscribes to `event_bus`

Importing `src.tools` (done at startup) triggers `@tool` decorator registrations — this is the only way tools are loaded.

### InferenceClient (`src/services/inference/`)

Split across three mixins composed in `InferenceClient`:
- `InferenceConnectionMixin` (`connection.py`) — WebSocket lifecycle, auth via HTTP headers (`X-Client-ID`, `X-API-Key`), exponential backoff reconnect loop started by `connect()` as a background task, message dispatch table in `_read_loop()`
- `InferenceSessionMixin` (`session_manager.py`) — `create_session()`, `ensure_session()` (closes previous before creating new), `release_session()`
- `InferenceClient` (`client.py`) — `infer()`, `list_models()`, `load_model()`

`connect()` is non-blocking — it starts `_connection_loop()` as an asyncio task. Use `verify_connection(timeout)` to wait for auth before sending requests.

### Controller (`src/core/controller/`)

`JotaController` composes two mixins:
- `JotaModelMixin` (`models.py`) — model loading/switching logic
- `JotaInputMixin` (`input.py`) — main inference pipeline: build prompt → call infer → parse tool calls → execute tools → re-infer if needed

### Tool system (`src/tools/`, `src/core/tool_manager.py`)

Register tools with `@tool` decorator. `ToolManager` generates JSON schemas automatically and enforces role-based access. Tool results are parsed from LLM output by `src/utils/tool_parser.py` using XML-style `<tool_call>` tags.

### Settings (`src/core/config.py`)

`Settings` is instantiated as a module-level singleton — it reads from `.env` and environment variables at import time. All required fields (no defaults) will raise a `ValidationError` on startup if missing. In tests, inject them via `env:` in the pytest step or `monkeypatch.setenv`.
