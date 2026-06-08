"""Watchlist storage (Postgres or SQLite)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from trade_sentinel_api.storage.connection import pg_connection, sqlite_connection, use_postgres

_WATCHLIST_DB = "watchlists.db"


def ensure_sqlite_watchlist_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            tickers TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        )
        """
    )


def watchlist_get(name: str = "default") -> list[str]:
    if use_postgres():
        with pg_connection() as conn:
            row = conn.execute(
                "SELECT tickers FROM watchlists WHERE name = %s",
                (name,),
            ).fetchone()
            if not row:
                return []
            tickers = row[0]
            return list(tickers) if isinstance(tickers, list) else json.loads(tickers)

    with sqlite_connection(_WATCHLIST_DB) as conn:
        ensure_sqlite_watchlist_schema(conn)
        row = conn.execute(
            "SELECT tickers FROM watchlists WHERE name = ?",
            (name,),
        ).fetchone()
        if not row:
            return []
        return json.loads(row[0])


def watchlist_set(name: str, tickers: list[str]) -> list[str]:
    normalized = sorted({t.upper().strip() for t in tickers if t.strip()})
    created_iso = datetime.now(UTC).isoformat()

    if use_postgres():
        with pg_connection() as conn:
            conn.execute(
                """
                INSERT INTO watchlists (name, tickers, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE
                SET tickers = EXCLUDED.tickers
                """,
                (name, normalized, created_iso),
            )
            conn.commit()
        return normalized

    with sqlite_connection(_WATCHLIST_DB) as conn:
        ensure_sqlite_watchlist_schema(conn)
        conn.execute(
            """
            INSERT INTO watchlists (name, tickers, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET tickers = excluded.tickers
            """,
            (name, json.dumps(normalized), created_iso),
        )
        conn.commit()
    return normalized
