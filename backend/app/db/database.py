"""
Lightweight SQLite access layer and schema initialization.

Provides helper functions to create connections and initialize the database
schema without introducing an ORM. This keeps early iterations simple and
allows swapping to SQLModel/SQLAlchemy later by replacing these functions.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from ..core.settings import get_settings


def _database_path_from_url(database_url: str) -> str:
    """Extract filesystem path from a SQLite URL like 'sqlite:///./data/app.db'."""

    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return database_url
    return database_url[len(prefix) :]


def _ensure_parent_directory_exists(db_path: str) -> None:
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def init_db() -> None:
    """Initialize database file and create tables if they do not exist."""

    settings = get_settings()
    db_path = _database_path_from_url(settings.database_url)
    _ensure_parent_directory_exists(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        # Create sessions table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        # Create messages table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """
        )


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with Row factory and FK enabled.

    The connection is closed automatically when the context exits.
    """

    settings = get_settings()
    db_path = _database_path_from_url(settings.database_url)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    finally:
        conn.close()


