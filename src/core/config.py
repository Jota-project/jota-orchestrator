from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "JotaOrchestrator"
    APP_ENV: str = "development"
    DEBUG: bool = False

    TRANSCRIPTION_SERVICE_URL: str

    INFERENCE_SERVICE_URL: str

    # Internal Services Authentication
    ORCHESTRATOR_ID: str       # ID del Orchestrator para servicios internos
    ORCHESTRATOR_API_KEY: str  # API Key del Orchestrator para servicios internos

    # ---------------------------------------------------------------------------
    # Agent personality
    # ---------------------------------------------------------------------------
    AGENT_BASE_SYSTEM_PROMPT: str = (
        "You are Jota, a helpful and friendly AI assistant. "
        "Respond concisely and naturally. Keep answers short — "
        "use a few sentences unless the user explicitly asks for detail. "
        "Match the language the user writes in."
    )
    TOOL_FOLLOWUP_PROMPT: str = (
        "The tool has provided the results. "
        "Please answer the original user query using this information."
    )

    # ---------------------------------------------------------------------------
    # Inference parameters
    # ---------------------------------------------------------------------------
    INFERENCE_DEFAULT_TEMP: float = 0.7
    INFERENCE_TOKEN_TIMEOUT: float = 30.0     # seconds to wait for next token
    INFERENCE_LOAD_MODEL_TIMEOUT: float = 30.0
    INFERENCE_LIST_MODELS_TIMEOUT: float = 10.0
    INFERENCE_SESSION_TIMEOUT: float = 5.0
    MODELS_CACHE_TTL: float = 300.0           # seconds model list is cached

    # ---------------------------------------------------------------------------
    # Tool output limits
    # ---------------------------------------------------------------------------
    TOOL_MAX_OUTPUT_CHARS: int = 4000         # cap before truncation in tool_manager
    MEMORY_TOOL_OUTPUT_CAP: int = 1000        # cap when injecting tool results into context (conservative for quick/voice flow)

    # ---------------------------------------------------------------------------
    # Tool Config
    # ---------------------------------------------------------------------------
    TAVILY_API_KEY: Optional[str] = None
    TAVILY_SEARCH_DEPTH: str = "basic"
    TAVILY_MAX_RESULTS: int = 5
    TAVILY_TIMEOUT: float = 6.0               # max seconds for a Tavily search before aborting
    ENABLE_GBNF_GRAMMAR: bool = False         # Deprecated: Use system prompt instead

    # ---------------------------------------------------------------------------
    # JotaDB Integration
    # ---------------------------------------------------------------------------
    JOTA_DB_URL: str
    JOTA_DB_SK: str            # Server Key - sent as Bearer token for DB access
    JOTA_DB_TIMEOUT: float = 10.0

    # ---------------------------------------------------------------------------
    # CORS
    # ---------------------------------------------------------------------------
    CORS_ORIGINS: list[str] = ["*"]

    # SSL/TLS & Validation
    SSL_VERIFY: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
