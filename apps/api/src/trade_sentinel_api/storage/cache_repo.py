"""Context cache storage (Postgres or SQLite)."""

from __future__ import annotations

import json
import math
import sqlite3
import time
from datetime import UTC, datetime
from typing import Any

from psycopg.types.json import Jsonb

from trade_sentinel_api.storage.connection import pg_connection, sqlite_connection, use_postgres

_CACHE_DB = "context_cache.db"


def ensure_sqlite_cache_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS context_cache (
            cache_key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            expires_at REAL NOT NULL
        )
        """
    )


def json_safe(value: Any) -> Any:
    """Recursively replace NaN/Inf floats so Postgres JSONB accepts the payload."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    return value


def decode_cache_payload(raw: Any) -> Any:
    """Decode DB cache payload; Postgres Jsonb may return plain str, not JSON text."""
    if isinstance(raw, (dict, list, bool)):
        return raw
    if isinstance(raw, (int, float)):
        return raw
    if raw is None:
        return None
    if isinstance(raw, str):
        if not raw:
            return ""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def cache_get(key: str) -> Any | None:
    now = time.time()
    if use_postgres():
        with pg_connection() as conn:
            row = conn.execute(
                "SELECT payload, expires_at FROM context_cache WHERE cache_key = %s",
                (key,),
            ).fetchone()
            if row and row[1].timestamp() > now:
                return decode_cache_payload(row[0])
        return None

    with sqlite_connection(_CACHE_DB) as conn:
        ensure_sqlite_cache_schema(conn)
        row = conn.execute(
            "SELECT payload, expires_at FROM context_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row and row[1] > now:
            return decode_cache_payload(json.loads(row[0]))
    return None


def cache_set(key: str, payload: Any, expires_at: float) -> None:
    if use_postgres():
        expires_dt = datetime.fromtimestamp(expires_at, tz=UTC)
        with pg_connection() as conn:
            conn.execute(
                """
                INSERT INTO context_cache (cache_key, payload, expires_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (cache_key) DO UPDATE
                SET payload = EXCLUDED.payload, expires_at = EXCLUDED.expires_at
                """,
                (key, Jsonb(json_safe(payload)), expires_dt),
            )
            conn.commit()
        return

    with sqlite_connection(_CACHE_DB) as conn:
        ensure_sqlite_cache_schema(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO context_cache (cache_key, payload, expires_at)
            VALUES (?, ?, ?)
            """,
            (key, json.dumps(payload, default=str), expires_at),
        )
        conn.commit()


def cache_delete(key: str) -> None:
    if use_postgres():
        with pg_connection() as conn:
            conn.execute("DELETE FROM context_cache WHERE cache_key = %s", (key,))
            conn.commit()
        return

    with sqlite_connection(_CACHE_DB) as conn:
        ensure_sqlite_cache_schema(conn)
        conn.execute("DELETE FROM context_cache WHERE cache_key = ?", (key,))
        conn.commit()


def cache_delete_like(pattern: str) -> None:
    """Delete cache rows whose cache_key matches SQL LIKE pattern (case-sensitive)."""
    if use_postgres():
        with pg_connection() as conn:
            conn.execute(
                "DELETE FROM context_cache WHERE cache_key LIKE %s",
                (pattern,),
            )
            conn.commit()
        return

    with sqlite_connection(_CACHE_DB) as conn:
        ensure_sqlite_cache_schema(conn)
        conn.execute("DELETE FROM context_cache WHERE cache_key LIKE ?", (pattern,))
        conn.commit()
