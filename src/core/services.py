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
