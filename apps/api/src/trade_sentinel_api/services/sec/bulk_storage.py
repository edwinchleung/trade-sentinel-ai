"""Hybrid SEC bulk storage: CSV/Parquet archives + Postgres/SQLite index."""

from __future__ import annotations

import csv
import json
import logging
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Any

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.db import sec_index_execute

logger = logging.getLogger(__name__)

_API_ROOT = Path(__file__).resolve().parents[3]


def bulk_data_root() -> Path:
    settings = get_settings()
    raw = settings.sec_bulk_data_dir.strip() or "data/sec_bulk"
    if raw.startswith("apps/api/"):
        raw = raw.removeprefix("apps/api/")
    path = Path(raw)
    if not path.is_absolute():
        path = _API_ROOT / raw
    path.mkdir(parents=True, exist_ok=True)
    return path


def quarter_dir(dataset: str, quarter_key: str) -> Path:
    d = bulk_data_root() / dataset / quarter_key
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_manifest(dataset: str) -> dict[str, Any]:
    path = bulk_data_root() / dataset / "manifest.json"
    if not path.exists():
        return {"quarters": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"quarters": []}


def write_manifest(dataset: str, manifest: dict[str, Any]) -> None:
    path = bulk_data_root() / dataset / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


_NPORT_CSV_FIELDS = (
    "report_date",
    "fund_cik",
    "fund_name",
    "holding_name",
    "cusip",
    "ticker",
    "asset_category",
    "fair_value_usd",
    "pct_of_nav",
)


def write_csv_archive(dataset: str, quarter_key: str, filename: str, rows: list[dict[str, Any]]) -> Path:
    out = quarter_dir(dataset, quarter_key) / filename
    if not rows:
        out.write_text("", encoding="utf-8")
        return out
    fieldnames = list(rows[0].keys())
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out


@contextmanager
def open_csv_archive_writer(
    dataset: str,
    quarter_key: str,
    filename: str,
    *,
    fieldnames: tuple[str, ...] | list[str],
):
    """Open a CSV archive for incremental row writes."""
    out = quarter_dir(dataset, quarter_key) / filename
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        yield writer, out


def upsert_13f_holdings_rows(rows: list[tuple]) -> int:
    """Upsert (quarter_end, filer_cik, cusip, ...) rows into sec_13f_holdings."""
    if not rows:
        return 0
    from trade_sentinel_api.db import ensure_pg_sec_index_schema, sec_index_connection, use_postgres

    if use_postgres():
        from trade_sentinel_api.db import pg_connection

        sql = """
            INSERT INTO sec_13f_holdings
            (quarter_end, filer_cik, filer_name, cusip, ticker, shares, value_usd, filing_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (quarter_end, filer_cik, cusip) DO UPDATE SET
                filer_name=EXCLUDED.filer_name,
                ticker=EXCLUDED.ticker,
                shares=EXCLUDED.shares,
                value_usd=EXCLUDED.value_usd,
                filing_date=EXCLUDED.filing_date
        """
        with pg_connection() as conn:
            ensure_pg_sec_index_schema(conn)
            conn.cursor().executemany(sql, rows)
            conn.commit()
        return len(rows)

    sql = """
        INSERT INTO sec_13f_holdings
        (quarter_end, filer_cik, filer_name, cusip, ticker, shares, value_usd, filing_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (quarter_end, filer_cik, cusip) DO UPDATE SET
            filer_name=excluded.filer_name,
            ticker=excluded.ticker,
            shares=excluded.shares,
            value_usd=excluded.value_usd,
            filing_date=excluded.filing_date
    """
    with sec_index_connection() as conn:
        conn.executemany(sql, rows)
        conn.commit()
    return len(rows)


def upsert_nport_holdings_rows(rows: list[tuple], *, batch_size: int = 2000) -> int:
    if not rows:
        return 0
    from trade_sentinel_api.db import ensure_pg_sec_index_schema, sec_index_connection, use_postgres

    if use_postgres():
        from trade_sentinel_api.db import pg_connection

        sql = """
            INSERT INTO sec_nport_holdings
            (report_date, fund_cik, fund_name, holding_name, cusip, ticker, asset_category, fair_value_usd, pct_of_nav)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (report_date, fund_cik, cusip, asset_category) DO UPDATE SET
                fund_name=EXCLUDED.fund_name,
                holding_name=EXCLUDED.holding_name,
                ticker=EXCLUDED.ticker,
                fair_value_usd=EXCLUDED.fair_value_usd,
                pct_of_nav=EXCLUDED.pct_of_nav
        """
        with pg_connection() as conn:
            ensure_pg_sec_index_schema(conn)
            cur = conn.cursor()
            for start in range(0, len(rows), batch_size):
                cur.executemany(sql, rows[start : start + batch_size])
            conn.commit()
        return len(rows)

    sql = """
        INSERT INTO sec_nport_holdings
        (report_date, fund_cik, fund_name, holding_name, cusip, ticker, asset_category, fair_value_usd, pct_of_nav)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (report_date, fund_cik, cusip, asset_category) DO UPDATE SET
            fund_name=excluded.fund_name,
            holding_name=excluded.holding_name,
            ticker=excluded.ticker,
            fair_value_usd=excluded.fair_value_usd,
            pct_of_nav=excluded.pct_of_nav
    """
    with sec_index_connection() as conn:
        for start in range(0, len(rows), batch_size):
            conn.executemany(sql, rows[start : start + batch_size])
        conn.commit()
    return len(rows)


def delete_nport_holdings_for_funds(report_date: str, fund_ciks: list[str]) -> int:
    """Remove prior rows for tracked funds on a report date before re-ingest."""
    if not report_date or not fund_ciks:
        return 0
    placeholders = ",".join("?" for _ in fund_ciks)
    sql = f"""
        DELETE FROM sec_nport_holdings
        WHERE report_date = ? AND fund_cik IN ({placeholders})
    """
    sec_index_execute(sql, (report_date, *fund_ciks))
    return len(fund_ciks)


def query_13f_by_ticker(ticker: str, *, limit_quarters: int = 2) -> list[dict[str, Any]]:
    symbol = ticker.upper()
    quarters = sec_index_execute(
        """
        SELECT DISTINCT quarter_end FROM sec_13f_holdings
        WHERE ticker = ?
        ORDER BY quarter_end DESC
        LIMIT ?
        """,
        (symbol, limit_quarters),
        fetch="all",
    )
    if not quarters:
        return []
    q_ends = [q[0] for q in quarters]
    placeholders = ",".join("?" for _ in q_ends)
    rows = sec_index_execute(
        f"""
        SELECT quarter_end, filer_cik, filer_name, cusip, ticker, shares, value_usd, filing_date
        FROM sec_13f_holdings
        WHERE ticker = ? AND quarter_end IN ({placeholders})
        ORDER BY quarter_end DESC, value_usd DESC
        """,
        (symbol, *q_ends),
        fetch="all",
    )
    if not rows:
        return []
    cols = (
        "quarter_end",
        "filer_cik",
        "filer_name",
        "cusip",
        "ticker",
        "shares",
        "value_usd",
        "filing_date",
    )
    return [dict(zip(cols, row, strict=True)) for row in rows]


def count_13f_holders(ticker: str, quarter_end: str) -> int:
    row = sec_index_execute(
        """
        SELECT COUNT(*) FROM sec_13f_holdings
        WHERE ticker = ? AND quarter_end = ?
        """,
        (ticker.upper(), quarter_end),
        fetch="one",
    )
    return int(row[0]) if row else 0


def has_13f_bulk_index() -> bool:
    row = sec_index_execute("SELECT COUNT(*) FROM sec_13f_holdings LIMIT 1", fetch="one")
    if row is None:
        return False
    try:
        count_row = sec_index_execute("SELECT COUNT(*) FROM sec_13f_holdings", fetch="one")
        return bool(count_row and count_row[0] > 0)
    except Exception:
        return False


def has_nport_bulk_index() -> bool:
    try:
        count_row = sec_index_execute("SELECT COUNT(*) FROM sec_nport_holdings", fetch="one")
        return bool(count_row and count_row[0] > 0)
    except Exception:
        return False


def _zip_member_name(zip_path: Path, member_suffix: str) -> str | None:
    if not zip_path.exists():
        return None
    with zipfile.ZipFile(zip_path, "r") as zf:
        return next((n for n in zf.namelist() if n.lower().endswith(member_suffix.lower())), None)


def iter_tsv_from_zip(zip_path: Path, member_suffix: str) -> Iterator[dict[str, str]]:
    """Stream TSV rows from a ZIP member without materializing the full file."""
    member = _zip_member_name(zip_path, member_suffix)
    if not member:
        return
    with zipfile.ZipFile(zip_path, "r") as zf, zf.open(member) as raw:
        text = TextIOWrapper(raw, encoding="utf-8", errors="replace")
        reader = csv.DictReader(text, delimiter="\t")
        for row in reader:
            yield {k: (v or "").strip() for k, v in row.items() if k}


def extract_tsv_from_zip(zip_path: Path, member_suffix: str) -> list[dict[str, str]]:
    return list(iter_tsv_from_zip(zip_path, member_suffix))
