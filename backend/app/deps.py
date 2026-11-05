"""FastAPI dependencies shared by the routes."""
import sqlite3
from typing import Iterator

from fastapi import HTTPException, Request

from app import db
from app.config import Settings


def get_settings_dep(request: Request) -> Settings:
    # Settings live on app.state so tests can build an app with their own settings.
    return request.app.state.settings


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """One SQLite connection per request (cheap for a local file), closed afterwards."""
    settings: Settings = request.app.state.settings
    if not settings.db_file.exists():
        raise HTTPException(503, "Knowledge base not loaded. Run: uv run python scripts/ingest.py")
    conn = db.connect(settings.db_file)
    try:
        yield conn
    finally:
        conn.close()
