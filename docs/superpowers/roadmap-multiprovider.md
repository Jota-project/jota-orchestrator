# Roadmap — Multi-Provider Refactor

**Plan de referencia:** [2026-04-09-multiprovider-openai.md](superpowers/plans/2026-04-09-multiprovider-openai.md)  
**Rama:** `feat/multiprovider-openai`

---

## Visión general

```
Fase 1          Fase 2          Fase 3          Fase 4
FUNDAMENTOS  →  CORE SWITCH  →  ENDPOINTS    →  CIERRE
(puras adiciones)  (switch real)   (surface API)   (cleanup + PR)

Sin riesgo      Alto riesgo     Riesgo medio    Sin riesgo
Sistema intacto Sistema nuevo   Endpoints live  Código viejo eliminado
```

---

## Prerequisito externo (jota-db) — antes de Fase 2

Estos cambios deben estar desplegados en jota-db **antes** de que Fase 2 pueda probarse end-to-end:

- [ ] `Conversations` — añadir campo `provider_id` (UUID, nullable FK a `InferenceProvider`)
- [ ] `InferenceProvider` — confirmar/añadir campo `api_key`
- [ ] Verificar que `GET /internal/providers` devuelve `api_key` en la respuesta
- [ ] Verificar que `POST /chat/conversations` acepta `provider_id`

> Fase 1 se puede hacer completamente en paralelo con estos cambios de DB.

---

## Fase 1 — Fundamentos (completada)
**Objetivo:** Añadir toda la infraestructura nueva sin tocar nada existente. El sistema sigue funcionando exactamente igual que antes.

**Tasks del plan:** 1, 3, 4, 5, 6, 7

| Task | Descripción | Ficheros clave |
|---|---|---|
| 1 | Dependencies | `requirements.txt` |
| 3 | MemoryManager internal/ methods | `src/core/memory.py` |
| 4 | ConfigManager | `src/core/config_manager.py` |
| 5 | BaseProvider + mocks | `src/services/providers/base.py`, `anthropic.py`, `gemini.py` |
| 6 | OpenAICompatibleAdapter | `src/services/providers/openai_compatible.py` |
| 7 | ProviderManager | `src/services/providers/manager.py` |

**Estado del sistema al final de Fase 1:**
- ✅ Todos los tests nuevos pasan
- ✅ La app arranca y funciona igual que antes (WS inference sin cambios)
- ✅ `src/services/providers/` existe pero no está conectado al runtime
- ✅ Se puede hacer PR parcial para revisión de código sin riesgo de regresión

**Gate de salida:**
```bash
pytest tests/unit/test_config_manager.py tests/unit/test_provider_manager.py \
       tests/unit/test_openai_adapter.py tests/unit/test_memory_manager_internal.py -v
# → todos pasan
```

---

## Fase 2 — Core Switch
**Objetivo:** Conectar el nuevo sistema al controller. Este es el cambio disruptivo — el `InferenceClient` WebSocket deja de ser la ruta de inferencia.

**Prerequisito:** Cambios de jota-db desplegados.

**Tasks del plan:** 2, 8, 9

| Task | Descripción | Ficheros clave |
|---|---|---|
| 2 | Limpiar config.py (eliminar settings obsoletos) | `src/core/config.py` |
| 8 | Actualizar services.py + controller/core.py | `src/core/services.py`, `core.py` |
| 9 | Refactorizar controller/input.py + eliminar models.py | `src/core/controller/input.py` |

**⚠️ Nota:** En este punto `websocket.py` sigue importando `inference_client` de services, que ya no existe. La app **no arrancará** hasta completar Fase 3. Esta fase y la siguiente deben hacerse en la misma sesión de trabajo o en ramas separadas.

**Estado del sistema al final de Fase 2:**
- ✅ Controller usa `ProviderManager` para inferencia
- ✅ `models.py` eliminado (sin carga de modelo, sin reconexión WS)
- ⚠️ `websocket.py` y `quick.py` rotos (importan inference_client que ya no existe)
- ⚠️ La app no arranca hasta Fase 3

**Gate de entrada:**
- jota-db tiene `provider_id` en conversations
- jota-db tiene `api_key` en providers

---

## Fase 3 — Endpoints y API surface
**Objetivo:** Actualizar los endpoints para usar el nuevo sistema. Al final de esta fase la app vuelve a funcionar end-to-end.

**Tasks del plan:** 10, 11, 12

| Task | Descripción | Ficheros clave |
|---|---|---|
| 10 | Refactorizar websocket.py | `src/api/chat/websocket.py` |
| 11 | Refactorizar quick.py | `src/api/quick.py` |
| 12 | Startup bloqueante en main.py | `src/main.py` |

**Estado del sistema al final de Fase 3:**
- ✅ App arranca correctamente (startup bloqueante — falla duro si DB no responde)
- ✅ `/api/chat/ws` funciona con el nuevo sistema de providers
- ✅ `/api/quick` funciona con el nuevo sistema de providers
- ✅ `/health` devuelve estado de cada provider
- ✅ Tool calls funcionan en ambos endpoints
- ⚠️ `src/services/inference/` sigue en disco (pendiente cleanup)

**Gate de salida — smoke test manual:**
```bash
# Arrancar con jota-db real
python -m uvicorn src.main:app --reload
# → "JotaOrchestrator listo para recibir peticiones"
# → /health devuelve providers con estado
# → WebSocket chat funciona end-to-end
# → /api/quick responde con tokens
```

---

## Fase 4 — Cierre
**Objetivo:** Eliminar código muerto, limpiar tests, abrir PR.

**Tasks del plan:** 13, 14, 15

| Task | Descripción | Ficheros clave |
|---|---|---|
| 13 | Eliminar `src/services/inference/` | directorio completo |
| 14 | Actualizar suite de tests | `tests/conftest.py`, eliminar tests WS |
| 15 | PR | GitHub |

**Estado del sistema al final de Fase 4:**
- ✅ Sin código muerto
- ✅ Suite de tests limpia y pasando
- ✅ PR abierto con descripción completa
- ✅ `.env` puede limpiarse de `INFERENCE_SERVICE_URL`

**Gate de salida:**
```bash
pytest tests/unit/ tests/integration/ -v
# → todos pasan
```

---

## Resumen de riesgos por fase

| Fase | Riesgo | Reversibilidad | Prerequisito externo |
|---|---|---|---|
| 1 | Bajo — solo adiciones | Alta — git revert sin impacto | No |
| 2+3 | Alto — switch completo | Media — rama separada | **Sí — jota-db** |
| 4 | Bajo — solo cleanup | Alta | No |

---

## Orden de trabajo recomendado

```
Día 1:  Fase 1 completa  → PR parcial para revisión (opcional)
        Coordinar cambios de jota-db en paralelo

Día 2:  jota-db desplegado
        Fase 2 + Fase 3 en la misma sesión (no dejar la app rota entre fases)

Día 3:  Smoke tests + ajustes
        Fase 4 → PR final
```

---

## Comandos de referencia rápida

```bash
# Arrancar suite de tests por fase
pytest tests/unit/test_config_manager.py tests/unit/test_provider_manager.py \
       tests/unit/test_openai_adapter.py tests/unit/test_memory_manager_internal.py -v  # Fase 1

pytest tests/unit/ -v                          # Fase 2+3
pytest tests/unit/ tests/integration/ -v       # Fase 4

# Verificar import completo del sistema (post Fase 3)
ORCHESTRATOR_ID=x ORCHESTRATOR_API_KEY=x JOTA_DB_URL=x JOTA_DB_SK=x \
python -c "import src.main; print('OK')"
```
