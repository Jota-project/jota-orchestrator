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