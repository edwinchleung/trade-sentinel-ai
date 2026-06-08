"""Shared yfinance fetch bundle — one Ticker session per symbol for lite scans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yfinance as yf

from trade_sentinel_api.models.schemas import EarningsSnapshot, FundamentalsSnapshot, MacdSnapshot
from trade_sentinel_api.services.earnings import _parse_yfinance_next_earnings
from trade_sentinel_api.services.earnings import _safe_float as earn_safe_float
from trade_sentinel_api.services.fundamentals import (
    _REVENUE_ROWS,
    _fundamentals_from_yf_data,
    _row_value,
)
from trade_sentinel_api.services.market_data import _resolve_live_quote
from trade_sentinel_api.services.technicals import compute_macd, compute_rsi


@dataclass
class TickerDataBundle:
    symbol: str
    stock: Any = None
    info: dict = field(default_factory=dict)
    hist: Any = None
    q_inc: Any = None
    q_bal: Any = None
    q_cf: Any = None
    annual: Any = None
    calendar: Any = None
    load_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.load_error is None and self.hist is not None and not getattr(self.hist, "empty", True)


def load_hist_only_sync(
    symbol: str,
    *,
    hist_prefetch: Any = None,
) -> tuple[Any, float, float | None]:
    """Load OHLCV history and basic quote fields without fundamentals."""
    sym = symbol.upper().strip()
    hist = hist_prefetch
    if hist is not None and not getattr(hist, "empty", True):
        close = hist["Close"]
        volume = hist["Volume"]
        price = float(close.iloc[-1])
        vol_avg = float(volume.tail(30).mean()) if len(volume) >= 1 else None
        vol_ratio = (int(volume.iloc[-1]) / vol_avg) if vol_avg and vol_avg > 0 else None
        return hist, price, vol_ratio

    try:
        stock = yf.Ticker(sym)
        hist = stock.history(period="3y", interval="1d")
        if hist is None or getattr(hist, "empty", True):
            return None, 0.0, None
        info = stock.info or {}
        close = hist["Close"]
        volume = hist["Volume"]
        price = float(info.get("regularMarketPrice") or info.get("currentPrice") or close.iloc[-1])
        vol_avg = float(volume.tail(30).mean()) if len(volume) >= 1 else None
        vol_ratio = (int(volume.iloc[-1]) / vol_avg) if vol_avg and vol_avg > 0 else None
        return hist, price, vol_ratio
    except Exception:
        return None, 0.0, None


def load_ticker_bundle_sync(
    symbol: str,
    *,
    hist_prefetch: Any = None,
) -> TickerDataBundle:
    """Load market + fundamentals + earnings inputs in one yfinance session."""
    sym = symbol.upper().strip()
    bundle = TickerDataBundle(symbol=sym)
    try:
        stock = yf.Ticker(sym)
        bundle.stock = stock
        if hist_prefetch is not None and not getattr(hist_prefetch, "empty", True):
            bundle.hist = hist_prefetch
        else:
            bundle.hist = stock.history(period="3y", interval="1d")
        bundle.info = stock.info or {}
        bundle.q_inc = stock.quarterly_income_stmt
        bundle.q_bal = stock.quarterly_balance_sheet
        bundle.q_cf = stock.quarterly_cashflow
        bundle.annual = stock.financials
        bundle.calendar = stock.calendar
    except Exception as exc:
        bundle.load_error = str(exc)
    return bundle


def market_from_bundle(bundle: TickerDataBundle) -> dict:
    """Derive market snapshot dict from a loaded bundle."""
    empty = {
        "price": None,
        "change_pct": None,
        "volume": None,
        "volume_avg_30d": None,
        "volume_ratio": None,
        "rsi": None,
        "macd": None,
        "price_history": [],
        "week52": {},
        "market_state": None,
        "price_source": None,
        "previous_close": None,
        "regular_market_price": None,
        "extended_price": None,
        "is_extended_hours": False,
        "quote_as_of": None,
    }
    if not bundle.ok:
        return empty

    hist = bundle.hist
    info = bundle.info
    close = hist["Close"]
    volume = hist["Volume"]
    quote = _resolve_live_quote(info, hist)
    vol_last = int(volume.iloc[-1])
    vol_avg = float(volume.tail(30).mean()) if len(volume) >= 1 else None
    vol_ratio = (vol_last / vol_avg) if vol_avg and vol_avg > 0 else None
    rsi = compute_rsi(close)
    macd_raw = compute_macd(close)
    macd = MacdSnapshot(**macd_raw)

    price_history = [
        {"date": idx.strftime("%Y-%m-%d"), "close": round(float(row["Close"]), 2)}
        for idx, row in hist.tail(30).iterrows()
    ]

    week52 = {
        "low": info.get("fiftyTwoWeekLow"),
        "high": info.get("fiftyTwoWeekHigh"),
    }

    return {
        "price": quote["price"],
        "change_pct": quote["change_pct"],
        "volume": vol_last,
        "volume_avg_30d": round(vol_avg, 0) if vol_avg else None,
        "volume_ratio": round(vol_ratio, 2) if vol_ratio else None,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "macd": macd,
        "price_history": price_history,
        "week52": week52,
        "hist": hist,
        **{k: quote[k] for k in (
            "market_state", "price_source", "previous_close",
            "regular_market_price", "extended_price", "is_extended_hours", "quote_as_of",
        )},
    }


def fundamentals_from_bundle(
    bundle: TickerDataBundle,
    current_price: float | None,
) -> FundamentalsSnapshot:
    if bundle.load_error or bundle.stock is None:
        return FundamentalsSnapshot(data_available=False, message="Fundamentals data unavailable.")
    return _fundamentals_from_yf_data(
        bundle.symbol,
        bundle.stock,
        bundle.info,
        bundle.q_inc,
        bundle.q_bal,
        bundle.q_cf,
        bundle.annual,
        bundle.hist,
        current_price,
    )


def prefetch_hist_chunk(symbols: list[str], *, period: str = "3y") -> dict[str, Any]:
    """Batch-download OHLCV for a chunk via yf.download (one HTTP round-trip)."""
    if not symbols:
        return {}
    syms = [s.upper().strip() for s in symbols if s.strip()]
    if not syms:
        return {}

    try:
        if len(syms) == 1:
            df = yf.download(
                syms[0],
                period=period,
                interval="1d",
                progress=False,
                auto_adjust=True,
            )
            if df is not None and not df.empty:
                return {syms[0]: df}
            return {}

        combined = yf.download(
            " ".join(syms),
            period=period,
            interval="1d",
            group_by="ticker",
            threads=False,
            progress=False,
            auto_adjust=True,
        )
    except Exception:
        return {}

    if combined is None or combined.empty:
        return {}

    result: dict[str, Any] = {}
    if not hasattr(combined.columns, "nlevels") or combined.columns.nlevels < 2:
        result[syms[0]] = combined
        return result

    for sym in syms:
        try:
            sub = combined[sym].dropna(how="all")
            if not sub.empty:
                result[sym] = sub
        except (KeyError, TypeError, AttributeError):
            continue
    return result


def _chunk_symbols(symbols: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [symbols]
    return [symbols[i : i + size] for i in range(0, len(symbols), size)]


def earnings_from_bundle(bundle: TickerDataBundle) -> EarningsSnapshot:
    if bundle.load_error or bundle.stock is None:
        return EarningsSnapshot(data_available=False, message="Earnings data unavailable.")

    next_date, days_until = _parse_yfinance_next_earnings(
        bundle.stock, bundle.info, bundle.calendar
    )
    last_eps_actual = earn_safe_float(bundle.info.get("trailingEps"))
    last_eps_estimate = earn_safe_float(bundle.info.get("forwardEps"))

    rev_actual = None
    if bundle.q_inc is not None and not bundle.q_inc.empty:
        rev_actual = _row_value(bundle.q_inc, _REVENUE_ROWS, 0)

    return EarningsSnapshot(
        next_report_date=next_date,
        days_until=days_until,
        last_eps_actual=last_eps_actual,
        last_eps_estimate=last_eps_estimate,
        last_revenue_actual=rev_actual,
        data_available=bool(next_date or last_eps_actual or rev_actual),
    )
