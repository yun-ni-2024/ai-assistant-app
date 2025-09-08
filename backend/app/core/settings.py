"""
Application settings and configuration helpers.

This module centralizes environment configuration to keep the rest of the
codebase simple and testable. It uses lightweight logic without external
dependencies to avoid early coupling. We can switch to Pydantic Settings later
if needed.
"""

import os
from functools import lru_cache
from typing import List
from dotenv import load_dotenv


class Settings:
    """Container for application configuration derived from environment.

    Attributes:
        cors_allow_origins: List of origins allowed by CORS middleware.
        openai_api_key: API key for OpenAI (may be empty during early dev).
        database_url: SQLite database URL string.
    """

    def __init__(self) -> None:
        # Load environment variables from a local .env file if present
        # This only affects current process and is safe for development use
        load_dotenv()
        # Comma-separated list of origins; default enables local dev origins
        cors_env = os.getenv(
            "CORS_ALLOW_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        )
        self.cors_allow_origins: List[str] = [o.strip() for o in cors_env.split(",") if o.strip()]

        # OpenAI API key (optional at this stage)
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

        # OpenAI model name (used when LLM is enabled)
        self.openai_model: str = os.getenv("OPENAI_MODEL", "")

        # Toggle to enable/disable LLM streaming integration (empty defaults to true)
        llm_stream_env = os.getenv("LLM_STREAMING_ENABLED", "")
        self.llm_streaming_enabled: bool = (llm_stream_env.lower() in {"1", "true", "yes"}) if llm_stream_env else True

        # LLM provider selection (empty defaults to "openai")
        self.llm_provider: str = (os.getenv("LLM_PROVIDER", "") or "openai").lower()

        # OpenRouter configuration (used when llm_provider == "openrouter")
        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        # Default base URL per OpenRouter docs
        self.openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        # Optional headers for rankings (safe to leave empty)
        self.openrouter_site_url: str = os.getenv("OPENROUTER_SITE_URL", "")
        self.openrouter_site_title: str = os.getenv("OPENROUTER_SITE_TITLE", "")

        # Google Custom Search Engine configuration
        self.google_cse_api_key: str = os.getenv("GOOGLE_CSE_API_KEY", "")
        self.google_cse_engine_id: str = os.getenv("GOOGLE_CSE_ENGINE_ID", "")

        # SQLite database path (will be used later)
        db_path = os.getenv("SQLITE_DB_PATH", "./data/app.db")
        # Use a file-based SQLite URL to simplify future integration
        self.database_url: str = f"sqlite:///{db_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Caching avoids repeatedly parsing environment variables and allows easy
    overrides in tests by clearing the cache.
    """

    return Settings()


