"""SEC Form 13F bulk dataset ingest from sec.gov quarterly ZIP files."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.sec.bulk_storage import (
    bulk_data_root,
    extract_tsv_from_zip,
    quarter_dir,
    read_manifest,
    upsert_13f_holdings_rows,
    write_csv_archive,
    write_manifest,
)
from trade_sentinel_api.services.sec.form13f import (
    _ISSUER_NAME_ALIASES,
    _load_cusip_map,
    _save_cusip_map,
)

logger = logging.getLogger(__name__)

_SEC_13F_INDEX = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
_QUARTER_RE = re.compile(r"(\d{4})q([1-4])", re.I)


def _sec_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "User-Agent": settings.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
    }


def quarter_key_from_label(label: str) -> str:
    m = _QUARTER_RE.search(label.replace("-", ""))
    if m:
        return f"{m.group(1)}Q{m.group(2)}"
    return label


def _map_cusip_to_ticker(cusip: str, name: str, cusip_map: dict[str, str]) -> str | None:
    cusip_u = cusip.upper()
    for ticker, mapped in cusip_map.items():
        if mapped.upper() == cusip_u:
            return ticker.upper()
    name_u = name.upper()
    for alias, ticker in _ISSUER_NAME_ALIASES.items():
        if alias in name_u:
            return ticker
    tokens = name_u.replace(",", "").split()
    if tokens and len(tokens[0]) <= 5 and tokens[0].isalpha():
        return tokens[0]
    return None


def parse_infotable_rows(
    infotable: list[dict[str, str]],
    *,
    submission_map: dict[str, dict[str, str]],
    cusip_map: dict[str, str],
) -> list[tuple]:
    rows: list[tuple] = []
    for row in infotable:
        cusip = (row.get("cusip") or row.get("CUSIP") or "").strip()
        if not cusip:
            continue
        accession = (row.get("accessionNumber") or row.get("ACCESSION_NUMBER") or "").strip()
        sub = submission_map.get(accession.replace("-", ""), submission_map.get(accession, {}))
        filer_cik = (sub.get("cik") or row.get("cik") or "").strip().zfill(10)
        filer_name = sub.get("companyName") or sub.get("filerName") or ""
        quarter_end = (
            row.get("reportCalendarOrQuarter")
            or sub.get("reportCalendarOrQuarter")
            or sub.get("periodOfReport")
            or ""
        )[:10]
        filing_date = (sub.get("filingDate") or "")[:10]
        name = row.get("nameOfIssuer") or row.get("NAMEOFISSUER") or ""
        shares_raw = row.get("sshPrnamt") or row.get("SSHPRNAMT") or "0"
        value_raw = row.get("value") or row.get("VALUE") or "0"
        try:
            shares = int(float(str(shares_raw).replace(",", "")))
        except ValueError:
            shares = 0
        try:
            value_usd = int(float(str(value_raw).replace(",", "")))
        except ValueError:
            value_usd = 0
        ticker = _map_cusip_to_ticker(cusip, name, cusip_map)
        if ticker and cusip:
            cusip_map[ticker] = cusip
        rows.append(
            (
                quarter_end,
                filer_cik,
                filer_name,
                cusip,
                ticker,
                shares,
                value_usd,
                filing_date or None,
            )
        )
    return rows


def _build_submission_map(submissions: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in submissions:
        acc = (row.get("accessionNumber") or row.get("ACCESSION_NUMBER") or "").strip()
        if not acc:
            continue
        out[acc.replace("-", "")] = row
        out[acc] = row
    return out


def ingest_13f_zip(zip_path: Path, *, quarter_key: str) -> dict[str, Any]:
    """Parse a downloaded 13F ZIP and upsert into the holdings index."""
    cusip_map = _load_cusip_map()
    infotable = extract_tsv_from_zip(zip_path, "INFOTABLE.tsv")
    submissions = extract_tsv_from_zip(zip_path, "SUBMISSION.tsv")
    if not infotable:
        return {"ok": False, "message": f"No INFOTABLE.tsv in {zip_path}", "rows": 0}

    submission_map = _build_submission_map(submissions)
    parsed = parse_infotable_rows(infotable, submission_map=submission_map, cusip_map=cusip_map)
    _save_cusip_map(cusip_map)

    archive_rows = [
        {
            "quarter_end": r[0],
            "filer_cik": r[1],
            "filer_name": r[2],
            "cusip": r[3],
            "ticker": r[4],
            "shares": r[5],
            "value_usd": r[6],
            "filing_date": r[7],
        }
        for r in parsed
    ]
    write_csv_archive("13f", quarter_key, "infotable.csv", archive_rows)
    count = upsert_13f_holdings_rows(parsed)

    manifest = read_manifest("13f")
    quarters = manifest.get("quarters") or []
    if quarter_key not in quarters:
        quarters.append(quarter_key)
    manifest["quarters"] = sorted(quarters, reverse=True)[-8:]
    manifest["last_ingest"] = datetime.now(UTC).isoformat()
    write_manifest("13f", manifest)

    return {"ok": True, "rows": count, "quarter_key": quarter_key}


def download_13f_quarter_zip(quarter_label: str, dest: Path | None = None) -> Path:
    """Download SEC 13F bulk ZIP for a quarter label like 2024q4."""
    label = quarter_label.lower().replace("-", "")
    url = f"{_SEC_13F_INDEX}/{label}_form13f.zip"
    qkey = quarter_key_from_label(label)
    dest = dest or quarter_dir("13f", qkey) / f"{label}_form13f.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0, follow_redirects=True, headers=_sec_headers()) as client:
        resp = client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest


def ingest_latest_13f_quarter(quarter_label: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.sec_bulk_13f_enabled:
        return {"ok": False, "message": "SEC bulk 13F ingest disabled"}
    label = quarter_label
    if not label:
        manifest = read_manifest("13f")
        label = (manifest.get("quarters") or [None])[0]
    if not label:
        label = "2024q4"
    qkey = quarter_key_from_label(label)
    zip_path = bulk_data_root() / "13f" / qkey / f"{label.lower()}_form13f.zip"
    if not zip_path.exists():
        try:
            zip_path = download_13f_quarter_zip(label, zip_path)
        except Exception as exc:
            logger.warning("13F bulk download failed for %s: %s", label, exc)
            return {"ok": False, "message": str(exc)}
    return ingest_13f_zip(zip_path, quarter_key=qkey)
