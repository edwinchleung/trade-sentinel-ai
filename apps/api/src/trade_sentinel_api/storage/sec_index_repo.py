"""SEC 13F / N-PORT index storage (Postgres or SQLite)."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from trade_sentinel_api.storage.connection import pg_connection, sqlite_connection, use_postgres

_SEC_INDEX_DB = "sec_index.db"

_SEC_13F_HOLDINGS_DDL = """
CREATE TABLE IF NOT EXISTS sec_13f_holdings (
    quarter_end TEXT NOT NULL,
    filer_cik TEXT NOT NULL,
    filer_name TEXT,
    cusip TEXT NOT NULL,
    ticker TEXT,
    shares INTEGER,
    value_usd INTEGER,
    filing_date TEXT,
    PRIMARY KEY (quarter_end, filer_cik, cusip)
);
CREATE INDEX IF NOT EXISTS idx_13f_ticker_quarter ON sec_13f_holdings(ticker, quarter_end);
"""

_SEC_NPORT_HOLDINGS_DDL = """
CREATE TABLE IF NOT EXISTS sec_nport_holdings (
    report_date TEXT NOT NULL,
    fund_cik TEXT NOT NULL,
    fund_name TEXT,
    holding_name TEXT,
    cusip TEXT,
    ticker TEXT,
    asset_category TEXT NOT NULL DEFAULT '',
    fair_value_usd BIGINT,
    pct_of_nav REAL,
    PRIMARY KEY (report_date, fund_cik, cusip, asset_category)
);
CREATE INDEX IF NOT EXISTS idx_nport_fund_date ON sec_nport_holdings(fund_cik, report_date);
"""


def _ensure_nport_holding_name_column(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ALTER TABLE sec_nport_holdings ADD COLUMN holding_name TEXT")
    except sqlite3.OperationalError:
        pass


def ensure_sec_index_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SEC_13F_HOLDINGS_DDL)
    conn.executescript(_SEC_NPORT_HOLDINGS_DDL)
    _ensure_nport_holding_name_column(conn)


def ensure_pg_sec_index_schema(conn) -> None:
    for stmt in (_SEC_13F_HOLDINGS_DDL, _SEC_NPORT_HOLDINGS_DDL):
        for line in stmt.strip().split(";"):
            part = line.strip()
            if part:
                conn.execute(part)
    try:
        conn.execute("ALTER TABLE sec_nport_holdings ADD COLUMN IF NOT EXISTS holding_name TEXT")
    except Exception:
        pass
    try:
        conn.execute(
            "ALTER TABLE sec_nport_holdings ALTER COLUMN fair_value_usd TYPE BIGINT"
        )
    except Exception:
        pass
    conn.commit()


@contextmanager
def sec_index_connection() -> Generator[sqlite3.Connection, None, None]:
    with sqlite_connection(_SEC_INDEX_DB) as conn:
        ensure_sec_index_schema(conn)
        yield conn


def sec_index_execute(sql: str, params: tuple | list = (), *, fetch: str | None = None) -> Any:
    """Run a query on Postgres (when configured) or SQLite sec_index."""
    if use_postgres():
        with pg_connection() as conn:
            ensure_pg_sec_index_schema(conn)
            cur = conn.execute(sql.replace("?", "%s"), params)
            if fetch == "all":
                return cur.fetchall()
            if fetch == "one":
                return cur.fetchone()
            conn.commit()
            return None

    with sec_index_connection() as conn:
        cur = conn.execute(sql, params)
        if fetch == "all":
            return cur.fetchall()
        if fetch == "one":
            return cur.fetchone()
        conn.commit()
        return None


def sec_index_executemany(sql: str, rows: list[tuple]) -> None:
    if not rows:
        return
    if use_postgres():
        with pg_connection() as conn:
            ensure_pg_sec_index_schema(conn)
            conn.cursor().executemany(sql.replace("?", "%s"), rows)
            conn.commit()
        return
    with sec_index_connection() as conn:
        conn.executemany(sql, rows)
        conn.commit()
