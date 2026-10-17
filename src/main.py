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
