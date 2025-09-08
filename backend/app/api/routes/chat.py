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
from ...services.tools import get_tool_registry


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


async def _extract_tool_parameters(client, tool_name: str, user_message: str, conversation_context: str) -> dict:
    """Extract tool parameters using tool-specific prompts."""
    try:
        # Get tool registry
        tool_registry = get_tool_registry()
        
        # Check if tool is enabled
        if not tool_registry.is_tool_enabled(tool_name):
            print(f"🔧 Tool {tool_name} is not enabled")
            return {}
        
        # Create tool instance
        tool_instance = tool_registry.create_tool_instance(tool_name)
        if not tool_instance:
            print(f"🔧 Failed to create tool instance for {tool_name}")
            return {}
        
        # Get tool-specific parameter extraction prompt
        parameter_prompt = tool_instance.get_parameter_extraction_prompt()
        
        # Format the prompt with actual values
        analysis_prompt = parameter_prompt.format(
            user_message=user_message,
            conversation_context=conversation_context
        )
        
        # Build LLM messages
        analysis_messages = [
            {"role": "system", "content": "You are a parameter extraction assistant. Always respond with valid JSON. Consider conversation context and user intent."},
            {"role": "user", "content": analysis_prompt}
        ]
        
        # Call LLM to extract parameters
        analysis_response = await client._client.chat.completions.create(
            model=client.model,
            messages=analysis_messages,
            max_tokens=200,
            temperature=0.1
        )
        
        analysis_text = analysis_response.choices[0].message.content.strip()
        print(f"🔧 LLM parameter extraction response for {tool_name}: {analysis_text}")
        
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
        parameters = json.loads(analysis_text)
        
        print(f"🔧 Extracted parameters for {tool_name}: {parameters}")
        return parameters
        
    except Exception as e:
        print(f"🔧 Error extracting parameters for {tool_name}: {str(e)}")
        return {}


async def _analyze_tool_needs(client, conversation_history: list, user_message: str) -> str:
    """Intelligently analyze user message and determine the most appropriate tool to use."""
    try:
        # Get tool registry
        tool_registry = get_tool_registry()
        
        # Get available tools from registry
        available_tools = tool_registry.get_available_tools()
        if not available_tools:
            print("🔧 No tools available")
            return "none"
        
        # Build tool selection prompt using tool classes' own descriptions
        tools_info = []
        for tool_name, tool_info in available_tools.items():
            # Get the actual tool instance to access its description methods
            tool_instance = tool_registry.get_tool_instance(tool_name)
            if tool_instance and hasattr(tool_instance, 'get_tool_selection_prompt'):
                tools_info.append(tool_instance.get_tool_selection_prompt())
            else:
                # Fallback to basic info if tool doesn't have the new methods
                tools_info.append(f"""
Tool Name: {tool_info['name']}
Description: {tool_info['description']}
Use Cases: {', '.join(tool_info['use_cases'])}
""")
        
        analysis_prompt = f"""You are an intelligent tool selector. Analyze the user's message and select the most appropriate tool to answer their question.

Available Tools:
{chr(10).join(tools_info)}

Conversation Context:
{_format_conversation_context(conversation_history)}

User Message: "{user_message}"

Selection Guidelines:
1. Carefully analyze the user's core need and intent
2. Consider the conversation context when interpreting pronouns like "it", "this", "that"
3. Choose the tool that can best address the user's specific question
4. If no tool is appropriate for the question, choose "none"

Please respond in this exact JSON format:
{{
    "tool": "tool_name" or "none",
    "reason": "brief explanation of why this tool is most appropriate"
}}"""

        # Use the same client to analyze
        analysis_messages = [
            {"role": "system", "content": "You are an intelligent tool selector that analyzes user messages to determine the most appropriate tool. Always respond with valid JSON. Consider conversation context and user intent."},
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
        print(f"🔧 LLM intelligent tool selection response: {analysis_text}")
        
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
        reason = analysis_data.get("reason", "No reason provided")
        
        # Validate that the selected tool is available
        if tool != "none" and tool not in available_tools:
            print(f"🔧 Selected tool {tool} is not available, falling back to none")
            tool = "none"
        
        print(f"🔧 Selected tool: {tool}, Reason: {reason}")
        
        return tool
        
    except Exception as e:
        print(f"🔧 Error in intelligent tool selection: {str(e)}")
        # If LLM analysis fails, don't use tools to avoid incorrect behavior
        return "none"


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


async def _generate_system_message(tool: str, tool_result: str, user_message: str) -> str:
    """Generate system message using tool-specific template."""
    try:
        # Get tool registry
        tool_registry = get_tool_registry()
        
        # Check if tool is enabled
        if not tool_registry.is_tool_enabled(tool):
            print(f"🔧 Tool {tool} is not enabled")
            return ""
        
        # Create tool instance
        tool_instance = tool_registry.create_tool_instance(tool)
        if not tool_instance:
            print(f"🔧 Failed to create tool instance for {tool}")
            return ""
        
        # Get tool-specific system message template
        system_message_template = tool_instance.get_system_message_template()
        
        # Format the template with actual values
        system_message = system_message_template.format(
            tool_result=tool_result,
            user_message=user_message
        )
        
        return system_message
        
    except Exception as e:
        print(f"🔧 Error generating system message for {tool}: {str(e)}")
        return f"Tool result processing failed: {str(e)}"


async def _execute_tool_and_format_result(tool: str, parameters: dict, session_id: str, message_id: str) -> str:
    """Execute a tool and format the result for AI context."""
    try:
        # Get tool registry
        tool_registry = get_tool_registry()
        
        # Check if tool is enabled
        if not tool_registry.is_tool_enabled(tool):
            print(f"🔧 Tool {tool} is not enabled")
            return ""
        
        # Create tool instance
        tool_instance = tool_registry.create_tool_instance(tool)
        if not tool_instance:
            print(f"🔧 Failed to create tool instance for {tool}")
            return ""
        
        # Execute the tool
        result = await tool_instance.execute(parameters)
        
        # Display results in backend console for debugging
        if tool == "fetch":
            print(f"📄 ===== Fetch Results Details =====")
            print(f"📄 URL: {result.get('url', 'N/A')}")
            print(f"📄 Title: {result.get('title', 'N/A')}")
            print(f"📄 Content Length: {len(result.get('content', ''))}")
            print(f"📄 Status Code: {result.get('status_code', 'N/A')}")
            print(f"📄 Content Type: {result.get('content_type', 'N/A')}")
            print(f"📄 Links Found: {len(result.get('links', []))}")
            print(f"📄 ===== Content Preview =====")
            content_preview = result.get('content', '')[:300]
            print(f"📄 {content_preview}{'...' if len(result.get('content', '')) > 300 else ''}")
            print(f"📄 ===== Fetch Results Complete =====")
            
        elif tool == "search":
            print(f"🔍 ===== Search Results Details =====")
            print(f"🔍 Query: {result.get('query', 'N/A')}")
            print(f"🔍 Total Results: {len(result.get('results', []))}")
            print(f"🔍 Search Time: {result.get('search_time', 'N/A')} seconds")
            print(f"🔍 API Source: {result.get('api_source', 'N/A')}")
            print(f"🔍 ===== Top 10 Results =====")
            
            for i, search_result in enumerate(result.get('results', [])[:10], 1):
                print(f"🔍 【{i}】{search_result.get('title', 'N/A')}")
                print(f"🔍 URL: {search_result.get('url', 'N/A')}")
                print(f"🔍 Snippet: {search_result.get('snippet', 'N/A')[:100]}...")
                print(f"🔍 Source: {search_result.get('source', 'N/A')}")
                print(f"🔍 Published: {search_result.get('published_date', 'N/A')}")
                print(f"🔍 ---")
            
            print(f"🔍 ===== Search Results Complete =====")
        
        # Return raw result as JSON string for system message template
        import json
        return json.dumps(result, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"🔧 Error executing {tool} tool: {str(e)}")
        return f"Tool execution failed: {str(e)}"




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
                tool = await _analyze_tool_needs(client, conversation_history, user_message)
                
                if tool != "none":
                    print(f"🔧 LLM determined tool needed: {tool}")
                    
                    try:
                        # Extract tool-specific parameters using tool's prompt
                        conversation_context = _format_conversation_context(conversation_history)
                        parameters = await _extract_tool_parameters(client, tool, user_message, conversation_context)
                        
                        # Execute the selected tool and get formatted result
                        tool_result = await _execute_tool_and_format_result(
                            tool, parameters, session_id, assistant_msg_id
                        )
                        
                        if tool_result:
                            # Generate system message using tool-specific template
                            system_message = await _generate_system_message(tool, tool_result, user_message)
                            
                            if system_message:
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


