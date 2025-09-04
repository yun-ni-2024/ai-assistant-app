"""
Two-step SSE chat flow (minimal viable loop).

Step 1: POST /chat/create -> returns a stream_id and session_id
Step 2: GET  /chat/stream/{stream_id} -> server-sent events streaming tokens

This implementation mocks the assistant response by echoing the user message.
It also persists the user message and a placeholder assistant message record.
Later we will replace the mock with a real LLM streaming integration.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Path
from fastapi import Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...db.database import db_connection
from ...core.settings import get_settings
from ...services.openai_stream import OpenAIStreamClient


router = APIRouter(prefix="/chat", tags=["chat"]) 


class CreateChatRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Existing session id; if omitted, a new session is created")
    user_message: str = Field(min_length=1, description="User's message content")


class CreateChatResponse(BaseModel):
    stream_id: str
    session_id: str


_streams: Dict[str, str] = {}
_assistant_placeholders: Dict[str, str] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_session(session_id: Optional[str], title: str) -> str:
    """Create session if needed and return session_id."""
    if session_id:
        return session_id

    new_id = str(uuid4())
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
            (new_id, title, _now_iso()),
        )
    return new_id


def _insert_message(message_id: str, session_id: str, role: str, content: str) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (message_id, session_id, role, content, _now_iso()),
        )


@router.post("/create", response_model=CreateChatResponse)
async def create_chat(req: CreateChatRequest = Body(...)) -> CreateChatResponse:
    """Create a chat request and return a stream_id for SSE consumption."""

    # Create or reuse session
    title = req.user_message[:40] or "New Chat"
    session_id = _ensure_session(req.session_id, title)

    # Persist user message
    user_msg_id = str(uuid4())
    _insert_message(user_msg_id, session_id, "user", req.user_message)

    # Persist a placeholder assistant message, to be updated progressively by stream
    assistant_msg_id = str(uuid4())
    _insert_message(assistant_msg_id, session_id, "assistant", "")

    # Register stream payload source: Either real OpenAI or local echo fallback
    stream_id = str(uuid4())
    settings = get_settings()
    if settings.llm_provider in {"openai", "openrouter"} and settings.llm_streaming_enabled and (
        (settings.llm_provider == "openai" and settings.openai_api_key)
        or (settings.llm_provider == "openrouter" and settings.openrouter_api_key)
    ):
        # Store the input and assistant msg id for the stream handler
        _streams[stream_id] = req.user_message
        _assistant_placeholders[stream_id] = assistant_msg_id
    else:
        # Fallback to echo text streaming
        assistant_content = f"Echo: {req.user_message}"
        _streams[stream_id] = assistant_content
        _assistant_placeholders[stream_id] = assistant_msg_id

    return CreateChatResponse(stream_id=stream_id, session_id=session_id)


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_response_text(text: str):
    # Naive tokenization by words; yields small chunks to simulate streaming
    words = text.split()
    for i, word in enumerate(words):
        chunk = (" " if i > 0 else "") + word
        yield _sse_event({"delta": chunk, "done": False})
        await asyncio.sleep(0.02)
    yield _sse_event({"done": True})


@router.get("/stream/{stream_id}")
async def stream_chat(stream_id: str = Path(...)) -> StreamingResponse:
    """Stream the assistant response corresponding to the given stream_id.

    If LLM streaming is enabled and configured, stream from OpenAI; otherwise
    stream a local echo fallback. While streaming, append content into the
    placeholder assistant message in the database.
    """

    payload = _streams.pop(stream_id, None)
    assistant_msg_id = _assistant_placeholders.pop(stream_id, None)
    if payload is None or assistant_msg_id is None:
        raise HTTPException(status_code=404, detail="Invalid or expired stream_id")

    settings = get_settings()

    async def generator():
        accumulated = []
        try:
            if settings.llm_provider in {"openai", "openrouter"} and settings.llm_streaming_enabled and (
                (settings.llm_provider == "openai" and settings.openai_api_key)
                or (settings.llm_provider == "openrouter" and settings.openrouter_api_key)
            ):
                if settings.llm_provider == "openrouter":
                    # Use OpenAI-compatible SDK against OpenRouter base_url
                    headers = {}
                    if settings.openrouter_site_url:
                        headers["HTTP-Referer"] = settings.openrouter_site_url
                    if settings.openrouter_site_title:
                        headers["X-Title"] = settings.openrouter_site_title
                    client = OpenAIStreamClient(
                        api_key=settings.openrouter_api_key,
                        model=settings.openai_model or "google/gemini-2.5-flash-image-preview:free",
                        base_url=settings.openrouter_base_url,
                        extra_headers=headers or None,
                    )
                else:
                    client = OpenAIStreamClient()
                # Construct messages with simple system + user content for now
                messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": payload},
                ]
                async for delta in client.stream_chat(messages):
                    accumulated.append(delta)
                    yield _sse_event({"delta": delta, "done": False})
                await client.close()
            else:
                # Fallback echo stream
                async for evt in _stream_response_text(f"Echo: {payload}"):
                    # evt is already an SSE-formatted string
                    # But we still need to collect deltas to update DB
                    try:
                        data_start = evt.find("data: ") + len("data: ")
                        json_str = evt[data_start:].strip()
                        import json as _json

                        d = _json.loads(json_str)
                        if d.get("delta"):
                            accumulated.append(d["delta"])
                        yield evt
                    except Exception:
                        yield evt
        finally:
            # Persist accumulated assistant content to DB
            if accumulated:
                with db_connection() as conn:
                    conn.execute(
                        "UPDATE messages SET content = content || ? WHERE id = ?",
                        ("".join(accumulated), assistant_msg_id),
                    )
            # Signal completion
            yield _sse_event({"done": True})

    return StreamingResponse(generator(), media_type="text/event-stream")


