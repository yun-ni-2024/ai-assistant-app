"""
FastAPI application entrypoint.

This module initializes the FastAPI app instance, configures CORS, and
exposes the ASGI callable named `app` for use by Uvicorn or other ASGI servers.

The app is intentionally minimal at this stage. A health check endpoint and
business routes will be added in subsequent steps.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.settings import get_settings
from .api.routes.health import router as health_router
from .api.routes.chat import router as chat_router
from .db.database import init_db


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Returns:
        FastAPI: Configured FastAPI app.
    """

    settings = get_settings()

    app = FastAPI(
        title="AI Assistant Backend",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS to allow local frontend development by default
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(chat_router)

    # Initialize database on startup
    @app.on_event("startup")
    async def _on_startup() -> None:  # pragma: no cover - simple wiring
        init_db()

    # Placeholder root route to verify the server is running
    @app.get("/")
    async def root() -> dict:
        """Return a simple JSON payload to confirm the service is up."""
        return {"message": "AI Assistant Backend is running"}

    return app


app = create_app()


