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


@router.get("/debug/sessions")
async def debug_sessions() -> dict:
    """Debug endpoint to view all sessions and messages in database."""
    from ...db.database import db_connection
    
    with db_connection() as conn:
        # Get all sessions
        sessions_cursor = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        sessions = [dict(row) for row in sessions_cursor.fetchall()]
        
        # Get all messages
        messages_cursor = conn.execute("SELECT * FROM messages ORDER BY created_at ASC")
        messages = [dict(row) for row in messages_cursor.fetchall()]
        
        # Group messages by session
        sessions_with_messages = []
        for session in sessions:
            session_messages = [msg for msg in messages if msg['session_id'] == session['id']]
            sessions_with_messages.append({
                **session,
                'messages': session_messages
            })
    
    return {
        "sessions_count": len(sessions),
        "messages_count": len(messages),
        "sessions": sessions_with_messages
    }


