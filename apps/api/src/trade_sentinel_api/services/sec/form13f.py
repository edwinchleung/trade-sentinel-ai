"""SEC Form 13F institutional holdings changes (top filers + watchlist tickers)."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    Institutional13FChange,
    Institutional13FChanges,
    Institutional13FHolderRow,
    Institutional13FHolders,
    InstitutionalConvictionRow,
    InstitutionalConvictionScan,
)
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.institutional_crowding import compute_hhi, crowding_risk_from_hhi
from trade_sentinel_api.services.scan_batch import resolve_scan_universe
from trade_sentinel_api.services.sec.adapter import (
    fetch_company_filings,
    parse_filing,
    thirteenf_to_holdings,
)
from trade_sentinel_api.services.sec.bulk_storage import (
    count_13f_holders,
    has_13f_bulk_index,
    query_13f_by_ticker,
    sec_index_execute,
)
from trade_sentinel_api.services.sec.edgar import fetch_submissions_json, get_cik_for_ticker

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_FILERS_PATH = _DATA_DIR / "institutional_filers.json"
_CACHE_DIR = _DATA_DIR / "13f_cache"
_CUSIP_MAP_PATH = _DATA_DIR / "ticker_cusip_map.json"
_CHANGE_THRESHOLD = 0.25
_DEFAULT_CUSIP_SEED: dict[str, str] = {
    "AAPL": "037833100",
    "MSFT": "594918104",
    "GOOGL": "02079K305",
    "GOOG": "02079K107",
    "AMZN": "023135106",
    "META": "30303M102",
    "NVDA": "67066G104",
    "TSLA": "88160R101",
    "BRK.B": "084670702",
    "JPM": "46625H100",
    "V": "92826C839",
    "UNH": "91324P102",
    "XOM": "30231G102",
    "JNJ": "478160104",
    "WMT": "931142103",
    "MA": "57636Q104",
    "PG": "742718109",
    "HD": "437076102",
    "CVX": "166764100",
    "MRK": "58933Y105",
    "ABBV": "00287Y109",
    "PEP": "713448108",
    "KO": "191216100",
    "COST": "22160K105",
    "AVGO": "11135F101",
    "LLY": "532457108",
    "BAC": "060505104",
    "ORCL": "68389X105",
    "CRM": "79466L302",
    "AMD": "007903107",
}
_ISSUER_NAME_ALIASES: dict[str, str] = {
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "FACEBOOK": "META",
    "AMAZON COM": "AMZN",
}


def _load_filers() -> list[dict]:
    if not _FILERS_PATH.exists():
        return []
    return json.loads(_FILERS_PATH.read_text())


def _notable_filer_ciks() -> set[str]:
    return {f["cik"].zfill(10) for f in _load_filers()}


def _notable_filer_names() -> dict[str, str]:
    return {f["cik"].zfill(10): f["name"] for f in _load_filers()}


def _load_cusip_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    if _CUSIP_MAP_PATH.exists():
        mapping = json.loads(_CUSIP_MAP_PATH.read_text())
    for ticker, cusip in _DEFAULT_CUSIP_SEED.items():
        mapping.setdefault(ticker, cusip)
    return mapping


def _save_cusip_map(mapping: dict[str, str]) -> None:
    _CUSIP_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CUSIP_MAP_PATH.write_text(json.dumps(mapping, indent=2, sort_keys=True))


def _holdings_from_filing(filer_cik: str, accession: str, *, quarter_end_hint: str | None) -> tuple[list[dict], str | None]:
    """Fetch 13F holdings via EdgarTools."""
    try:
        filings = fetch_company_filings(filer_cik, "13F-HR", limit=8)
    except Exception:
        filings = []

    target = None
    normalized_acc = accession.replace("-", "")
    for filing in filings:
        acc = getattr(filing, "accession_no", None) or getattr(filing, "accession_number", None)
        if acc and acc.replace("-", "") == normalized_acc:
            target = filing
            break

    if target is None:
        try:
            from edgar import get_by_accession_number

            target = get_by_accession_number(accession)
        except Exception:
            return [], quarter_end_hint

    obj, _ = parse_filing(target)
    if obj is None:
        return [], quarter_end_hint
    return thirteenf_to_holdings(obj)


def _fetch_13f_holdings_for_filing(
    cik: str,
    accession: str,
    client: object | None = None,
    *,
    quarter_end_hint: str | None = None,
) -> tuple[list[dict], str | None]:
    del client
    return _holdings_from_filing(cik, accession, quarter_end_hint=quarter_end_hint)


def _filer_cache_path(filer_cik: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{filer_cik}.json"


def _load_filer_cache(filer_cik: str) -> list[dict]:
    path = _filer_cache_path(filer_cik)
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
    except (OSError, ValueError, json.JSONDecodeError):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return []
    if not isinstance(data, dict):
        return []
    quarters = data.get("quarters", [])
    return quarters if isinstance(quarters, list) else []


def _save_filer_quarter(filer_cik: str, quarter_end: str, holdings: list[dict], filing_date: str) -> None:
    quarters = _load_filer_cache(filer_cik)
    updated = [q for q in quarters if q.get("quarter_end") != quarter_end]
    updated.append(
        {
            "quarter_end": quarter_end,
            "filing_date": filing_date,
            "holdings": holdings,
        }
    )
    updated.sort(key=lambda q: q.get("quarter_end") or "", reverse=True)
    path = _filer_cache_path(filer_cik)
    payload = json.dumps({"quarters": updated[:8]}, indent=2)
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        path.write_text(payload, encoding="utf-8")


def _recent_13f_filings(cik: str, limit: int = 4) -> list[dict]:
    try:
        filings = fetch_company_filings(cik, "13F-HR", limit=max(limit * 2, limit))
    except Exception:
        filings = []

    if filings:
        out: list[dict] = []
        for filing in filings:
            form = getattr(filing, "form", "")
            if form not in ("13F-HR", "13F-HR/A"):
                continue
            acc = getattr(filing, "accession_no", None) or getattr(filing, "accession_number", None)
            if not acc:
                continue
            filing_date = getattr(filing, "filing_date", None)
            quarter_end = None
            for attr in ("report_period", "period_of_report", "quarter_end"):
                val = getattr(filing, attr, None)
                if val:
                    quarter_end = str(val)[:10]
                    break
            out.append(
                {
                    "accession": str(acc),
                    "filing_date": str(filing_date)[:10] if filing_date else None,
                    "quarter_end": quarter_end,
                }
            )
            if len(out) >= limit:
                break
        if out:
            return out

    data = fetch_submissions_json(cik)
    if data is None:
        return []
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accession = recent.get("accessionNumber", [])
    report_dates = recent.get("reportDate", [])
    out = []
    for i, form in enumerate(forms):
        if form not in ("13F-HR", "13F-HR/A"):
            continue
        acc = accession[i] if i < len(accession) else None
        if not acc:
            continue
        out.append(
            {
                "accession": acc,
                "filing_date": dates[i] if i < len(dates) else None,
                "quarter_end": report_dates[i] if i < len(report_dates) else None,
            }
        )
        if len(out) >= limit:
            break
    return out


def _match_holding(
    ticker: str,
    holdings: list[dict],
    *,
    cusip_map: dict[str, str],
) -> dict | None:
    symbol = ticker.upper()
    target_cusip = cusip_map.get(symbol)
    if target_cusip:
        for h in holdings:
            if (h.get("cusip") or "").upper() == target_cusip.upper():
                return h
    for h in holdings:
        name = (h.get("name") or "").upper()
        tokens = name.replace(",", "").split()
        if symbol in tokens or name.startswith(symbol + " "):
            if h.get("cusip"):
                cusip_map[symbol] = h["cusip"]
            return h
        alias = _ISSUER_NAME_ALIASES.get(name) or _ISSUER_NAME_ALIASES.get(tokens[0] if tokens else "")
        if alias == symbol:
            if h.get("cusip"):
                cusip_map[symbol] = h["cusip"]
            return h
    return None


def _classify_change(
    prior: float | None,
    current: float | None,
) -> Literal["new", "increased", "decreased", "exit", "held"]:
    p = prior or 0.0
    c = current or 0.0
    if p <= 0 and c > 0:
        return "new"
    if p > 0 and c <= 0:
        return "exit"
    if p <= 0 and c <= 0:
        return "held"
    delta = (c - p) / p
    if delta >= _CHANGE_THRESHOLD:
        return "increased"
    if delta <= -_CHANGE_THRESHOLD:
        return "decreased"
    return "held"


def build_cusip_ticker_index(cusip_map: dict[str, str] | None = None) -> dict[str, str]:
    mapping = cusip_map or _load_cusip_map()
    return {v.upper(): k.upper() for k, v in mapping.items() if v}


def _holding_by_cusip(holdings: list[dict], cusip: str | None) -> dict | None:
    if not cusip:
        return None
    target = cusip.upper()
    for h in holdings:
        if (h.get("cusip") or "").upper() == target:
            return h
    return None


def _ticker_from_holding(
    holding: dict,
    *,
    cusip_index: dict[str, str],
    cusip_map: dict[str, str],
) -> str | None:
    cusip = (holding.get("cusip") or "").upper()
    if cusip and cusip in cusip_index:
        return cusip_index[cusip]
    name = (holding.get("name") or "").upper()
    tokens = name.replace(",", "").split()
    if tokens:
        candidate = _ISSUER_NAME_ALIASES.get(name) or _ISSUER_NAME_ALIASES.get(tokens[0]) or tokens[0]
        if len(candidate) <= 5 and candidate.isalpha():
            if candidate in cusip_map or _match_holding(candidate, [holding], cusip_map=cusip_map):
                if holding.get("cusip"):
                    cusip_map[candidate] = holding["cusip"]
                    cusip_index[holding["cusip"].upper()] = candidate
                return candidate
    return None


def _refresh_filer_holdings_sync() -> tuple[dict[str, list[Institutional13FChange]], dict[str, int]]:
    """Fetch all tracked filers once and aggregate QoQ changes by ticker."""
    cusip_map = _load_cusip_map()
    cusip_index = build_cusip_ticker_index(cusip_map)
    ticker_changes: dict[str, list[Institutional13FChange]] = defaultdict(list)

    filers_refreshed = 0
    try:
        for filer in _load_filers():
            filer_cik = filer["cik"].zfill(10)
            filings = _recent_13f_filings(filer_cik, limit=2)
            if not filings:
                continue

            current_holdings: list[dict] = []
            prior_holdings: list[dict] = []
            quarter_end = None
            filer_had_current = False

            for idx, filing in enumerate(filings[:2]):
                holdings, qe = _fetch_13f_holdings_for_filing(
                    filer_cik,
                    filing["accession"],
                    quarter_end_hint=filing.get("quarter_end") or filing.get("filing_date"),
                )
                if idx == 0 and holdings:
                    filer_had_current = True
                if holdings and qe:
                    _save_filer_quarter(
                        filer_cik,
                        qe,
                        holdings,
                        filing.get("filing_date") or "",
                    )
                if idx == 0:
                    current_holdings = holdings
                    quarter_end = qe
                elif idx == 1:
                    prior_holdings = holdings

            if filer_had_current:
                filers_refreshed += 1

            cached = _load_filer_cache(filer_cik)
            if not prior_holdings and len(cached) >= 2:
                prior_holdings = cached[1].get("holdings", [])

            seen_cusips: set[str] = set()
            for match in current_holdings:
                cusip = (match.get("cusip") or "").upper()
                if cusip and cusip in seen_cusips:
                    continue
                if cusip:
                    seen_cusips.add(cusip)

                ticker = _ticker_from_holding(
                    match,
                    cusip_index=cusip_index,
                    cusip_map=cusip_map,
                )
                if not ticker:
                    continue

                prior_match = _holding_by_cusip(prior_holdings, match.get("cusip"))
                cur_shares = match.get("shares")
                prior_shares = prior_match.get("shares") if prior_match else None
                change_type = _classify_change(prior_shares, cur_shares)
                pct_change = None
                if prior_shares and cur_shares and prior_shares > 0:
                    pct_change = round((cur_shares - prior_shares) / prior_shares * 100, 1)

                quarter_note = f"Quarter ended {quarter_end}" if quarter_end else "QoQ vs prior 13F filing"
                ticker_changes[ticker.upper()].append(
                    Institutional13FChange(
                        filer_name=filer["name"],
                        filer_cik=filer_cik,
                        ticker=ticker.upper(),
                        shares=cur_shares,
                        value_usd=match.get("value"),
                        change_type=change_type,
                        prior_shares=prior_shares,
                        pct_change=pct_change,
                        quarter_end=quarter_end,
                        quarter_note=quarter_note,
                    )
                )
    except httpx.HTTPError:
        return {}, {"filers_refreshed": 0, "tickers_mapped": 0}
    finally:
        _save_cusip_map(cusip_map)

    result = dict(ticker_changes)
    meta = {"filers_refreshed": filers_refreshed, "tickers_mapped": len(result)}
    return result, meta


def refresh_tracked_filer_holdings() -> dict[str, list[Institutional13FChange]]:
    changes, _ = _refresh_filer_holdings_sync()
    return changes


def _conviction_from_changes(changes: list[Institutional13FChange]) -> bool:
    strong = sum(
        1 for c in changes if c.change_type in ("new", "increased") or c.change_type == "held"
    )
    new_or_up = sum(1 for c in changes if c.change_type in ("new", "increased"))
    if new_or_up >= 1 and len(changes) >= 2:
        return True
    return len(changes) >= 2 and strong >= 2


def _sort_filer_changes(changes: list[Institutional13FChange]) -> list[Institutional13FChange]:
    def rank(c: Institutional13FChange) -> tuple[int, float]:
        type_rank = 0 if c.change_type == "new" else 1 if c.change_type == "increased" else 2
        return (type_rank, -(abs(c.pct_change or 0)))

    return sorted(changes, key=rank)


def _changes_from_bulk_rows(ticker: str, rows: list[dict[str, Any]]) -> tuple[list[Institutional13FChange], list[float], str | None]:
    """Build QoQ changes from bulk index rows (multiple quarters)."""
    notable = _notable_filer_ciks()
    notable_names = _notable_filer_names()
    by_quarter: dict[str, dict[str, dict]] = {}
    for row in rows:
        qe = row.get("quarter_end") or ""
        cik = (row.get("filer_cik") or "").zfill(10)
        by_quarter.setdefault(qe, {})[cik] = row

    quarters = sorted(by_quarter.keys(), reverse=True)
    if not quarters:
        return [], [], None
    current_q = quarters[0]
    prior_q = quarters[1] if len(quarters) > 1 else None
    current = by_quarter.get(current_q, {})
    prior = by_quarter.get(prior_q, {}) if prior_q else {}

    changes: list[Institutional13FChange] = []
    shares_held: list[float] = []
    all_ciks = set(current) | set(prior)

    for cik in all_ciks:
        cur_row = current.get(cik)
        prior_row = prior.get(cik)
        cur_shares = float(cur_row["shares"]) if cur_row and cur_row.get("shares") is not None else None
        prior_shares = float(prior_row["shares"]) if prior_row and prior_row.get("shares") is not None else None
        if cur_shares is None and prior_shares is None:
            continue
        change_type = _classify_change(prior_shares, cur_shares)
        pct_change = None
        if prior_shares and cur_shares and prior_shares > 0:
            pct_change = round((cur_shares - prior_shares) / prior_shares * 100, 1)
        if cur_shares:
            shares_held.append(cur_shares)
        filer_name = (cur_row or prior_row or {}).get("filer_name") or notable_names.get(cik, cik)
        changes.append(
            Institutional13FChange(
                filer_name=str(filer_name),
                filer_cik=cik,
                ticker=ticker,
                shares=cur_shares,
                value_usd=float(cur_row["value_usd"]) if cur_row and cur_row.get("value_usd") is not None else None,
                change_type=change_type,
                prior_shares=prior_shares,
                pct_change=pct_change,
                quarter_end=current_q,
                quarter_note=f"Quarter ended {current_q}" if current_q else None,
                is_notable_filer=cik in notable,
            )
        )
    return changes, shares_held, current_q


def _fetch_ticker_changes_from_bulk(ticker: str, quarters: int) -> Institutional13FChanges | None:
    if not has_13f_bulk_index():
        return None
    rows = query_13f_by_ticker(ticker, limit_quarters=max(2, quarters))
    if not rows:
        return None
    changes, shares_held, current_q = _changes_from_bulk_rows(ticker, rows)
    notable = [c for c in changes if c.is_notable_filer]
    holder_count = count_13f_holders(ticker, current_q) if current_q else len(
        {r["filer_cik"] for r in rows if r.get("quarter_end") == current_q}
    )
    prior_q = sorted({r["quarter_end"] for r in rows}, reverse=True)
    prior_count = count_13f_holders(ticker, prior_q[1]) if len(prior_q) > 1 else None
    holder_delta = (holder_count - prior_count) if prior_count is not None else None
    hhi = compute_hhi(shares_held)
    return Institutional13FChanges(
        ticker=ticker,
        as_of=datetime.now(UTC),
        changes=_sort_filer_changes(changes),
        notable_filer_changes=_sort_filer_changes(notable),
        conviction_buy=_conviction_from_changes(changes),
        crowding_score=round(hhi, 4) if hhi is not None else None,
        crowding_risk=crowding_risk_from_hhi(hhi),
        holder_count=holder_count,
        holder_count_delta=holder_delta,
        data_scope="full_universe",
        data_available=len(changes) > 0,
        message=None if changes else "No 13F holders in bulk index for this ticker.",
        disclaimer="13F data is quarterly and up to 45 days delayed after quarter end.",
    )


def fetch_13f_holders_sync(ticker: str) -> Institutional13FHolders:
    symbol = ticker.upper()
    notable = _notable_filer_ciks()
    if has_13f_bulk_index():
        rows = query_13f_by_ticker(symbol, limit_quarters=1)
        quarters = sorted({r["quarter_end"] for r in rows}, reverse=True)
        current_q = quarters[0] if quarters else None
        holders = [
            Institutional13FHolderRow(
                filer_name=str(r.get("filer_name") or r.get("filer_cik")),
                filer_cik=(r.get("filer_cik") or "").zfill(10),
                shares=float(r["shares"]) if r.get("shares") is not None else None,
                value_usd=float(r["value_usd"]) if r.get("value_usd") is not None else None,
                quarter_end=r.get("quarter_end"),
                is_notable_filer=(r.get("filer_cik") or "").zfill(10) in notable,
            )
            for r in rows
            if r.get("quarter_end") == current_q
        ]
        holders.sort(key=lambda h: -(h.value_usd or 0))
        return Institutional13FHolders(
            ticker=symbol,
            as_of=datetime.now(UTC),
            quarter_end=current_q,
            holders=holders,
            holder_count=len(holders),
            data_scope="full_universe",
            data_available=len(holders) > 0,
        )
    result = _fetch_ticker_changes_sync(symbol, 1)
    holders = [
        Institutional13FHolderRow(
            filer_name=c.filer_name,
            filer_cik=c.filer_cik,
            shares=c.shares,
            value_usd=c.value_usd,
            quarter_end=c.quarter_end,
            is_notable_filer=c.filer_cik in notable,
        )
        for c in result.changes
        if c.shares
    ]
    return Institutional13FHolders(
        ticker=symbol,
        as_of=datetime.now(UTC),
        quarter_end=holders[0].quarter_end if holders else None,
        holders=holders,
        holder_count=len(holders),
        data_scope="tracked_filers_only",
        data_available=len(holders) > 0,
        message=result.message,
    )


async def fetch_13f_holders(ticker: str) -> Institutional13FHolders:
    cache_key = f"v1:holders:{ticker.upper()}"
    cached = get_cached("smart_money_13f", cache_key)
    if cached:
        return Institutional13FHolders(**cached)
    result = await asyncio.to_thread(fetch_13f_holders_sync, ticker.upper())
    ttl = get_settings().smart_money_13f_cache_hours * 3600
    set_cached_ttl("smart_money_13f", cache_key, result.model_dump(mode="json"), ttl)
    return result


def _fetch_ticker_changes_sync(ticker: str, quarters: int) -> Institutional13FChanges:
    bulk = _fetch_ticker_changes_from_bulk(ticker, quarters)
    if bulk is not None:
        return bulk

    issuer_cik = get_cik_for_ticker(ticker)
    if not issuer_cik:
        return Institutional13FChanges(
            ticker=ticker,
            as_of=datetime.now(UTC),
            data_available=False,
            message=f"No CIK for {ticker}.",
        )

    cusip_map = _load_cusip_map()
    changes: list[Institutional13FChange] = []
    shares_held: list[float] = []
    notable_ciks = _notable_filer_ciks()

    try:
        for filer in _load_filers():
            filer_cik = filer["cik"].zfill(10)
            filings = _recent_13f_filings(filer_cik, limit=max(2, quarters))
            if not filings:
                continue

            current_holdings: list[dict] = []
            prior_holdings: list[dict] = []
            quarter_end = None
            quarter_note = None

            for idx, filing in enumerate(filings[:quarters]):
                holdings, qe = _fetch_13f_holdings_for_filing(
                    filer_cik,
                    filing["accession"],
                    quarter_end_hint=filing.get("quarter_end") or filing.get("filing_date"),
                )
                if holdings and qe:
                    _save_filer_quarter(
                        filer_cik,
                        qe,
                        holdings,
                        filing.get("filing_date") or "",
                    )
                if idx == 0:
                    current_holdings = holdings
                    quarter_end = qe
                elif idx == 1:
                    prior_holdings = holdings

            cached = _load_filer_cache(filer_cik)
            if not prior_holdings and len(cached) >= 2:
                prior_holdings = cached[1].get("holdings", [])

            match = _match_holding(ticker, current_holdings, cusip_map=cusip_map)
            if not match:
                continue

            prior_match = _match_holding(ticker, prior_holdings, cusip_map=cusip_map)
            cur_shares = match.get("shares")
            prior_shares = prior_match.get("shares") if prior_match else None
            change_type = _classify_change(prior_shares, cur_shares)
            pct_change = None
            if prior_shares and cur_shares and prior_shares > 0:
                pct_change = round((cur_shares - prior_shares) / prior_shares * 100, 1)

            if cur_shares:
                shares_held.append(float(cur_shares))

            if quarter_end:
                quarter_note = f"Quarter ended {quarter_end}"
            elif prior_holdings:
                quarter_note = "QoQ vs prior 13F filing"

            changes.append(
                Institutional13FChange(
                    filer_name=filer["name"],
                    filer_cik=filer_cik,
                    ticker=ticker,
                    shares=cur_shares,
                    value_usd=match.get("value"),
                    change_type=change_type,
                    prior_shares=prior_shares,
                    pct_change=pct_change,
                    quarter_end=quarter_end,
                    quarter_note=quarter_note,
                    is_notable_filer=filer_cik in notable_ciks,
                )
            )
    except httpx.HTTPError as exc:
        return Institutional13FChanges(
            ticker=ticker,
            as_of=datetime.now(UTC),
            data_available=False,
            message=f"13F fetch failed: {exc}",
        )
    finally:
        _save_cusip_map(cusip_map)

    hhi = compute_hhi(shares_held)
    crowding = crowding_risk_from_hhi(hhi)
    conviction = _conviction_from_changes(changes)

    return Institutional13FChanges(
        ticker=ticker,
        as_of=datetime.now(UTC),
        changes=changes,
        notable_filer_changes=[c for c in changes if c.is_notable_filer],
        conviction_buy=conviction,
        crowding_score=round(hhi, 4) if hhi is not None else None,
        crowding_risk=crowding,
        holder_count=len([c for c in changes if c.shares]),
        data_scope="tracked_filers_only",
        data_available=len(changes) > 0,
        message=None if changes else "No 13F holdings found for this ticker among tracked filers.",
        disclaimer="13F data is quarterly and up to 45 days delayed after quarter end.",
    )


async def fetch_13f_changes(ticker: str, quarters: int = 2) -> Institutional13FChanges:
    cache_key = f"v2:{ticker.upper()}:{quarters}"
    cached = get_cached("smart_money_13f", cache_key)
    if cached:
        return Institutional13FChanges(**cached)

    result = await asyncio.to_thread(_fetch_ticker_changes_sync, ticker.upper(), quarters)
    ttl = get_settings().smart_money_13f_cache_hours * 3600
    set_cached_ttl("smart_money_13f", cache_key, result.model_dump(mode="json"), ttl)
    return result


async def scan_institutional_conviction(
    universe: str = "sp500",
    *,
    refresh: bool = False,
) -> InstitutionalConvictionScan:
    universe_key, tickers, _ = resolve_scan_universe(universe)
    cache_key = f"v2:conviction_scan:{universe_key}"
    cached = get_cached("smart_money_13f_conviction", cache_key)
    if cached and not refresh:
        return InstitutionalConvictionScan(**cached)

    universe_set = set(tickers)
    ticker_changes, meta = await asyncio.to_thread(_refresh_filer_holdings_sync)

    rows: list[InstitutionalConvictionRow] = []
    bulk_index = has_13f_bulk_index()
    for sym, changes in ticker_changes.items():
        if universe_set and sym not in universe_set:
            continue
        if _conviction_from_changes(changes):
            sorted_changes = _sort_filer_changes(changes)
            strong = [c for c in sorted_changes if c.change_type in ("new", "increased")]
            strongest = None
            best = None
            if strong:
                best = strong[0]
                strongest = best.change_type
                if best.pct_change is not None:
                    strongest = f"{best.change_type} ({best.pct_change:+.0f}%)"
            holder_count: int | None = None
            holder_delta: int | None = None
            if bulk_index:
                q_rows = sec_index_execute(
                    """
                    SELECT DISTINCT quarter_end FROM sec_13f_holdings
                    WHERE ticker = ? ORDER BY quarter_end DESC LIMIT 2
                    """,
                    (sym.upper(),),
                    fetch="all",
                )
                if q_rows:
                    current_q = q_rows[0][0]
                    holder_count = count_13f_holders(sym, current_q)
                    if len(q_rows) > 1:
                        prior_holders = count_13f_holders(sym, q_rows[1][0])
                        holder_delta = holder_count - prior_holders
            previews = [
                {
                    "filer_name": c.filer_name,
                    "change_type": c.change_type,
                    "pct_change": c.pct_change,
                    "shares": c.shares,
                    "prior_shares": c.prior_shares,
                    "value_usd": c.value_usd,
                    "quarter_end": c.quarter_end,
                    "quarter_note": c.quarter_note,
                }
                for c in strong[:5]
            ]
            rows.append(
                InstitutionalConvictionRow(
                    ticker=sym,
                    filer_count=len(changes),
                    holder_count=holder_count,
                    holder_count_delta=holder_delta,
                    conviction_buy=True,
                    top_filers=[c.filer_name for c in sorted_changes[:3]],
                    strongest_change=strongest,
                    headline_filer=best.filer_name if best else None,
                    headline_pct_change=best.pct_change if best else None,
                    headline_value_usd=best.value_usd if best else None,
                    quarter_end=best.quarter_end if best else None,
                    filer_previews=previews,
                    filer_changes=sorted_changes,
                )
            )

    rows.sort(key=lambda r: -r.filer_count)
    label = universe_key.upper() if universe_key != "watchlist" else "watchlist"
    result = InstitutionalConvictionScan(
        as_of=datetime.now(UTC),
        universe=universe_key,  # type: ignore[arg-type]
        rows=rows,
        data_available=len(rows) > 0,
        message=None if rows else f"No institutional conviction signals in {label}.",
        filers_refreshed=meta.get("filers_refreshed", 0),
        tickers_mapped=meta.get("tickers_mapped", 0),
        data_scope="full_universe" if bulk_index else "tracked_filers_only",
    )
    ttl = get_settings().smart_money_13f_cache_hours * 3600
    set_cached_ttl("smart_money_13f_conviction", cache_key, result.model_dump(mode="json"), ttl)
    return result
