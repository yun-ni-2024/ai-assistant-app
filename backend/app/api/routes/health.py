"""
Health check API routes.

Exposes a simple `/healthz` endpoint that validates the application is alive.
In later iterations we will expand this to check external dependencies like
database connectivity and LLM credentials.
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from ...core.settings import get_settings


router = APIRouter(tags=["health"]) 


@router.get("/healthz")
async def healthz() -> dict:
    """Return a minimal health report.

    Returns:
        dict: Health status with current UTC time.
    """

    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
    }


@router.get("/config")
async def config() -> dict:
    """Return non-sensitive runtime configuration for debugging.

    Secrets are masked.
    """

    s = get_settings()
    masked_key = (s.openai_api_key[:4] + "***") if s.openai_api_key else ""
    masked_or_key = (s.openrouter_api_key[:4] + "***") if getattr(s, "openrouter_api_key", "") else ""
    return {
        "llm_provider": s.llm_provider,
        "llm_streaming_enabled": s.llm_streaming_enabled,
        "openai_model": s.openai_model,
        "openai_api_key_present": bool(s.openai_api_key),
        "openai_api_key_masked": masked_key,
        "openrouter_base_url": getattr(s, "openrouter_base_url", ""),
        "openrouter_api_key_present": bool(getattr(s, "openrouter_api_key", "")),
        "openrouter_api_key_masked": masked_or_key,
    }


