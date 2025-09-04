# Backend (FastAPI)

This backend exposes a minimal FastAPI application for the AI Assistant.

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

Env vars (optional for now):

- `CORS_ALLOW_ORIGINS`: Comma-separated list of allowed origins
- `OPENAI_API_KEY`: OpenAI API key
- `SQLITE_DB_PATH`: Path to SQLite database file (default `./data/app.db`)

## Project Layout

```
backend/
  app/
    core/
      settings.py
    main.py
  requirements.txt
  README.md
  .gitignore
```

> Database models, services, and API routes will be added incrementally.
