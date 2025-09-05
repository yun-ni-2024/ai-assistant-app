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
_stream_sessions: Dict[str, str] = {}  # Map stream_id to session_id


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
    _stream_sessions[stream_id] = session_id  # Store session_id for conversation history
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


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str = Path(...)) -> list:
    """Get all messages for a specific session."""
    with db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        )
        messages = []
        for row in cursor.fetchall():
            message = dict(row)
            # 重命名字段以匹配前端期望
            message['timestamp'] = message.pop('created_at')
            messages.append(message)
    return messages


@router.get("/stream/{stream_id}")
async def stream_chat(stream_id: str = Path(...)) -> StreamingResponse:
    """Stream the assistant response corresponding to the given stream_id.

    If LLM streaming is enabled and configured, stream from OpenAI; otherwise
    stream a local echo fallback. While streaming, append content into the
    placeholder assistant message in the database.
    """

    payload = _streams.pop(stream_id, None)
    assistant_msg_id = _assistant_placeholders.pop(stream_id, None)
    session_id = _stream_sessions.pop(stream_id, None)
    if payload is None or assistant_msg_id is None or session_id is None:
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
                
                # Get conversation history for context (limit to last 10 messages to avoid token limits)
                with db_connection() as conn:
                    # Get the most recent 10 messages, then sort them in chronological order
                    cursor = conn.execute(
                        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 10",
                        (session_id,)
                    )
                    recent_messages = [{"role": row["role"], "content": row["content"]} for row in cursor.fetchall()]
                    
                    # Reverse to get chronological order (oldest first)
                    all_messages = list(reversed(recent_messages))
                    
                    # Filter out the last assistant placeholder message if it's empty
                    conversation_history = []
                    for i, msg in enumerate(all_messages):
                        # Skip the last message if it's an empty assistant message
                        if i == len(all_messages) - 1 and msg["role"] == "assistant" and not msg["content"].strip():
                            continue
                        conversation_history.append(msg)
                
                # Construct messages with conversation history
                messages = [
                    {"role": "system", "content": "You are a helpful AI assistant. When responding to users:\n\n1. Always start your response as a complete, independent statement\n2. Do not use leading characters like '?' or empty lines at the beginning\n3. Be conversational and helpful, but maintain your AI identity\n4. You have access to the full conversation history and should maintain context\n5. Respond naturally and engage with the user's questions or requests\n6. If the user asks about something from previous messages, reference it appropriately\n7. Keep responses clear, informative, and well-structured"},
                    *conversation_history,  # Include conversation history
                ]
                
                print(f"🔍 Sending to AI - Session: {session_id}, Messages count: {len(messages)}")
                for i, msg in enumerate(messages):
                    print(f"🔍 Message {i}: {msg['role']} - {msg['content'][:100]}...")
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


