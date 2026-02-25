# Visión Técnica: Jota - El Cerebro Centralizado

Este documento define la arquitectura, los estándares y la hoja de ruta para **Jota**, un ecosistema de asistente virtual diseñado para la persistencia, la conciencia contextual y la eficiencia.

---

## 1. Resumen de Infraestructura

Jota funciona como una **arquitectura backend distribuida** orquestada centralmente.

### Módulos Núcleo (Core)
* **Jota-Orchestrator (Python/FastAPI):** El centro nervioso. Actúa como un **Enrutador Cognitivo** que gestiona la lógica de negocio, la memoria y la orquestación.
    - **Estado Actual**: Integrado con Inference Center (WebSocket) y lógica de sesiones asíncrona.
* **Inference Center (C++):** Motor de inferencia remoto.
* **Transcription API (C++):** Servidor de streaming STT.

---

## 2. Arquitectura de Orquestación

### Flujo de Inferencia End-to-End (Implementado)
El orquestador actúa como un proxy inteligente y gestor de estado:

1. **Entrada de Usuario**: Recibida vía WebSocket (`/ws/chat/{user_id}`) o REST.
2. **Controlador (`JotaController`)**:
   - Recupera el historial de **Memoria**.
   - Invoca al cliente de inferencia.
3. **Cliente de Inferencia (`InferenceClient`)**:
   - Gestiona la conexión WebSocket persistente con el motor C++.
   - **Stateless**: Delega el estado de la sesión en `MemoryManager` (JotaDB).
   - Autentica (`auth`), crea sesiones (`create_session`) y las cierra explícitamente (`close_session`) bajo demanda para no saturar los límites de recursos.
   - Despacha streams de tokens concurrentes usando colas asíncronas (`asyncio.Queue`).
   - Soporta **Exponential Backoff** para reconexión automática.
4. **Streaming**: Los tokens fluyen en tiempo real de `InferenceCenter` -> `Orchestrator` -> `User` sin bloqueo.

### Gestión de Memoria Unificada (JotaDB)
* **Persistencia Externa:** El orquestador no almacena estado. Todo reside en JotaDB.
* **Contexto de Sesión:** Mapeo dinámico `conversación_id` <-> `inference_session_id` gestionado por JotaDB.
* **Deep Health Check:** Monitoreo activo de conexiones a JotaDB y Motor de Inferencia (`/health`).

---

## 3. Plan de Implementación

### Fase 1: El Puente de Datos (✅ Completado)
* [x] Configurar `InferenceClient` con protocolo asíncrono y autenticación.
* [x] Implementar streaming de tokens en tiempo real (Async Generators).
* [x] API WebSocket para clientes finales.

### Fase 2: Lógica de Decisión y Routing (🚧 En Progreso)
* Desarrollar el `IntentRouter` para distinguir comandos de conversación.
* Estructura de "Tool Calling" para domótica.

### Fase 3: Interfaz y Observabilidad
* Web Dashboard para control y métricas.

---

## 4. Estándares
* **WebSockets (WS/WSS):** Estándar comunicación streaming.
* **AsyncIO:** Núcleo de concurrencia en Python para manejar I/O intenso sin bloquear.
* **Seguridad:** Autenticación por Tokens en capa de transporte.