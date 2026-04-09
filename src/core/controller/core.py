"""
Core controller for the Orchestrator.

This module exports the main Orchestrator controller (`JotaController`) which unifies
model management and inference input handling by inheriting from mixins.
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