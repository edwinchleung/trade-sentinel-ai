"""SEC N-PORT bulk ingest and fund holdings queries."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.db import sec_index_execute
from trade_sentinel_api.services.sec.bulk_storage import (
    _NPORT_CSV_FIELDS,
    _zip_member_name,
    bulk_data_root,
    delete_nport_holdings_for_funds,
    extract_tsv_from_zip,
    iter_tsv_from_zip,
    open_csv_archive_writer,
    quarter_dir,
    read_manifest,
    upsert_nport_holdings_rows,
    write_manifest,
)

logger = logging.getLogger(__name__)

_NPORT_DERA_BASE = "https://www.sec.gov/files/dera/data/form-n-port-data-sets"
_QUARTER_RE = re.compile(r"(\d{4})q([1-4])", re.I)

_FUND_CIK_MAP: dict[str, str] = {
    "SPY": "0000884394",
    "QQQ": "0001067839",
    "ARKK": "0001579982",
    "IWM": "0001100663",
    "VTI": "0000102909",
}


def _sec_headers() -> dict[str, str]:
    settings = get_settings()
    return {"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"}


def target_fund_ciks() -> set[str]:
    settings = get_settings()
    raw = settings.sec_bulk_nport_fund_ciks.strip()
    if raw:
        return {cik.strip().zfill(10) for cik in raw.split(",") if cik.strip()}
    return {cik.zfill(10) for cik in _FUND_CIK_MAP.values()}


def fund_cik_for_ticker(ticker: str) -> str | None:
    return _FUND_CIK_MAP.get(ticker.upper())


def _field(row: dict[str, str], *names: str) -> str:
    for name in names:
        val = row.get(name)
        if val:
            return val.strip()
    return ""


def _normalize_accession(raw: str) -> str:
    return raw.replace("-", "").strip()


def _build_submission_maps(
    submissions: list[dict[str, str]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Return accession -> report_date and normalized accession -> report_date."""
    by_accession: dict[str, str] = {}
    by_norm: dict[str, str] = {}
    for row in submissions:
        acc = _field(row, "ACCESSION_NUMBER", "accession_number")
        if not acc:
            continue
        report_date = _field(row, "REPORT_DATE", "report_date")[:10]
        if not report_date:
            continue
        by_accession[acc] = report_date
        by_norm[_normalize_accession(acc)] = report_date
    return by_accession, by_norm


def _build_registrant_maps(
    registrants: list[dict[str, str]],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    """Return accession maps for CIK and registrant name."""
    cik_by_acc: dict[str, str] = {}
    cik_by_norm: dict[str, str] = {}
    name_by_acc: dict[str, str] = {}
    name_by_norm: dict[str, str] = {}
    for row in registrants:
        acc = _field(row, "ACCESSION_NUMBER", "accession_number")
        if not acc:
            continue
        cik = _field(row, "CIK", "cik").zfill(10)
        reg_name = _field(row, "REGISTRANT_NAME", "registrant_name")
        if cik:
            cik_by_acc[acc] = cik
            cik_by_norm[_normalize_accession(acc)] = cik
        if reg_name:
            name_by_acc[acc] = reg_name
            name_by_norm[_normalize_accession(acc)] = reg_name
    return cik_by_acc, cik_by_norm, name_by_acc, name_by_norm


def _build_series_maps(
    fund_info: list[dict[str, str]],
) -> tuple[dict[str, str], dict[str, str]]:
    series_by_acc: dict[str, str] = {}
    series_by_norm: dict[str, str] = {}
    for row in fund_info:
        acc = _field(row, "ACCESSION_NUMBER", "accession_number")
        if not acc:
            continue
        series = _field(row, "SERIES_NAME", "series_name")
        if series:
            series_by_acc[acc] = series
            series_by_norm[_normalize_accession(acc)] = series
    return series_by_acc, series_by_norm


def _build_target_accessions(
    registrants: list[dict[str, str]],
    target_ciks: set[str],
) -> set[str]:
    accessions: set[str] = set()
    for row in registrants:
        acc = _field(row, "ACCESSION_NUMBER", "accession_number")
        cik = _field(row, "CIK", "cik").zfill(10)
        if acc and cik in target_ciks:
            accessions.add(acc)
            accessions.add(_normalize_accession(acc))
    return accessions


def _build_ticker_by_holding(
    identifiers: list[dict[str, str]],
    *,
    holding_ids: set[str] | None = None,
) -> dict[str, str]:
    tickers: dict[str, str] = {}
    for row in identifiers:
        holding_id = _field(row, "HOLDING_ID", "holding_id")
        if not holding_id or (holding_ids is not None and holding_id not in holding_ids):
            continue
        ticker = _field(row, "IDENTIFIER_TICKER", "identifier_ticker")
        if ticker:
            tickers[holding_id] = ticker.upper()
    return tickers


def _lookup_accession(
    acc: str,
    by_acc: dict[str, str],
    by_norm: dict[str, str],
) -> str:
    if acc in by_acc:
        return by_acc[acc]
    return by_norm.get(_normalize_accession(acc), "")


def _accession_in_targets(acc: str, target_accessions: set[str]) -> bool:
    return acc in target_accessions or _normalize_accession(acc) in target_accessions


def _parse_holding_row(
    row: dict[str, str],
    *,
    sub_acc: dict[str, str],
    sub_norm: dict[str, str],
    cik_acc: dict[str, str],
    cik_norm: dict[str, str],
    series_acc: dict[str, str],
    series_norm: dict[str, str],
    reg_norm: dict[str, str],
    target_accessions: set[str] | None = None,
) -> dict[str, Any] | None:
    acc = _field(row, "ACCESSION_NUMBER", "accession_number")
    if not acc:
        return None
    if target_accessions is not None and not _accession_in_targets(acc, target_accessions):
        return None

    fund_cik = _lookup_accession(acc, cik_acc, cik_norm)
    if not fund_cik:
        return None

    report_date = _lookup_accession(acc, sub_acc, sub_norm)
    series_name = _lookup_accession(acc, series_acc, series_norm)
    if not series_name:
        series_name = _lookup_accession(acc, {}, reg_norm)

    cusip = _field(row, "ISSUER_CUSIP", "issuer_cusip", "CUSIP", "cusip")
    asset_cat = _field(row, "ASSET_CAT", "asset_cat")[:32]
    holding_name = _field(row, "ISSUER_NAME", "issuer_name", "NAME", "name")
    holding_id = _field(row, "HOLDING_ID", "holding_id")

    raw_value = _field(row, "CURRENCY_VALUE", "currency_value", "valUSD", "VALUSD")
    if not raw_value:
        raw_value = _field(row, "BALANCE", "balance")
    try:
        fair_value = int(float(raw_value or 0))
    except (ValueError, OverflowError):
        fair_value = 0

    pct_raw = _field(row, "PERCENTAGE", "percentage", "pctVal", "PCTVAL")
    try:
        pct_nav = float(pct_raw) if pct_raw else None
    except ValueError:
        pct_nav = None

    if not cusip and not holding_name:
        return None

    return {
        "report_date": report_date or "",
        "fund_cik": fund_cik,
        "fund_name": series_name or None,
        "holding_name": holding_name or None,
        "cusip": cusip or "",
        "holding_id": holding_id or None,
        "asset_category": asset_cat,
        "fair_value_usd": fair_value,
        "pct_of_nav": pct_nav,
    }


def _row_to_tuple(parsed: dict[str, Any], *, ticker: str | None = None) -> tuple:
    return (
        parsed["report_date"],
        parsed["fund_cik"],
        parsed["fund_name"],
        parsed["holding_name"],
        parsed["cusip"],
        ticker,
        parsed["asset_category"],
        parsed["fair_value_usd"],
        parsed["pct_of_nav"],
    )


def _archive_row(parsed: dict[str, Any], *, ticker: str | None = None) -> dict[str, Any]:
    return {
        "report_date": parsed["report_date"],
        "fund_cik": parsed["fund_cik"],
        "fund_name": parsed["fund_name"],
        "holding_name": parsed["holding_name"],
        "cusip": parsed["cusip"],
        "ticker": ticker,
        "asset_category": parsed["asset_category"],
        "fair_value_usd": parsed["fair_value_usd"],
        "pct_of_nav": parsed["pct_of_nav"],
    }


def parse_nport_holdings_rows(
    *,
    submissions: list[dict[str, str]],
    registrants: list[dict[str, str]],
    fund_info: list[dict[str, str]],
    holdings: list[dict[str, str]],
    identifiers: list[dict[str, str]] | None = None,
    target_ciks: set[str] | None = None,
) -> tuple[list[tuple], list[dict[str, Any]]]:
    sub_acc, sub_norm = _build_submission_maps(submissions)
    cik_acc, cik_norm, _, reg_norm = _build_registrant_maps(registrants)
    series_acc, series_norm = _build_series_maps(fund_info)
    target_accessions = _build_target_accessions(registrants, target_ciks) if target_ciks else None
    ticker_by_holding = _build_ticker_by_holding(identifiers or [])

    rows: list[tuple] = []
    archive: list[dict[str, Any]] = []
    skipped = 0

    for row in holdings:
        parsed = _parse_holding_row(
            row,
            sub_acc=sub_acc,
            sub_norm=sub_norm,
            cik_acc=cik_acc,
            cik_norm=cik_norm,
            series_acc=series_acc,
            series_norm=series_norm,
            reg_norm=reg_norm,
            target_accessions=target_accessions,
        )
        if parsed is None:
            skipped += 1
            continue

        holding_id = parsed.get("holding_id")
        ticker = ticker_by_holding.get(holding_id) if holding_id else None
        rows.append(_row_to_tuple(parsed, ticker=ticker))
        archive.append(_archive_row(parsed, ticker=ticker))

    if skipped:
        logger.debug("N-PORT ingest skipped %s holding rows without CIK/accession", skipped)
    return rows, archive


def _holdings_member_suffix(zip_path: Path) -> str | None:
    for suffix in ("FUND_REPORTED_HOLDING.tsv", "HOLDING.tsv"):
        if _zip_member_name(zip_path, suffix):
            return suffix
    return None


def _stream_identifiers_for_holdings(
    zip_path: Path,
    holding_ids: set[str],
) -> dict[str, str]:
    tickers: dict[str, str] = {}
    if not holding_ids:
        return tickers
    for row in iter_tsv_from_zip(zip_path, "IDENTIFIERS.tsv"):
        holding_id = _field(row, "HOLDING_ID", "holding_id")
        if not holding_id or holding_id not in holding_ids:
            continue
        ticker = _field(row, "IDENTIFIER_TICKER", "identifier_ticker")
        if ticker:
            tickers[holding_id] = ticker.upper()
    return tickers


def parse_nport_holdings_stream(
    zip_path: Path,
    *,
    submissions: list[dict[str, str]],
    registrants: list[dict[str, str]],
    fund_info: list[dict[str, str]],
    target_ciks: set[str],
    quarter_key: str,
) -> tuple[list[tuple], int]:
    """Stream holdings from ZIP for tracked fund CIKs only; enrich tickers in a second pass."""
    holdings_suffix = _holdings_member_suffix(zip_path)
    if not holdings_suffix:
        return [], 0

    sub_acc, sub_norm = _build_submission_maps(submissions)
    cik_acc, cik_norm, _, reg_norm = _build_registrant_maps(registrants)
    series_acc, series_norm = _build_series_maps(fund_info)
    target_accessions = _build_target_accessions(registrants, target_ciks)

    parsed_rows: list[dict[str, Any]] = []
    holding_ids: set[str] = set()
    skipped = 0

    for row in iter_tsv_from_zip(zip_path, holdings_suffix):
        parsed = _parse_holding_row(
            row,
            sub_acc=sub_acc,
            sub_norm=sub_norm,
            cik_acc=cik_acc,
            cik_norm=cik_norm,
            series_acc=series_acc,
            series_norm=series_norm,
            reg_norm=reg_norm,
            target_accessions=target_accessions,
        )
        if parsed is None:
            skipped += 1
            continue
        holding_id = parsed.get("holding_id")
        if holding_id:
            holding_ids.add(holding_id)
        parsed_rows.append(parsed)

    if skipped:
        logger.debug("N-PORT stream skipped %s holding rows outside tracked funds", skipped)

    ticker_by_holding = _stream_identifiers_for_holdings(zip_path, holding_ids)

    rows: list[tuple] = []
    with open_csv_archive_writer("nport", quarter_key, "holdings.csv", fieldnames=_NPORT_CSV_FIELDS) as (
        csv_writer,
        _,
    ):
        for parsed in parsed_rows:
            holding_id = parsed.get("holding_id")
            ticker = ticker_by_holding.get(holding_id) if holding_id else None
            rows.append(_row_to_tuple(parsed, ticker=ticker))
            csv_writer.writerow(_archive_row(parsed, ticker=ticker))

    return rows, len(rows)


def ingest_nport_zip(zip_path: Path, *, quarter_key: str) -> dict[str, Any]:
    submissions = extract_tsv_from_zip(zip_path, "SUBMISSION.tsv")
    registrants = extract_tsv_from_zip(zip_path, "REGISTRANT.tsv")
    fund_info = extract_tsv_from_zip(zip_path, "FUND_REPORTED_INFO.tsv")

    if not _holdings_member_suffix(zip_path):
        return {"ok": False, "message": f"No holdings TSV in {zip_path}", "rows": 0}
    if not registrants:
        return {"ok": False, "message": f"No REGISTRANT.tsv in {zip_path}", "rows": 0}

    target_ciks = target_fund_ciks()
    rows, count = parse_nport_holdings_stream(
        zip_path,
        submissions=submissions,
        registrants=registrants,
        fund_info=fund_info,
        target_ciks=target_ciks,
        quarter_key=quarter_key,
    )
    if not rows:
        return {"ok": False, "message": "No N-PORT holdings parsed for tracked funds", "rows": 0}

    report_dates = {row[0] for row in rows if row[0]}
    for report_date in report_dates:
        delete_nport_holdings_for_funds(report_date, sorted(target_ciks))

    upserted = upsert_nport_holdings_rows(rows)
    manifest = read_manifest("nport")
    quarters = manifest.get("quarters") or []
    if quarter_key not in quarters:
        quarters.append(quarter_key)
    manifest["quarters"] = sorted(quarters, reverse=True)[-8:]
    manifest["last_ingest"] = datetime.now(UTC).isoformat()
    write_manifest("nport", manifest)
    return {"ok": True, "rows": upserted, "quarter_key": quarter_key, "parsed": count}


def download_nport_quarter_zip(quarter_label: str) -> Path:
    label = quarter_label.lower().replace("-", "")
    m = _QUARTER_RE.search(label)
    qkey = f"{m.group(1)}Q{m.group(2)}" if m else label.upper()
    url = f"{_NPORT_DERA_BASE}/{label}_nport.zip"
    dest = quarter_dir("nport", qkey) / f"{label}_nport.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading N-PORT bulk ZIP from %s", url)
    with httpx.Client(timeout=300.0, follow_redirects=True, headers=_sec_headers()) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                    fh.write(chunk)
    return dest


def ingest_latest_nport_quarter(quarter_label: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.sec_bulk_nport_enabled:
        return {"ok": False, "message": "N-PORT bulk ingest disabled"}
    label = quarter_label
    if not label:
        manifest = read_manifest("nport")
        label = (manifest.get("quarters") or [None])[0]
    if not label:
        label = "2025q4"
    m = _QUARTER_RE.search(label.lower())
    qkey = f"{m.group(1)}Q{m.group(2)}" if m else label.upper()
    zip_path = bulk_data_root() / "nport" / qkey / f"{label.lower()}_nport.zip"
    if not zip_path.exists():
        try:
            zip_path = download_nport_quarter_zip(label)
        except Exception as exc:
            logger.warning("N-PORT bulk download failed for %s: %s", label, exc)
            return {"ok": False, "message": str(exc)}
    return ingest_nport_zip(zip_path, quarter_key=qkey)


def query_nport_holdings(fund_cik: str, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = sec_index_execute(
        """
        SELECT report_date, fund_cik, fund_name, holding_name, cusip, ticker, asset_category, fair_value_usd, pct_of_nav
        FROM sec_nport_holdings
        WHERE fund_cik = ?
        ORDER BY report_date DESC, fair_value_usd DESC
        LIMIT ?
        """,
        (fund_cik.zfill(10), limit),
        fetch="all",
    )
    if not rows:
        return []
    cols = (
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
    return [dict(zip(cols, row, strict=True)) for row in rows]
