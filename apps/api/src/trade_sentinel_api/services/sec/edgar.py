import asyncio
import json
import logging
import threading
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    InsiderSummary,
    InsiderTimeline,
    InsiderTransaction,
    NotableInsiderTransaction,
)
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.sec.adapter import (
    fetch_company_filings,
    filing_to_insider_transactions,
    parse_form4_from_filing_url,
)
from trade_sentinel_api.services.sec.http import sec_get
from trade_sentinel_api.services.sec.insider_classification import (
    ClassificationMode,
    classify_insider_transaction,
    detect_cluster_buying,
)

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_CIK_DISK_CACHE_PATH = _DATA_DIR / "company_tickers_cache.json"
_CIK_SEED_PATH = _DATA_DIR / "company_tickers_seed.json"
_CIK_DISK_CACHE_DAYS = 7
_MIN_CIK_MAP_ENTRIES = 1000

_CIK_LOCK = threading.Lock()
_CIK_CACHE: dict[str, str] | None = None
_CIK_FAILED_UNTIL: datetime | None = None
_CIK_MAP_UNAVAILABLE = False
_CIK_USING_FALLBACK = False


class _SecGetClient(Protocol):
    def get(self, url: str) -> httpx.Response: ...


def _normalize_cik_map(raw: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for ticker, cik in raw.items():
        symbol = str(ticker).upper().strip()
        if not symbol:
            continue
        mapping[symbol] = str(cik).strip().zfill(10)
    return mapping


def _load_cik_seed() -> dict[str, str]:
    if not _CIK_SEED_PATH.exists():
        return {}
    try:
        payload = json.loads(_CIK_SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if isinstance(payload, dict) and "mapping" in payload:
        return _normalize_cik_map(payload["mapping"])
    if isinstance(payload, dict):
        return _normalize_cik_map(payload)
    return {}


def _cik_map_is_persistable(mapping: dict[str, str]) -> bool:
    return len(mapping) >= _MIN_CIK_MAP_ENTRIES


def _resolve_cik_map(mapping: dict[str, str]) -> dict[str, str]:
    """Prefer a full SEC map; merge bundled seed when the map is incomplete."""
    seed = _load_cik_seed()
    if len(mapping) < _MIN_CIK_MAP_ENTRIES:
        if seed:
            if mapping:
                logger.warning(
                    "CIK map has only %d entries — merging with bundled seed (%d tickers)",
                    len(mapping),
                    len(seed),
                )
            return {**seed, **mapping}
        return mapping
    if not seed:
        return mapping
    merged = dict(mapping)
    for ticker, cik in seed.items():
        merged.setdefault(ticker, cik)
    return merged


def _load_cik_disk_cache(*, allow_stale: bool) -> tuple[dict[str, str] | None, bool]:
    if not _CIK_DISK_CACHE_PATH.exists():
        return None, False
    try:
        payload = json.loads(_CIK_DISK_CACHE_PATH.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(str(payload.get("fetched_at", "")).replace("Z", "+00:00"))
        mapping = _normalize_cik_map(payload.get("mapping", {}))
        if not mapping or not _cik_map_is_persistable(mapping):
            return None, False
        age = datetime.now(UTC) - fetched_at.astimezone(UTC)
        is_stale = age > timedelta(days=_CIK_DISK_CACHE_DAYS)
        if is_stale and not allow_stale:
            return None, True
        return mapping, is_stale
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None, False


def _save_cik_disk_cache(mapping: dict[str, str]) -> None:
    if not _cik_map_is_persistable(mapping):
        logger.debug(
            "Skipping CIK disk cache write (%d entries < %d)",
            len(mapping),
            _MIN_CIK_MAP_ENTRIES,
        )
        return
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": datetime.now(UTC).isoformat(),
            "mapping": mapping,
        }
        _CIK_DISK_CACHE_PATH.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as exc:
        logger.debug("Could not persist SEC CIK disk cache: %s", exc)


def _fallback_cik_map(detail: str) -> dict[str, str]:
    global _CIK_MAP_UNAVAILABLE, _CIK_USING_FALLBACK

    disk, is_stale = _load_cik_disk_cache(allow_stale=True)
    if disk:
        resolved = _resolve_cik_map(disk)
        _CIK_MAP_UNAVAILABLE = True
        _CIK_USING_FALLBACK = True
        logger.warning(
            "SEC company ticker list unavailable (%s) — using %s disk cache (%d tickers)",
            detail,
            "stale" if is_stale else "cached",
            len(resolved),
        )
        return resolved

    seed = _load_cik_seed()
    if seed:
        _CIK_MAP_UNAVAILABLE = True
        _CIK_USING_FALLBACK = True
        logger.warning(
            "SEC company ticker list unavailable (%s) — using bundled CIK seed (%d tickers)",
            detail,
            len(seed),
        )
        return seed

    _CIK_MAP_UNAVAILABLE = True
    _CIK_USING_FALLBACK = False
    logger.warning("SEC company ticker list unavailable after retries: %s", detail)
    raise httpx.HTTPError(f"SEC company_tickers.json failed: {detail}")


def _fetch_company_tickers_with_retry() -> dict[str, str]:
    global _CIK_MAP_UNAVAILABLE, _CIK_USING_FALLBACK

    url = "https://www.sec.gov/files/company_tickers.json"
    last_status: int | None = None
    try:
        resp = sec_get(url, timeout=20.0)
        last_status = resp.status_code
        if resp.status_code >= 400:
            resp.raise_for_status()
        data = resp.json()
        mapping: dict[str, str] = {}
        for entry in data.values():
            ticker = str(entry.get("ticker", "")).upper()
            cik = str(entry.get("cik_str", "")).zfill(10)
            if ticker:
                mapping[ticker] = cik
        mapping = _resolve_cik_map(mapping)
        if _cik_map_is_persistable(mapping):
            _CIK_MAP_UNAVAILABLE = False
            _CIK_USING_FALLBACK = False
            _save_cik_disk_cache(mapping)
        else:
            _CIK_MAP_UNAVAILABLE = True
            _CIK_USING_FALLBACK = True
        return mapping
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        detail = f"HTTP {last_status}" if last_status else str(exc)
        return _fallback_cik_map(detail)


def get_company_tickers() -> dict[str, str]:
    """Return ticker -> CIK map; shared across threads with lock + negative cache."""
    global _CIK_CACHE, _CIK_FAILED_UNTIL, _CIK_USING_FALLBACK

    now = datetime.now(UTC)
    if _CIK_CACHE is not None:
        return _CIK_CACHE

    with _CIK_LOCK:
        if _CIK_CACHE is not None:
            return _CIK_CACHE

        if _CIK_FAILED_UNTIL is not None and now < _CIK_FAILED_UNTIL:
            fallback = _load_cik_disk_cache(allow_stale=True)[0] or _load_cik_seed()
            if fallback:
                _CIK_CACHE = _resolve_cik_map(fallback)
                _CIK_USING_FALLBACK = True
                return _CIK_CACHE

        fresh_disk = _load_cik_disk_cache(allow_stale=False)[0]
        if fresh_disk:
            _CIK_CACHE = _resolve_cik_map(fresh_disk)
            _CIK_USING_FALLBACK = False
            _CIK_MAP_UNAVAILABLE = False
            return _CIK_CACHE

        try:
            _CIK_CACHE = _fetch_company_tickers_with_retry()
            _CIK_FAILED_UNTIL = None
            return _CIK_CACHE
        except httpx.HTTPError:
            settings = get_settings()
            _CIK_FAILED_UNTIL = datetime.now(UTC) + timedelta(
                seconds=settings.sec_cik_failure_ttl_seconds
            )
            raise


def _company_tickers() -> dict[str, str]:
    return get_company_tickers()


@lru_cache(maxsize=1)
def _cik_to_ticker() -> dict[str, str]:
    """Map zero-padded CIK -> primary ticker symbol."""
    reverse: dict[str, str] = {}
    for ticker, cik in _company_tickers().items():
        reverse.setdefault(cik, ticker)
    return reverse


def get_ticker_for_cik(cik: str) -> str | None:
    try:
        mapping = _cik_to_ticker()
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    normalized = str(cik).strip().zfill(10)
    return mapping.get(normalized)


def parse_form4_from_url(doc_url: str, client: _SecGetClient | None = None) -> dict | None:
    """Fetch and parse a Form 4 filing via EdgarTools."""
    del client
    return parse_form4_from_filing_url(doc_url)


def _empty_timeline(ticker: str, message: str) -> InsiderTimeline:
    if _CIK_MAP_UNAVAILABLE and message == "SEC company ticker list unavailable.":
        logger.debug("insider_timeline_empty ticker=%s message=%s", ticker, message)
    else:
        logger.warning("insider_timeline_empty ticker=%s message=%s", ticker, message)
    return InsiderTimeline(
        ticker=ticker,
        transactions=[],
        data_available=False,
        message=message,
    )


async def fetch_insider_timeline(ticker: str, limit: int = 10) -> InsiderTimeline:
    symbol = ticker.upper().strip()
    return await asyncio.to_thread(_fetch_form4_sync, symbol, limit)


def _fetch_submissions_json(cik: str) -> dict | None:
    cache_key = cik.zfill(10)
    cached = get_cached("sec_submissions", cache_key)
    if isinstance(cached, dict):
        return cached

    url = f"https://data.sec.gov/submissions/CIK{cache_key}.json"
    try:
        resp = sec_get(url, timeout=20.0)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    ttl = get_settings().sec_submissions_cache_seconds
    set_cached_ttl("sec_submissions", cache_key, data, ttl)
    return data


def fetch_submissions_json(cik: str) -> dict | None:
    """Public wrapper for per-CIK submissions cache (used by sec_filings)."""
    return _fetch_submissions_json(cik)


def _fetch_form4_sync(ticker: str, limit: int) -> InsiderTimeline:
    try:
        _company_tickers()
    except (httpx.HTTPError, ValueError, KeyError):
        return _empty_timeline(ticker, "SEC company ticker list unavailable.")

    if get_cik_for_ticker(ticker) is None:
        return _empty_timeline(ticker, "CIK not found for ticker.")

    try:
        filings = fetch_company_filings(ticker, "4", max(limit * 3, limit))
    except Exception as exc:
        logger.debug("EdgarTools Form 4 fetch failed for %s: %s", ticker, exc)
        return _empty_timeline(ticker, "SEC Form 4 filings unavailable.")

    results: list[InsiderTransaction] = []
    for filing in filings:
        if len(results) >= limit:
            break
        batch = filing_to_insider_transactions(filing, limit=limit - len(results))
        results.extend(batch)
        if len(results) >= limit:
            break

    if not results:
        return _empty_timeline(ticker, "No recent Form 4 filings found for this issuer.")

    return InsiderTimeline(ticker=ticker, transactions=results[:limit], data_available=True)


def get_cik_for_ticker(ticker: str) -> str | None:
    try:
        tickers = _company_tickers()
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    return tickers.get(ticker.upper().strip())


def clear_edgar_cache() -> None:
    global _CIK_CACHE, _CIK_FAILED_UNTIL, _CIK_MAP_UNAVAILABLE, _CIK_USING_FALLBACK
    from trade_sentinel_api.services.cache import clear_cached_by_prefix
    from trade_sentinel_api.services.sec.http import clear_sec_http_state

    with _CIK_LOCK:
        _CIK_CACHE = None
        _CIK_FAILED_UNTIL = None
        _CIK_MAP_UNAVAILABLE = False
        _CIK_USING_FALLBACK = False
    _cik_to_ticker.cache_clear()
    clear_cached_by_prefix("sec_submissions")
    clear_sec_http_state()


def warm_company_tickers_cache() -> bool:
    """Pre-load SEC CIK map; returns True on success."""
    try:
        get_company_tickers()
        return True
    except httpx.HTTPError:
        return False


def _classify_insider_side(
    tx: InsiderTransaction,
    *,
    mode: ClassificationMode = "open_market",
) -> str | None:
    """Return 'buy', 'sell', 'excluded', or None for a single transaction."""
    side = classify_insider_transaction(tx, mode=mode)
    if side in ("buy", "sell"):
        return side
    if side == "excluded":
        return "excluded"
    return None


def summarize_insider_activity(
    transactions: list[InsiderTransaction],
    *,
    mode: ClassificationMode = "open_market",
) -> InsiderSummary:
    """Aggregate Form 4 transactions into a 90-day signal summary."""
    if not transactions:
        return InsiderSummary(data_available=False)

    cutoff = date.today() - timedelta(days=90)
    buy_shares = 0.0
    sell_shares = 0.0
    buy_count = 0
    sell_count = 0
    open_market_buy_count = 0
    open_market_sell_count = 0
    excluded_count = 0
    notable: list[NotableInsiderTransaction] = []
    recent_activity = 0
    recent_for_cluster: list[InsiderTransaction] = []

    for tx in transactions:
        try:
            filing = date.fromisoformat(tx.filing_date[:10])
        except ValueError:
            filing = date.today()
        if filing < cutoff:
            continue

        recent_activity += 1
        shares = tx.shares or 0
        price = tx.price or 0
        notional = shares * price if shares and price else 0
        side = _classify_insider_side(tx, mode=mode)

        if side == "buy":
            buy_shares += shares
            buy_count += 1
            if tx.is_open_market or (tx.transaction_code or "").upper()[:1] == "P":
                open_market_buy_count += 1
                recent_for_cluster.append(tx)
        elif side == "sell":
            sell_shares += shares
            sell_count += 1
            if tx.is_open_market or (tx.transaction_code or "").upper()[:1] == "S":
                open_market_sell_count += 1
        elif side == "excluded":
            excluded_count += 1

        if notional >= 1_000_000 and side in ("buy", "sell"):
            notable.append(
                NotableInsiderTransaction(
                    filing_date=tx.filing_date,
                    insider_name=tx.insider_name,
                    transaction_type=tx.transaction_type,
                    shares=tx.shares,
                    price=tx.price,
                    notional=round(notional, 2),
                )
            )

    net = buy_shares - sell_shares
    if buy_shares > sell_shares * 2 and buy_count > 0:
        sentiment = "accumulation"
    elif sell_shares > buy_shares * 2 and sell_count > 0:
        sentiment = "distribution"
    else:
        sentiment = "neutral"

    cluster_buying = detect_cluster_buying(recent_for_cluster)

    new_insiders: list[dict[str, str | float | None]] = []
    for tx in transactions:
        if tx.source_form != "3":
            continue
        try:
            filing = date.fromisoformat(tx.filing_date[:10])
        except ValueError:
            continue
        if filing < cutoff:
            continue
        new_insiders.append(
            {
                "insider_name": tx.insider_name,
                "title": tx.title,
                "shares": tx.shares,
                "filing_date": tx.filing_date,
            }
        )

    bullets: list[str] = []
    if buy_count or sell_count:
        bullets.append(
            f"90-day open-market insider flow: {buy_count} buy(s) ({buy_shares:,.0f} sh) vs "
            f"{sell_count} sell(s) ({sell_shares:,.0f} sh); net {net:+,.0f} shares."
        )
        bullets.append(f"Open-market sentiment: {sentiment}.")
        if excluded_count:
            bullets.append(
                f"{excluded_count} grant/exercise/gift filing(s) excluded from sentiment."
            )
        if cluster_buying:
            bullets.append("Cluster buying: multiple insiders purchased within 7 days.")
    if new_insiders:
        bullets.append(f"{len(new_insiders)} new insider appointment(s) (Form 3) in the last 90 days.")
    elif recent_activity:
        bullets.append(
            f"{recent_activity} Form 4 filing(s) in the last 90 days; "
            "no open-market buy/sell classification (grants/exercises/metadata only)."
        )
    if notable:
        bullets.append(f"{len(notable)} notable open-market transaction(s) exceeding $1M notional.")

    has_flow = buy_count > 0 or sell_count > 0
    return InsiderSummary(
        net_shares_90d=net,
        buy_count=buy_count,
        sell_count=sell_count,
        open_market_buy_count=open_market_buy_count,
        open_market_sell_count=open_market_sell_count,
        excluded_count=excluded_count,
        cluster_buying=cluster_buying,
        sentiment=sentiment,
        notable_transactions=notable[:5],
        new_insiders_90d=new_insiders[:10],
        analysis_bullets=bullets,
        data_available=has_flow or recent_activity > 0,
    )
