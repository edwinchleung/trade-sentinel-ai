"""CFTC Commitments of Traders — commercial positioning extremes."""

from __future__ import annotations

import asyncio
import csv
import io
import zipfile
from datetime import UTC, datetime

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import CotPositionRow, CotReport
from trade_sentinel_api.services.cache import clear_cached, get_cached, set_cached_ttl

# CFTC legacy futures-only yearly ZIP archives (flat CSV URLs retired)
_COT_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"

_SYMBOL_MAP = {
    "ES": ("S&P 500", "E-MINI S&P 500"),
    "CL": ("CRUDE OIL", "WTI-PHYSICAL"),
    "GC": ("GOLD",),
    "ZN": ("10-YEAR", "10 YEAR"),
}


def _find_row(rows: list[dict], aliases: tuple[str, ...]) -> dict | None:
    for row in rows:
        name = (row.get("Market_and_Exchange_Names") or row.get("Market and Exchange Names") or "").upper()
        if any(alias.upper() in name for alias in aliases):
            return row
    return None


def _parse_cot_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _extract_csv_from_zip(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.lower().endswith((".txt", ".csv")):
                return zf.read(name).decode("utf-8", errors="replace")
    raise ValueError("No CSV/TXT file found in COT ZIP archive")


def _download_cot_rows(client: httpx.Client) -> list[dict]:
    year = datetime.now(UTC).year
    last_exc: Exception | None = None
    for attempt_year in (year, year - 1, year - 2):
        url = _COT_URL.format(year=attempt_year)
        resp = client.get(url)
        if resp.status_code != 200:
            last_exc = httpx.HTTPStatusError(
                f"HTTP {resp.status_code} for {url}",
                request=resp.request,
                response=resp,
            )
            continue
        text = _extract_csv_from_zip(resp.content)
        return _parse_cot_csv(text)
    if last_exc:
        raise last_exc
    raise ValueError("COT data unavailable: no archive found")


def _commercial_net(row: dict) -> float | None:
    for comm_long, comm_short in (
        ("Comm_Positions_Long_All", "Comm_Positions_Short_All"),
        ("Comm Positions-Long (All)", "Comm Positions-Short (All)"),
    ):
        if comm_long in row and comm_short in row:
            try:
                return float(row[comm_long].replace(",", "")) - float(
                    row[comm_short].replace(",", "")
                )
            except (ValueError, AttributeError):
                pass
    return None


def _fetch_sync(symbols: list[str]) -> CotReport:
    positions: list[CotPositionRow] = []
    try:
        with httpx.Client(timeout=30.0) as client:
            rows = _download_cot_rows(client)
    except (httpx.HTTPError, ValueError) as exc:
        return CotReport(
            as_of=datetime.now(UTC),
            data_available=False,
            message=f"COT data unavailable: {exc}",
        )

    for sym in symbols:
        aliases = _SYMBOL_MAP.get(sym.upper())
        if not aliases:
            continue
        row = _find_row(rows, aliases)
        if not row:
            continue
        net = _commercial_net(row)
        report_date = row.get("Report_Date_as_YYYY-MM-DD") or row.get("Report Date as YYYY-MM-DD")
        signal = None
        if net is not None:
            if net > 0:
                signal = "commercial_net_long"
            elif net < 0:
                signal = "commercial_net_short"
        positions.append(
            CotPositionRow(
                symbol=sym.upper(),
                market_name=row.get("Market_and_Exchange_Names") or row.get("Market and Exchange Names"),
                report_date=report_date,
                commercial_net=net,
                signal=signal,
                reversal_zone=abs(net or 0) > 100000,
            )
        )

    return CotReport(
        as_of=datetime.now(UTC),
        positions=positions,
        data_available=len(positions) > 0,
        message=None if positions else "No COT matches for requested symbols.",
        disclaimer="Macro futures positioning — not per-stock. Commercials considered smart-money hedgers.",
    )


async def fetch_cot_report(symbols: list[str] | None = None) -> CotReport:
    syms = symbols or ["ES", "CL", "GC", "ZN"]
    cache_key = ",".join(sorted(s.upper() for s in syms))
    cached = get_cached("smart_money_cot", cache_key)
    if cached:
        report = CotReport(**cached)
        if report.data_available or not report.message or "404" not in report.message:
            return report
        clear_cached("smart_money_cot", cache_key)

    report = await asyncio.to_thread(_fetch_sync, syms)
    ttl = get_settings().smart_money_cot_cache_hours * 3600
    set_cached_ttl("smart_money_cot", cache_key, report.model_dump(mode="json"), ttl)
    return report
