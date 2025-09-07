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


async def _analyze_tool_needs(client, conversation_history: list, user_message: str) -> tuple[str, dict]:
    """Analyze user message and determine which tool to use with priority: fetch > search."""
    try:
        # Create analysis prompt for tool selection with conversation context
        analysis_prompt = f"""Analyze the following user message and determine which tool to use. Available tools: fetch (for URLs), search (for real-time info).

Conversation context:
{_format_conversation_context(conversation_history)}

Current user message: "{user_message}"

Please respond in this exact JSON format:
{{
    "tool": "fetch" or "search" or "none",
    "parameters": {{"url": "..."}} or {{"query": "..."}} or {{}},
    "reason": "brief explanation of tool choice"
}}

Priority rules:
1. FETCH (highest priority): If message contains a URL (http:// or https://) or mentions "this webpage", "this link", "analyze this page"
2. SEARCH (medium priority): If asking for real-time info, news, weather, current events, "latest", "today", "recent"
3. NONE (lowest priority): General knowledge questions that don't need tools

IMPORTANT: 
1. Consider the conversation context when interpreting pronouns like "it", "this", "that", etc.
2. ALWAYS generate search queries in the SAME LANGUAGE as the user's message. If user writes in Chinese, generate Chinese search query. If user writes in English, generate English search query.

Examples:
- "Analyze this webpage: https://example.com" → tool: "fetch", parameters: {{"url": "https://example.com"}}
- "What's the weather today?" → tool: "search", parameters: {{"query": "weather today"}}
- "今天天气怎么样？" → tool: "search", parameters: {{"query": "今天天气"}}
- "What is AI?" → tool: "none", parameters: {{}}
- "什么是人工智能？" → tool: "none", parameters: {{}}
- "This link: https://news.com" → tool: "fetch", parameters: {{"url": "https://news.com"}}
- "这个链接：https://news.com" → tool: "fetch", parameters: {{"url": "https://news.com"}}
- "Latest AI news" → tool: "search", parameters: {{"query": "latest AI news"}}
- "AI最新新闻" → tool: "search", parameters: {{"query": "AI最新新闻"}}
- "Tell me about its latest news" (after discussing AI) → tool: "search", parameters: {{"query": "latest AI news"}}
- "告诉我关于它的最新新闻" (after discussing AI) → tool: "search", parameters: {{"query": "AI最新新闻"}}
- "Please fetch https://example.com and search for AI news" → tool: "fetch", parameters: {{"url": "https://example.com"}} (fetch has priority)
"""

        # Use the same client to analyze
        analysis_messages = [
            {"role": "system", "content": "You are an AI assistant that analyzes user messages to determine which tool to use. Always respond with valid JSON. Consider the conversation context and the language of the user's message. Pay special attention to pronouns and references that need to be resolved based on the conversation history. CRITICAL: Always generate search queries in the same language as the user's message."},
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
        print(f"🔧 LLM tool analysis response: {analysis_text}")
        
        # Clean up the response text (remove markdown code blocks if present)
        if analysis_text.startswith("```json"):
            analysis_text = analysis_text[7:]  # Remove ```json
        if analysis_text.startswith("```"):
            analysis_text = analysis_text[3:]   # Remove ```
        if analysis_text.endswith("```"):
            analysis_text = analysis_text[:-3]  # Remove trailing ```
        analysis_text = analysis_text.strip()
        
        # Parse JSON response
        import json
        analysis_data = json.loads(analysis_text)
        
        tool = analysis_data.get("tool", "none")
        parameters = analysis_data.get("parameters", {})
        
        # Keep search query as-is without adding date context
        # Adding dates can mislead search engines and reduce result relevance
        
        return tool, parameters
        
    except Exception as e:
        print(f"🔧 Error in tool analysis: {str(e)}")
        # If LLM analysis fails, don't use tools to avoid incorrect behavior
        return "none", {}


def _format_conversation_context(conversation_history: list) -> str:
    """Format conversation history for tool analysis context."""
    if not conversation_history:
        return "No previous conversation context."
    
    context_lines = []
    for i, msg in enumerate(conversation_history[-6:], 1):  # Last 6 messages for context
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "user":
            context_lines.append(f"User: {content}")
        elif role == "assistant":
            context_lines.append(f"Assistant: {content[:200]}{'...' if len(content) > 200 else ''}")
        elif role == "system":
            context_lines.append(f"System: {content[:100]}{'...' if len(content) > 100 else ''}")
    
    return "\n".join(context_lines) if context_lines else "No previous conversation context."


async def _execute_tool_and_format_result(tool: str, parameters: dict, session_id: str, message_id: str) -> str:
    """Execute a tool and format the result for AI context."""
    try:
        mcp_client = get_mcp_client()
        result = await mcp_client.execute_tool(
            tool_name=tool,
            parameters=parameters,
            session_id=session_id,
            message_id=message_id
        )
        
        if tool == "fetch":
            # Display fetch results in backend console for debugging
            fetch_results = result["result"]
            print(f"📄 ===== Fetch Results Details =====")
            print(f"📄 URL: {fetch_results.get('url', 'N/A')}")
            print(f"📄 Title: {fetch_results.get('title', 'N/A')}")
            print(f"📄 Content Length: {len(fetch_results.get('content', ''))}")
            print(f"📄 Status Code: {fetch_results.get('status_code', 'N/A')}")
            print(f"📄 Content Type: {fetch_results.get('content_type', 'N/A')}")
            print(f"📄 Links Found: {len(fetch_results.get('links', []))}")
            print(f"📄 ===== Content Preview =====")
            content_preview = fetch_results.get('content', '')[:300]
            print(f"📄 {content_preview}{'...' if len(fetch_results.get('content', '')) > 300 else ''}")
            print(f"📄 ===== Fetch Results Formatting Complete =====")
            return _format_fetch_result(fetch_results)
        elif tool == "search":
            # Display search results in backend console for debugging
            search_results = result["result"]
            print(f"🔍 ===== Search Results Details =====")
            print(f"🔍 Query: {search_results.get('query', 'N/A')}")
            print(f"🔍 Total Results: {len(search_results.get('results', []))}")
            print(f"🔍 Search Time: {search_results.get('search_time', 'N/A')} seconds")
            print(f"🔍 API Source: {search_results.get('api_source', 'N/A')}")
            print(f"🔍 ===== Top 10 Results =====")
            
            for i, search_result in enumerate(search_results.get('results', [])[:10], 1):
                print(f"🔍 【{i}】{search_result.get('title', 'N/A')}")
                print(f"🔍 URL: {search_result.get('url', 'N/A')}")
                print(f"🔍 Snippet: {search_result.get('snippet', 'N/A')[:100]}...")
                print(f"🔍 Source: {search_result.get('source', 'N/A')}")
                print(f"🔍 Published: {search_result.get('published_date', 'N/A')}")
                print(f"🔍 ---")
            
            print(f"🔍 ===== Search Results Formatting Complete =====")
            return _format_search_result(search_results)
        else:
            return ""
            
    except Exception as e:
        print(f"🔧 Error executing {tool} tool: {str(e)}")
        return f"Tool execution failed: {str(e)}"


def _format_fetch_result(fetch_data: dict) -> str:
    """Format fetch tool result for AI context."""
    url = fetch_data.get("url", "")
    title = fetch_data.get("title", "Unknown")
    content = fetch_data.get("content", "")
    summary = fetch_data.get("summary", "")
    links = fetch_data.get("links", [])
    
    formatted_result = f"""📄 Webpage Content Retrieved:

**Source**: {url}
**Title**: {title}

**Content**:
{content}

"""
    
    # Only include links if they are relevant and not too many
    if links and len(links) <= 5:
        formatted_result += "**Additional Links Found**:\n"
        for i, link in enumerate(links, 1):
            formatted_result += f"{i}. {link['text']} - {link['url']}\n"
        formatted_result += "\n"
    
    return formatted_result


def _format_search_result(search_data: dict) -> str:
    """Format search tool result for AI context."""
    query = search_data.get("query", "")
    results = search_data.get("results", [])
    
    formatted_result = f"""📰 Search Results (Query: {query}):

"""
    
    for i, result in enumerate(results[:10], 1):  # Show top 10 results
        title = result.get("title", "")
        url = result.get("url", "")
        snippet = result.get("snippet", "")
        
        formatted_result += f"**{i}. {title}**\n"
        formatted_result += f"🔗 {url}\n"
        formatted_result += f"📝 {snippet}\n\n"
    
    return formatted_result


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
        # Get the next sequence_id for this session
        cursor = conn.execute(
            "SELECT COALESCE(MAX(sequence_id), 0) + 1 FROM messages WHERE session_id = ?",
            (session_id,)
        )
        sequence_id = cursor.fetchone()[0]
        
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, content, created_at, sequence_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, session_id, role, content, _now_iso(), sequence_id),
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
            "SELECT id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY sequence_id ASC",
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
                    # Get the most recent 10 messages, ordered by sequence_id for stable ordering
                    cursor = conn.execute(
                        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY sequence_id DESC LIMIT 10",
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
                
                # Analyze user message to determine which tool to use
                user_message = messages[-1]["content"] if messages else ""
                # Pass conversation history (excluding system messages) for context
                conversation_history = [msg for msg in messages if msg.get("role") != "system"]
                tool, parameters = await _analyze_tool_needs(client, conversation_history, user_message)
                
                if tool != "none":
                    print(f"🔧 LLM determined tool needed: {tool} with parameters: {parameters}")
                    
                    try:
                        # Execute the selected tool and get formatted result
                        tool_result = await _execute_tool_and_format_result(
                            tool, parameters, session_id, assistant_msg_id
                        )
                        
                        if tool_result:
                            # Add tool result to conversation context as system message
                            if tool == "fetch":
                                system_message = f"""I have retrieved webpage content for you. Here is the information:

{tool_result}

Please answer the user's question based on this webpage content: {user_message}

IMPORTANT: This webpage content contains REAL information that directly addresses the user's question. You MUST use this information to provide a comprehensive answer. Do NOT say you cannot provide specific data when the webpage content clearly contains relevant information.

Guidelines for webpage content analysis:
1. Extract and present ALL relevant information from the webpage content
2. Look for specific data, numbers, facts, and concrete information that directly relate to the user's question
3. Focus on analyzing and summarizing the content rather than citing sources
4. If the webpage content contains specific data, numbers, or facts, present them clearly and prominently
5. Provide a comprehensive analysis based on the webpage content
6. If there are related links in the content, you may mention them naturally but don't over-emphasize them
7. Adapt your response to match the user's language and cultural context

Please respond in the same language as the user's question and provide a thorough analysis of the webpage content."""
                            elif tool == "search":
                                system_message = f"""I have searched for relevant information for you. Here are the search results:

{tool_result}

Please answer the user's question based on these search results: {user_message}

IMPORTANT: These search results contain REAL-TIME, CURRENT information that directly addresses the user's question. You MUST use this information to provide a comprehensive answer. Do NOT say you cannot provide specific data when the search results clearly contain relevant information.

Guidelines:
1. CAREFULLY FILTER search results - only include information that is DIRECTLY relevant to the user's specific question
2. IGNORE search results that are not related to the user's question, even if they appear in the search results
3. Focus on extracting specific data, numbers, facts, and concrete information that directly relate to the user's question
4. If multiple sources mention the same relevant information, present it as confirmed data
5. ACTIVELY embed URLs as inline references throughout your response using markdown link format: [descriptive text](URL)
6. When mentioning specific data, facts, or information, immediately follow with the source link in the same sentence
7. Make URLs an integral part of your response, not just an afterthought - weave them naturally into the text
8. If the search results contain specific data, numbers, or facts, present them clearly and prominently with their source links
9. At the end of your response, provide a separate list of all relevant URLs with appropriate section heading in the user's language
10. Use natural language to describe the format - for example, in English you might say "Related links:" or "Sources:", in Chinese you might say "相关链接：" or "参考资料：", etc.
11. Adapt all formatting, headings, and labels to match the user's language and cultural context

CONTENT FILTERING RULES:
- Only include information that is DIRECTLY relevant to the user's specific question
- IGNORE search results that are not related to the user's question, even if they appear in the search results
- Don't feel obligated to use all search results - quality and relevance are more important than quantity
- If search results are mostly irrelevant, acknowledge this and provide what relevant information you can find
- Examples: If user asks about finance but results include entertainment news, ignore the entertainment; if user asks about technology but results include unrelated topics, ignore the unrelated topics

CRITICAL LINK EMBEDDING RULES:
- NEVER add source references as separate phrases at the end of sentences like "[来源]" or "来源："
- NEVER add source names as standalone text after the main content
- ALWAYS integrate links naturally into the flow of your sentences
- Use descriptive link text that makes sense in context
- Links should feel like natural parts of your writing, not afterthoughts
- When mentioning information, weave the source link into the sentence structure
- Make your writing flow naturally - readers should not notice the links are "added on"
- Think of links as integral parts of your narrative, not citations to be appended

Please respond in the same language as the user's question and adapt all formatting accordingly."""
                            
                            messages.append({
                                "role": "system", 
                                "content": system_message
                            })
                            
                            print(f"🔧 {tool} tool completed, result injected into AI context")
                        
                    except Exception as e:
                        error_msg = f"{tool} tool execution encountered an error: {str(e)}"
                        messages.append({
                            "role": "system", 
                            "content": f"Tool execution failed: {error_msg}. Please respond based on your knowledge."
                        })
                        print(f"🔧 {tool} tool failed: {str(e)}")
                
                # Stream AI response
                response_text = ""
                async for delta in client.stream_chat(messages):
                    response_text += delta
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


