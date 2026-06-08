"""Database connection helpers for Postgres and SQLite fallback."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from trade_sentinel_api.config import get_settings

logger = logging.getLogger(__name__)

SQLITE_DIR = Path(__file__).resolve().parents[3] / ".cache"
_storage_backend_logged = False


def use_postgres() -> bool:
    url = get_settings().database_url.strip()
    return url.startswith("postgresql")


@contextmanager
def pg_connection():
    import psycopg

    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        yield conn


@contextmanager
def sqlite_connection(db_name: str) -> Generator[sqlite3.Connection, None, None]:
    SQLITE_DIR.mkdir(parents=True, exist_ok=True)
    path = SQLITE_DIR / db_name
    conn = sqlite3.connect(path)
    try:
        yield conn
    finally:
        conn.close()


def log_storage_backend_once() -> None:
    global _storage_backend_logged
    if _storage_backend_logged:
        return
    _storage_backend_logged = True
    if use_postgres():
        logger.info("storage_backend=postgres database_url configured")
    else:
        path = SQLITE_DIR / "watchlists.db"
        logger.info("storage_backend=sqlite watchlists_path=%s", path)
