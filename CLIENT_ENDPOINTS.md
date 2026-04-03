# JotaOrchestrator — Documentación de Endpoints para Clientes

## Tabla de Contenidos

1. [Autenticación y Tipos de Cliente](#autenticación-y-tipos-de-cliente)
2. [Mapa de Endpoints](#mapa-de-endpoints)
3. [Endpoints de Sistema](#endpoints-de-sistema)
   - `GET /` — Raíz
   - `GET /health` — Health Check
4. [Endpoints de Datos (`/api`)](#endpoints-de-datos-api)
   - `GET /api/models` — Listar modelos
   - `GET /api/conversations` — Listar conversaciones
   - `GET /api/conversations/{conversation_id}/messages` — Mensajes
   - `PATCH /api/conversations/{conversation_id}/model` — Cambiar modelo
5. [Endpoint QUICK (`/api/quick`)](#endpoint-quick-apiquick)
   - `POST /api/quick` — Comando rápido con streaming NDJSON
6. [Endpoint CHAT (`/api/chat`)](#endpoint-chat-apichat)
   - `WebSocket /api/chat/ws` — Chat en tiempo real
7. [Códigos de Error](#códigos-de-error)

---

## Autenticación y Tipos de Cliente

Todos los endpoints (excepto `/` y `/health`) requieren autenticación mediante `x-client-key`.

### Tipos de cliente

JotaOrchestrator distingue dos tipos de clientes. El tipo se configura en JotaDB al crear el cliente y se valida en cada petición:

| `client_type` | Endpoints permitidos | Caso de uso |
|---------------|---------------------|-------------|
| `chat` | `/api/chat/ws` + todos los de `/api/` | Aplicaciones de conversación, interfaces web |
| `quick` | `/api/quick` + todos los de `/api/` | Agentes de voz, domótica, comandos rápidos |

### Mecanismo de autenticación

- **Header HTTP:** `x-client-key: <tu_clave_de_cliente>`
- **Query param WebSocket:** `?x_client_key=<clave>` o `?client_key=<clave>` (para clientes que no soporten cabeceras personalizadas al abrir el WebSocket)
- La clave se valida en JotaDB en cada petición. Si es inválida o falta → `401 Unauthorized`.
- La validación devuelve internamente el `client_id` UUID, que aísla los datos de cada cliente.

> ⚠️ Las credenciales `ORCHESTRATOR_API_KEY` y `JOTA_DB_SK` son internas del servidor. El cliente nunca debe conocerlas.

---

## Mapa de Endpoints

```
GET  /                                              — Liveness check (sin auth)
GET  /health                                        — Health check profundo (sin auth)

GET  /api/models                                    — Lista modelos del Engine
GET  /api/conversations                             — Lista conversaciones del cliente
GET  /api/conversations/{conv_id}/messages          — Historial de mensajes
PATCH /api/conversations/{conv_id}/model            — Cambia modelo de conversación

POST /api/quick                                     — Comando rápido NDJSON (client_type: quick)

WS   /api/chat/ws                                   — Chat en tiempo real (client_type: chat)
```

---

## Endpoints de Sistema

### `GET /`

**Descripción:** Liveness check. No verifica conectividad interna.
**Autenticación:** Ninguna.

**Respuesta `200 OK`:**
```json
{
  "message": "Welcome to JotaOrchestrator",
  "environment": "development",
  "status": "online"
}
```

---

### `GET /health`

**Descripción:** Health check profundo. Comprueba la conectividad con JotaDB y el InferenceEngine.
**Autenticación:** Ninguna.

**Respuesta `200 OK`:**
```json
{
  "status": "ok",
  "components": {
    "inference_engine": "connected",
    "jota_db": "connected"
  }
}
```

**Respuesta `503 Service Unavailable`:**
```json
{
  "status": "degraded",
  "components": {
    "inference_engine": "disconnected",
    "jota_db": "connected"
  }
}
```

---

## Endpoints de Datos (`/api`)

Disponibles para ambos tipos de cliente (`chat` y `quick`). Todos requieren `x-client-key`.

### `GET /api/models`

**Descripción:** Devuelve la lista de modelos AI disponibles en el InferenceEngine. La respuesta se cachea en memoria durante `MODELS_CACHE_TTL` segundos (default: 5 minutos).

**Headers:**
| Header | Requerido |
|--------|-----------|
| `x-client-key` | ✅ |

**Respuesta `200 OK`:**
```json
{
  "status": "success",
  "models": [
    {
      "id": "llama-3-8b-instruct",
      "name": "Llama 3 8B Instruct",
      "size": "8B",
      "format": "gguf"
    }
  ]
}
```

> El esquema exacto de cada objeto depende del InferenceEngine. El Orchestrator retransmite la respuesta tal cual.

**Errores:**
| Código | Causa |
|--------|-------|
| `401` | `x-client-key` inválido o ausente |
| `503` | InferenceEngine no disponible |

---

### `GET /api/conversations`

**Descripción:** Lista las últimas N conversaciones del cliente autenticado. La identidad se resuelve desde la `x-client-key`.

**Query params:**
| Parámetro | Tipo | Default | Rango | Descripción |
|-----------|------|---------|-------|-------------|
| `limit` | int | `10` | 1–100 | Número de conversaciones |

**Headers:**
| Header | Requerido |
|--------|-----------|
| `x-client-key` | ✅ |

**Respuesta `200 OK`:**
```json
{
  "status": "success",
  "conversations": [
    {
      "id": "conv-uuid-1234",
      "client_id": "client-uuid-5678",
      "model_id": "llama-3-8b-instruct",
      "created_at": "2026-03-03T17:00:00Z",
      "updated_at": "2026-03-03T17:45:00Z"
    }
  ]
}
```

**Errores:**
| Código | Causa |
|--------|-------|
| `401` | `x-client-key` inválido o ausente |
| `500` | Error al consultar JotaDB |

---

### `GET /api/conversations/{conversation_id}/messages`

**Descripción:** Devuelve el historial de mensajes de una conversación ordenados cronológicamente. Filtrado por `client_id`.

**Parámetros de ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `conversation_id` | string | UUID de la conversación |

**Query params:**
| Parámetro | Tipo | Default | Rango | Descripción |
|-----------|------|---------|-------|-------------|
| `limit` | int | `50` | 1–1000 | Número de mensajes |

**Headers:**
| Header | Requerido |
|--------|-----------|
| `x-client-key` | ✅ |

**Respuesta `200 OK`:**
```json
{
  "status": "success",
  "messages": [
    {
      "id": "msg-uuid-0001",
      "conversation_id": "conv-uuid-1234",
      "role": "user",
      "content": "Busca información sobre energía solar",
      "created_at": "2026-03-03T17:00:10Z",
      "extra_data": null
    },
    {
      "id": "msg-uuid-0002",
      "conversation_id": "conv-uuid-1234",
      "role": "assistant",
      "content": "La energía solar es una fuente de energía renovable...",
      "created_at": "2026-03-03T17:00:18Z",
      "extra_data": {
        "model_id": "llama-3-8b-instruct"
      }
    },
    {
      "id": "msg-uuid-0003",
      "conversation_id": "conv-uuid-1234",
      "role": "tool",
      "content": "{\"results\": [{\"title\": \"Solar energy overview...\"}]}",
      "created_at": "2026-03-03T17:00:14Z",
      "extra_data": {
        "tool_name": "web_search",
        "execution_time": "1.45s"
      }
    }
  ]
}
```

**Roles de mensaje:**
- `user` — Mensaje del usuario.
- `assistant` — Respuesta del modelo. `extra_data.model_id` indica qué modelo la generó.
- `tool` — Resultado de una herramienta ejecutada. `extra_data.tool_name` y `extra_data.execution_time` proporcionan trazabilidad.
- `system` — Mensajes de sistema internos.

**Errores:**
| Código | Causa |
|--------|-------|
| `401` | `x-client-key` inválido o ausente |
| `500` | Error al consultar JotaDB |

---

### `PATCH /api/conversations/{conversation_id}/model`

**Descripción:** Actualiza el modelo AI asignado a una conversación. Valida que el `model_id` exista en el InferenceEngine antes de persistir (usando la caché de `/api/models`). Si el Engine no responde, permite el cambio igualmente (degraded mode).

**Parámetros de ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `conversation_id` | string | UUID de la conversación |

**Headers:**
| Header | Requerido |
|--------|-----------|
| `x-client-key` | ✅ |
| `Content-Type: application/json` | ✅ |

**Cuerpo:**
```json
{
  "model_id": "mistral-7b-v0.3"
}
```

**Respuesta `200 OK`:**
```json
{
  "status": "success",
  "conversation_id": "conv-uuid-1234",
  "model_id": "mistral-7b-v0.3"
}
```

**Errores:**
| Código | Causa |
|--------|-------|
| `401` | `x-client-key` inválido o ausente |
| `404` | `model_id` no existe en el Engine. La respuesta incluye la lista de modelos disponibles. |
| `500` | Error al persistir en JotaDB |

```json
// Ejemplo 404
{
  "detail": "Modelo 'gpt-9000' no encontrado. Disponibles: ['llama-3-8b-instruct', 'mistral-7b-v0.3']"
}
```

---

## Endpoint QUICK (`/api/quick`)

Para clientes de tipo `quick`. Optimizado para comandos de voz, domótica y respuestas cortas sin contexto persistente.

### `POST /api/quick`

**Descripción:** Ejecuta un comando rápido y devuelve la respuesta en streaming NDJSON (una línea JSON por evento). Stateless: no guarda mensajes en JotaDB. Optimizado para TTS (sin markdown, máximo 1-2 frases).

Soporta ejecución de herramientas (p. ej. `web_search`): en ese caso se emiten eventos `status` intermedios antes de la respuesta final.

**Headers:**
| Header | Requerido |
|--------|-----------|
| `x-client-key` | ✅ (debe ser `client_type: quick`) |
| `Content-Type: application/json` | ✅ |

**Cuerpo:**
```json
{
  "text": "¿Qué tiempo hace en Madrid?",
  "model_id": "llama-3-8b-instruct"
}
```

| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `text` | string | ✅ | — | Comando o pregunta del usuario |
| `model_id` | string | ❌ | `null` | Modelo a usar. Si `null`, usa el cargado actualmente en el Engine. |

**Respuesta: stream NDJSON**

La respuesta es un stream HTTP con `Content-Type: application/x-ndjson`. Cada línea es un objeto JSON terminado en `\n`:

| `type` | Descripción | Acción recomendada |
|--------|-------------|-------------------|
| `token` | Fragmento de texto de la respuesta | Acumular y reproducir por TTS |
| `status` | Estado intermedio (búsqueda, procesamiento) | Mostrar spinner o feedback visual |
| `error` | Error durante la ejecución | Mostrar al usuario, detener acumulación |

```
{"type": "token", "content": "En Madrid hay "}\n
{"type": "token", "content": "18 grados "}\n
{"type": "token", "content": "y cielo despejado."}\n
```

Ejemplo con ejecución de herramienta:
```
{"type": "status", "content": "Buscando información usando web_search..."}\n
{"type": "status", "content": "Búsqueda completada en 1.23s. Generando respuesta..."}\n
{"type": "status", "content": "Analizando resultados..."}\n
{"type": "token", "content": "Según los últimos datos, "}\n
{"type": "token", "content": "el tiempo en Madrid es soleado con 22 grados."}\n
```

**Errores HTTP (antes de iniciar el stream):**
| Código | Causa |
|--------|-------|
| `401` | `x-client-key` inválido o ausente |
| `403` | El `client_type` no es `quick` |
| `503` | InferenceEngine no disponible |

**Ejemplo de cliente JavaScript:**
```javascript
const response = await fetch("http://localhost:8000/api/quick", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "x-client-key": "mi_clave_quick"
  },
  body: JSON.stringify({ text: "Pon un timer de 5 minutos" })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const lines = decoder.decode(value).split("\n").filter(Boolean);
  for (const line of lines) {
    const msg = JSON.parse(line);
    if (msg.type === "token") {
      buffer += msg.content; // Acumular para TTS
    } else if (msg.type === "status") {
      console.log("Estado:", msg.content); // Feedback visual
    } else if (msg.type === "error") {
      console.error("Error:", msg.content);
    }
  }
}

speakTTS(buffer); // Reproducir respuesta acumulada
```

---

## Endpoint CHAT (`/api/chat`)

Para clientes de tipo `chat`. Conversación persistente multi-turno con streaming de tokens en tiempo real.

### `WebSocket /api/chat/ws`

**Descripción:** Conexión WebSocket persistente para chat en tiempo real. Soporta conversaciones multi-turno, cambio de modelo mid-session y ejecución de herramientas. La identidad del cliente se resuelve desde la `x-client-key`.

**URL de conexión:**
```
ws://host:port/api/chat/ws
  ?conversation_id=conv-uuid-1234    (opcional — retoma conversación existente)
  ?model_id=llama-3-8b-instruct      (opcional — modelo a usar)
  &x_client_key=<tu_clave>           (o via header x-client-key)
```

**Query params:**
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `conversation_id` | string | ❌ | UUID de conversación a retomar. Si se omite, se crea una nueva. |
| `model_id` | string | ❌ | Modelo AI para esta sesión. Si se omite, usa el cargado en el Engine. |
| `x_client_key` | string | ✅* | Clave de autenticación |
| `client_key` | string | ✅* | Alias alternativo para `x_client_key` |

> \* Al menos uno de `x-client-key` (header) o `x_client_key`/`client_key` (query) es obligatorio.

**Autenticación fallida:** el servidor cierra el WebSocket con código `4001` antes de hacer `accept`.
**Tipo de cliente incorrecto (`quick`):** cierra con código `4003`.

#### Ciclo de vida

```
APERTURA
  ├─ Validación de client_key                → close(4001) si falla
  ├─ Validación client_type != "quick"       → close(4003) si es quick
  ├─ Verificación Engine disponible          → close(1011) si no disponible
  ├─ Gestión de conversación                 → create_conversation() si no hay conversation_id
  ├─ ensure_session(client_id)              → cierra sesión previa del cliente si existía
  ├─ get_conversation_messages() + set_context() → inyecta historial en el Engine
  └─ websocket.accept()                      → conexión lista

BUCLE DE MENSAJES
  ├─ Recibir texto plano → inferencia + streaming de tokens
  └─ Recibir JSON con "type" → mensaje de control (ver abajo)

CIERRE
  └─ release_session(client_id)
```

#### Protocolo de mensajes

**Cliente → Servidor:**

| Formato | Descripción |
|---------|-------------|
| Texto plano | Mensaje del usuario. Ej: `"¿Cuándo fue la Revolución Francesa?"` |
| `{"type": "switch_model", "model_id": "..."}` | Cambia el modelo mid-session sin reconectar |

**Servidor → Cliente:**

| `type` | Descripción | Acción recomendada |
|--------|-------------|-------------------|
| `token` | Fragmento de texto de la respuesta | Acumular en buffer de respuesta |
| `status` | Estado intermedio (búsqueda, herramienta) | Mostrar spinner o texto de estado |
| `model_switched` | Confirmación de cambio de modelo | Actualizar UI con nuevo modelo |
| `error` | Error durante la sesión | Mostrar al usuario |

```json
// Ejemplos de frames del servidor
{"type": "token", "content": "La Revolución Francesa "}
{"type": "token", "content": "comenzó en 1789."}
{"type": "status", "content": "Buscando información actualizada..."}
{"type": "model_switched", "model_id": "mistral-7b-v0.3"}
{"type": "error", "message": "Inference Engine no disponible"}
```

**Cierre del WebSocket:**

| Código | Significado |
|--------|-------------|
| `4001` | Autenticación rechazada |
| `4003` | Tipo de cliente no permitido (`quick` intentando usar WS) |
| `1011` | Error interno del servidor |
| `1000` | Cierre normal iniciado por el cliente |

#### Ejemplo de cliente JavaScript

```javascript
const ws = new WebSocket(
  `ws://localhost:8000/api/chat/ws` +
  `?conversation_id=conv-uuid-1234` +
  `&x_client_key=mi_clave_chat`
);

let buffer = "";

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === "token") {
    buffer += msg.content;
    document.getElementById("response").textContent = buffer;
  } else if (msg.type === "status") {
    document.getElementById("status").textContent = msg.content;
  } else if (msg.type === "model_switched") {
    console.log("Modelo cambiado a:", msg.model_id);
  } else if (msg.type === "error") {
    console.error("Error del servidor:", msg.message);
  }
};

ws.onopen = () => {
  buffer = "";
  ws.send("Explícame la fotosíntesis");
};

// Cambiar modelo mid-session (sin reconectar)
function switchModel(modelId) {
  ws.send(JSON.stringify({ type: "switch_model", model_id: modelId }));
}

ws.onerror = (e) => console.error("WebSocket error:", e);
ws.onclose = (e) => console.log(`Cerrado: código ${e.code}`);
```

#### Gestión de contexto

- Al abrirse la conexión, el Orchestrator **recupera automáticamente** el historial de la `conversation_id` desde JotaDB e inyecta los mensajes como contexto en el InferenceEngine.
- Cada mensaje de usuario y cada respuesta del asistente se **persisten automáticamente** en JotaDB.
- Si la inferencia se interrumpe por desconexión abrupta, la respuesta parcial se guarda con el sufijo `[INTERRUPTED]`.
- El InferenceEngine mantiene **una sesión activa por `client_id`** a la vez. Abrir una nueva conexión con el mismo cliente cierra la sesión anterior.

---

## Códigos de Error

### HTTP

| Código | Causa típica |
|--------|-------------|
| `401 Unauthorized` | `x-client-key` ausente, expirado o inválido |
| `403 Forbidden` | Tipo de cliente no permitido en ese endpoint |
| `404 Not Found` | `model_id` no existe en el Engine |
| `500 Internal Server Error` | Fallo al persistir en JotaDB |
| `503 Service Unavailable` | InferenceEngine no disponible o timeout |

### WebSocket (códigos de cierre)

| Código | Significado |
|--------|-------------|
| `4001` | Autenticación rechazada |
| `4003` | Tipo de cliente no permitido |
| `1011` | Error interno del servidor |
| `1000` | Cierre normal |
