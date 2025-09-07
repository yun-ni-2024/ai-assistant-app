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
import re
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
from ...services.mcp_client import get_mcp_client, MCPToolError


router = APIRouter(prefix="/chat", tags=["chat"]) 


class CreateChatRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Existing session id; if omitted, a new session is created")
    user_message: str = Field(min_length=1, description="User's message content")
    system_prompt: Optional[str] = Field(default=None, description="Custom system prompt; if omitted, uses default")


class CreateChatResponse(BaseModel):
    stream_id: str
    session_id: str


_streams: Dict[str, str] = {}
_assistant_placeholders: Dict[str, str] = {}
_stream_sessions: Dict[str, str] = {}  # Map stream_id to session_id
_stream_system_prompts: Dict[str, str] = {}  # Map stream_id to system_prompt


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _analyze_search_need(client, user_message: str) -> tuple[bool, str]:
    """Use LLM to analyze if user message needs search and generate search query."""
    try:
        # Create a simple analysis prompt
        analysis_prompt = f"""Analyze the following user message and determine if it requires real-time information or current data that would benefit from a web search.

User message: "{user_message}"

Please respond in this exact JSON format:
{{
    "needs_search": true/false,
    "search_query": "optimized search query if needed, or empty string if not needed",
    "reason": "brief explanation of why search is or isn't needed"
}}

Consider these factors:
- Questions about current events, news, weather, stock prices, recent developments
- Requests for up-to-date information that changes frequently
- Questions about "today", "latest", "recent", "current" topics in any language
- General knowledge questions that don't need current data should NOT trigger search
- Consider the language of the user's question and adapt the search query accordingly

Examples:
- "What's the weather like today?" → needs_search: true, search_query: "weather today"
- "What is artificial intelligence?" → needs_search: false, search_query: ""
- "Latest AI news" → needs_search: true, search_query: "latest AI news"
- "What is 1+1?" → needs_search: false, search_query: ""
- "¿Cómo está el clima hoy?" → needs_search: true, search_query: "clima hoy"
- "Quelles sont les dernières nouvelles?" → needs_search: true, search_query: "dernières nouvelles"
"""

        # Use the same client to analyze
        analysis_messages = [
            {"role": "system", "content": "You are an AI assistant that analyzes user messages to determine if they need web search. Always respond with valid JSON. Consider the language of the user's message and adapt your analysis accordingly."},
            {"role": "user", "content": analysis_prompt}
        ]
        
        # Get analysis response
        analysis_response = await client._client.chat.completions.create(
            model=client.model,
            messages=analysis_messages,
            max_tokens=200,
            temperature=0.1
        )
        
        analysis_text = analysis_response.choices[0].message.content.strip()
        print(f"🔍 LLM analysis response: {analysis_text}")
        
        # Parse JSON response
        import json
        analysis_data = json.loads(analysis_text)
        
        needs_search = analysis_data.get("needs_search", False)
        search_query = analysis_data.get("search_query", "").strip()
        
        # Add current date context to search query if needed
        if needs_search and search_query:
            now = datetime.now()
            current_year = now.year
            current_month = now.month
            current_day = now.day
            
            if "today" in search_query.lower() or "今日" in search_query or "今天" in search_query:
                search_query = f"{search_query} {current_year}-{current_month:02d}-{current_day:02d}"
            elif "latest" in search_query.lower() or "recent" in search_query.lower() or "最新" in search_query or "最近" in search_query:
                search_query = f"{search_query} {current_year}-{current_month:02d}"
        
        return needs_search, search_query
        
    except Exception as e:
        print(f"🔍 Error in search analysis: {str(e)}")
        # If LLM analysis fails, don't search to avoid incorrect behavior
        return False, ""


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
        # Store the input, system prompt, and assistant msg id for the stream handler
        _streams[stream_id] = req.user_message
        _assistant_placeholders[stream_id] = assistant_msg_id
        _stream_system_prompts[stream_id] = req.system_prompt
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
            # Rename fields to match frontend expectations
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
    system_prompt = _stream_system_prompts.pop(stream_id, None)
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
                # Use custom system prompt if provided, otherwise use default
                default_system_prompt = """You are a helpful AI assistant. When responding to users:

1. Always start your response as a complete, independent statement
2. Be conversational and helpful, but maintain your AI identity
3. You have access to the full conversation history and should maintain context
4. Respond naturally and engage with the user's questions or requests
5. If the user asks about something from previous messages, reference it appropriately
6. Keep responses clear, informative, and well-structured

IMPORTANT: If you see search results in the system context, these are REAL-TIME information I searched for you. You MUST use this information to provide accurate, up-to-date answers. Do NOT say you cannot provide specific data when search results clearly contain relevant information. Extract and present the key facts, numbers, and details from the search results. ACTIVELY embed source URLs as inline references throughout your response using markdown links. Adapt your language to match the user's question language and naturally incorporate the search results into your response."""
                
                messages = [
                    {"role": "system", "content": system_prompt or default_system_prompt},
                    *conversation_history,  # Include conversation history
                ]
                
                print(f"🔍 Sending to AI - Session: {session_id}, Messages count: {len(messages)}")
                print(f"🔍 System prompt: {system_prompt[:100] if system_prompt else 'None'}...")
                for i, msg in enumerate(messages):
                    print(f"🔍 Message {i}: {msg['role']} - {msg['content'][:100]}...")
                
                # First, check if user message needs search using LLM
                user_message = messages[-1]["content"] if messages else ""
                needs_search, search_query = await _analyze_search_need(client, user_message)
                
                if needs_search and search_query:
                    print(f"🔍 LLM determined search needed: {search_query}")
                    
                    try:
                        # Execute search first
                        mcp_client = get_mcp_client()
                        search_result = await mcp_client.execute_tool(
                            tool_name="search",
                            parameters={"query": search_query},
                            session_id=session_id,
                            message_id=assistant_msg_id
                        )
                        
                        # Format search results
                        search_results = search_result["result"]
                        search_summary = f"📰 Latest Information Search Results (Query: {search_results['query']}):\n\n"
                        
                        # Display search results in backend console for debugging
                        print(f"🔍 ===== Search Results Details =====")
                        print(f"🔍 Query: {search_results['query']}")
                        print(f"🔍 Total Results: {len(search_results['results'])}")
                        print(f"🔍 Search Time: {search_results.get('search_time', 'N/A')} seconds")
                        print(f"🔍 API Source: {search_results.get('api_source', 'N/A')}")
                        print(f"🔍 ===== Top 5 Results =====")
                        
                        for i, result in enumerate(search_results['results'][:5], 1):
                            print(f"🔍 【{i}】{result['title']}")
                            print(f"🔍 URL: {result['url']}")
                            print(f"🔍 Snippet: {result['snippet'][:100]}...")
                            print(f"🔍 Source: {result.get('source', 'N/A')}")
                            print(f"🔍 Published: {result.get('published_date', 'N/A')}")
                            print(f"🔍 ---")
                            
                            # Format for AI context
                            search_summary += f"📄 {result['title']}\n"
                            search_summary += f"🔗 {result['url']}\n"
                            search_summary += f"📝 {result['snippet']}\n\n"
                        
                        print(f"🔍 ===== Search Results Formatting Complete =====")
                        
                        # Add search results to conversation context as system message
                        messages.append({
                            "role": "system", 
                            "content": f"""I have searched for relevant information for you. Here are the search results:

{search_summary}

Please answer the user's question based on these search results: {user_message}

IMPORTANT: These search results contain REAL-TIME, CURRENT information that directly addresses the user's question. You MUST use this information to provide a comprehensive answer. Do NOT say you cannot provide specific data when the search results clearly contain relevant information.

EXAMPLE of proper link embedding: Instead of "According to Yahoo Finance, the market rose 2%", write "According to [Yahoo Finance](https://finance.yahoo.com), the market rose 2%". Always embed links directly in your text using [link text](URL) format.

Guidelines:
1. Extract and present ALL relevant information from the search results - don't leave out important details
2. Look for specific data, numbers, facts, and concrete information in the snippets that directly relate to the user's question
3. If multiple sources mention the same information, present it as confirmed data
4. ACTIVELY embed URLs as inline references throughout your response using markdown link format: [descriptive text](URL)
5. When mentioning specific data, facts, or information, immediately follow with the source link in the same sentence
6. Make URLs an integral part of your response, not just an afterthought - weave them naturally into the text
7. If the search results contain specific data, numbers, or facts, present them clearly and prominently with their source links
8. At the end of your response, provide a separate list of all relevant URLs with appropriate section heading in the user's language
9. Use natural language to describe the format - for example, in English you might say "Related links:" or "Sources:", in Chinese you might say "相关链接：" or "参考资料：", etc.
10. Adapt all formatting, headings, and labels to match the user's language and cultural context

Please respond in the same language as the user's question and adapt all formatting accordingly."""
                        })
                        
                        print(f"🔍 Search completed, found {len(search_results['results'])} results")
                        print(f"🔍 ===== Search Complete, Results Injected into AI Context =====")
                        
                    except Exception as e:
                        error_msg = f"Search process encountered an error: {str(e)}"
                        messages.append({
                            "role": "system", 
                            "content": f"Search failed: {error_msg}. Please respond based on your knowledge."
                        })
                        print(f"🔍 Search failed: {str(e)}")
                
                # Stream AI response and check for tool calls
                response_text = ""
                async for delta in client.stream_chat(messages):
                    response_text += delta
                    accumulated.append(delta)
                    yield _sse_event({"delta": delta, "done": False})
                
                await client.close()
                
                # Check if AI response contains search tool call
                if "[SEARCH:" in response_text and "]" in response_text:
                    try:
                        # Extract search query
                        search_match = re.search(r'\[SEARCH:\s*([^\]]+)\]', response_text)
                        if search_match:
                            search_query = search_match.group(1).strip()
                            
                            # Optimize search query for current information
                            now = datetime.now()
                            current_year = now.year
                            current_month = now.month
                            current_day = now.day
                            
                            # Add current date context to search query for better results
                            # Support multiple languages for time-sensitive queries
                            today_keywords = ["today", "今日", "今天", "heute", "aujourd'hui", "hoy"]
                            recent_keywords = ["latest", "recent", "最新", "最近", "neueste", "récent", "reciente"]
                            
                            if any(keyword in search_query.lower() for keyword in today_keywords):
                                search_query = f"{search_query} {current_year}-{current_month:02d}-{current_day:02d}"
                            elif any(keyword in search_query.lower() for keyword in recent_keywords):
                                search_query = f"{search_query} {current_year}-{current_month:02d}"
                            
                            print(f"🔍 Detected search request: {search_query}")
                            
                            # Execute search tool
                            mcp_client = get_mcp_client()
                            search_result = await mcp_client.execute_tool(
                                tool_name="search",
                                parameters={"query": search_query},
                                session_id=session_id,
                                message_id=assistant_msg_id
                            )
                            
                            # Format search results for AI
                            search_results = search_result["result"]
                            search_summary = f"\n\n[Search Results]\n"
                            search_summary += f"Search Query: {search_results['query']}\n"
                            search_summary += f"Found {len(search_results['results'])} results:\n\n"
                            
                            for i, result in enumerate(search_results['results'][:5], 1):  # Show top 5 results
                                search_summary += f"{i}. {result['title']}\n"
                                search_summary += f"   {result['url']}\n"
                                search_summary += f"   {result['snippet']}\n\n"
                            
                            # Add search results to accumulated content
                            accumulated.append(search_summary)
                            
                            # Stream the search results
                            for line in search_summary.split('\n'):
                                yield _sse_event({"delta": line + '\n', "done": False})
                                await asyncio.sleep(0.01)  # Small delay for streaming effect
                            
                            print(f"🔍 Search completed, found {len(search_results['results'])} results")
                            
                    except MCPToolError as e:
                        error_msg = f"\n\n[Search Error] Unable to execute search: {str(e)}\n"
                        accumulated.append(error_msg)
                        yield _sse_event({"delta": error_msg, "done": False})
                        print(f"🔍 Search failed: {str(e)}")
                    except Exception as e:
                        error_msg = f"\n\n[Search Error] Error occurred during search process: {str(e)}\n"
                        accumulated.append(error_msg)
                        yield _sse_event({"delta": error_msg, "done": False})
                        print(f"🔍 Search error: {str(e)}")
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


