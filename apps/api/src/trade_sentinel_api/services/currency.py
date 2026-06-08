"""FX helpers for normalizing financial statement amounts to USD."""

from __future__ import annotations

import logging

import yfinance as yf

from trade_sentinel_api.services.cache import get_cached, set_cached_ttl

logger = logging.getLogger(__name__)

_FX_CACHE_TTL = 14400
_SANITY_FCF_MCAP_RATIO = 50.0


def normalize_ccy(code: str | None) -> str | None:
    if not code or not str(code).strip():
        return None
    return str(code).strip().upper()


def currencies_differ(trading: str | None, financial: str | None) -> bool:
    t = normalize_ccy(trading)
    f = normalize_ccy(financial)
    if not t or not f:
        return False
    return t != f


def convert_amount(amount: float | None, rate: float | None) -> float | None:
    if amount is None or rate is None or rate <= 0:
        return None
    return amount * rate


def fetch_fx_rate_sync(from_ccy: str, to_ccy: str) -> float | None:
    """Return units of `to_ccy` per 1 unit of `from_ccy` (multiply from-amount by rate)."""
    src = normalize_ccy(from_ccy)
    dst = normalize_ccy(to_ccy)
    if not src or not dst or src == dst:
        return 1.0

    cache_key = f"{src}:{dst}"
    cached = get_cached("fx", cache_key)
    if isinstance(cached, dict) and cached.get("rate") is not None:
        return float(cached["rate"])

    rate = _yahoo_fx_rate(src, dst)
    if rate is None:
        inv = _yahoo_fx_rate(dst, src)
        if inv is not None and inv > 0:
            rate = 1.0 / inv

    if rate is not None and rate > 0:
        set_cached_ttl("fx", cache_key, {"rate": rate}, _FX_CACHE_TTL)
        return rate
    return None


def _yahoo_fx_rate(from_ccy: str, to_ccy: str) -> float | None:
    pair = f"{from_ccy}{to_ccy}=X"
    try:
        hist = yf.Ticker(pair).history(period="5d")
        if hist is not None and not hist.empty:
            close = float(hist["Close"].iloc[-1])
            if close > 0:
                return close
    except Exception as exc:
        logger.debug("FX fetch failed for %s: %s", pair, exc)
    return None


def financial_currency_is_usd(financial: str | None) -> bool:
    return normalize_ccy(financial) == "USD"


def fx_rate_financial_to_usd(financial: str | None) -> float | None:
    """Units of USD per 1 unit of financial currency. 1.0 when already USD."""
    fin = normalize_ccy(financial)
    if not fin:
        return None
    if fin == "USD":
        return 1.0
    return fetch_fx_rate_sync(fin, "USD")


def fcf_mcap_ratio_suspicious(fcf: float | None, market_cap: float | None) -> bool:
    if fcf is None or market_cap is None or market_cap <= 0 or fcf <= 0:
        return False
    return (fcf / market_cap) > _SANITY_FCF_MCAP_RATIO
