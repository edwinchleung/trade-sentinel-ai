"""Trade journal storage (Postgres or SQLite)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from psycopg.types.json import Jsonb

from trade_sentinel_api.storage.connection import pg_connection, sqlite_connection, use_postgres

_JOURNAL_DB = "trade_journal.db"


def ensure_sqlite_journal_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trade_journal (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            direction TEXT NOT NULL,
            quantity REAL NOT NULL,
            entry_price REAL NOT NULL,
            account_size REAL NOT NULL,
            instrument_type TEXT NOT NULL,
            ai_warnings TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def journal_list() -> list[tuple]:
    if use_postgres():
        with pg_connection() as conn:
            return conn.execute(
                """
                SELECT id, ticker, direction, quantity, entry_price, account_size,
                       instrument_type, ai_warnings, created_at
                FROM trade_journal ORDER BY created_at DESC
                """
            ).fetchall()

    with sqlite_connection(_JOURNAL_DB) as conn:
        ensure_sqlite_journal_schema(conn)
        return conn.execute(
            """
            SELECT id, ticker, direction, quantity, entry_price, account_size,
                   instrument_type, ai_warnings, created_at
            FROM trade_journal ORDER BY created_at DESC
            """
        ).fetchall()


def journal_insert(
    entry_id: str,
    ticker: str,
    direction: str,
    quantity: float,
    entry_price: float,
    account_size: float,
    instrument_type: str,
    ai_warnings: list[str],
    created_iso: str,
) -> None:
    warnings_json = json.dumps(ai_warnings)

    if use_postgres():
        created_dt = datetime.fromisoformat(created_iso)
        with pg_connection() as conn:
            conn.execute(
                """
                INSERT INTO trade_journal
                (id, ticker, direction, quantity, entry_price, account_size,
                 instrument_type, ai_warnings, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entry_id,
                    ticker,
                    direction,
                    quantity,
                    entry_price,
                    account_size,
                    instrument_type,
                    Jsonb(ai_warnings),
                    created_dt,
                ),
            )
            conn.commit()
        return

    with sqlite_connection(_JOURNAL_DB) as conn:
        ensure_sqlite_journal_schema(conn)
        conn.execute(
            """
            INSERT INTO trade_journal
            (id, ticker, direction, quantity, entry_price, account_size,
             instrument_type, ai_warnings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                ticker,
                direction,
                quantity,
                entry_price,
                account_size,
                instrument_type,
                warnings_json,
                created_iso,
            ),
        )
        conn.commit()
