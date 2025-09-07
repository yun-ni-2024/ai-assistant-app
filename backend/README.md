# Backend (FastAPI)

This backend exposes a FastAPI application for the AI Assistant with MCP tool integration.

## Quickstart (Windows PowerShell)

1. Create and activate virtual environment

```powershell
# From the backend directory
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies

```powershell
pip install -r requirements.txt
```

3. Run the dev server

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Open docs

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Configuration

### Required Environment Variables

Create a `.env` file in the backend directory:

```env
# LLM Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENAI_MODEL=deepseek/deepseek-chat-v3.1:free

# MCP Tools Configuration
MCP_SEARCH_ENABLED=true
GOOGLE_CSE_API_KEY=your_google_cse_api_key_here
GOOGLE_CSE_ENGINE_ID=your_google_cse_engine_id_here

# Database
SQLITE_DB_PATH=./data/app.db
```

### Optional Environment Variables

- `CORS_ALLOW_ORIGINS`: Comma-separated list of allowed origins
- `MCP_SEARCH_URL`: MCP search server URL (default: http://localhost:3001)

## Project Layout

```
backend/
  app/
    api/
      routes/
        chat.py          # Chat endpoints with MCP integration
        health.py        # Health check endpoints
        tools.py         # MCP tools management
    core/
      settings.py        # Configuration management
      mcp_config.py      # MCP tools configuration
    db/
      database.py        # Database connection & schema
    services/
      openai_stream.py   # LLM streaming client
      mcp_client.py      # MCP tools client
    main.py              # FastAPI application entry
  data/
    app.db              # SQLite database file
  requirements.txt
  README.md
  .gitignore
```

## API Endpoints

### Chat Endpoints
- `POST /chat/create` - Create a new chat session
- `GET /chat/stream/{stream_id}` - Stream AI responses with MCP integration
- `GET /chat/sessions/{session_id}/messages` - Get session messages

### MCP Tools Endpoints
- `GET /tools/` - List all available MCP tools
- `GET /tools/enabled` - List enabled MCP tools
- `POST /tools/execute` - Execute an MCP tool
- `GET /tools/{tool_name}/info` - Get specific tool information
- `GET /tools/health` - MCP tools health check

### Utility Endpoints
- `GET /healthz` - Health check
- `GET /config` - Configuration status
