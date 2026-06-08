"""Lit-market volume footprint: OBV, A/D, VWAP deviation from OHLCV."""

from __future__ import annotations

import asyncio
import contextvars
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    VolumeFootprint,
    VolumeScanResult,
    VolumeScanRow,
)
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.polygon_client import fetch_ohlcv, is_polygon_enabled
from trade_sentinel_api.services.scan_batch import (
    apply_scan_response_filter,
    resolve_scan_universe,
    scan_cache_ttl_seconds,
    scan_universe_chunked,
)
from trade_sentinel_api.services.yfinance_bundle import load_hist_only_sync, prefetch_hist_chunk

_LOOKBACK = 20
_volume_hist_prefetch: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "volume_hist_prefetch",
    default={},
)


def _compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = close.diff().fillna(0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (direction * volume).cumsum()


def _compute_ad_line(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    clv = ((close - low) - (high - close)) / (high - low).replace(0, pd.NA)
    clv = clv.fillna(0)
    return (clv * volume).cumsum()


def _rolling_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int) -> pd.Series:
    typical = (high + low + close) / 3
    pv = typical * volume
    vol_sum = volume.rolling(window).sum()
    return pv.rolling(window).sum() / vol_sum.replace(0, pd.NA)


def _slope(series: pd.Series) -> float:
    """Linear slope over the series window (normalized by length)."""
    if series is None or len(series) < 2:
        return 0.0
    y = series.astype(float).values
    x = np.arange(len(y), dtype=float)
    if np.allclose(y, y[0]):
        return 0.0
    coeff = np.polyfit(x, y, 1)
    return float(coeff[0])


def _divergence(price_slope: float, indicator_slope: float) -> str | None:
    """Detect trend divergence: price up + indicator down = bearish; price down + indicator up = bullish."""
    price_up = price_slope > 0
    price_down = price_slope < 0
    ind_up = indicator_slope > 0
    ind_down = indicator_slope < 0
    if price_up and ind_down:
        return "bearish"
    if price_down and ind_up:
        return "bullish"
    return None


def build_volume_footprint(hist: pd.DataFrame, *, price: float, volume_ratio: float | None) -> VolumeFootprint:
    empty = VolumeFootprint(current_price=price, data_available=False, message="Insufficient OHLCV history.")
    if hist is None or hist.empty or len(hist) < _LOOKBACK + 5:
        return empty

    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]

    window = hist.tail(_LOOKBACK)
    close_w = window["Close"]
    high_w = window["High"]
    low_w = window["Low"]
    vol_w = window["Volume"]

    obv = _compute_obv(close, volume)
    ad_line = _compute_ad_line(high, low, close, volume)
    vwap = _rolling_vwap(high, low, close, volume, _LOOKBACK)

    obv_w = obv.tail(_LOOKBACK)
    ad_w = ad_line.tail(_LOOKBACK)

    price_slope = _slope(close_w)
    obv_slope = _slope(obv_w)
    ad_slope = _slope(ad_w)

    obv_divergence = _divergence(price_slope, obv_slope)
    ad_divergence = _divergence(price_slope, ad_slope)

    price_start = float(close_w.iloc[0])
    price_end = float(close_w.iloc[-1])
    price_chg_pct = ((price_end - price_start) / price_start * 100) if price_start else 0.0

    vwap_last = float(vwap.iloc[-1]) if pd.notna(vwap.iloc[-1]) else None
    vwap_dev_pct = None
    vwap_signal = None
    if vwap_last and price > 0:
        vwap_dev_pct = round((price - vwap_last) / vwap_last * 100, 2)
        if vwap_dev_pct > 1 and (volume_ratio or 0) > 1.2:
            vwap_signal = "sustained_above_vwap"
        elif abs(vwap_dev_pct) < 0.5 and (volume_ratio or 0) > 1.5 and price_chg_pct < 0:
            vwap_signal = "rejection_at_vwap"

    quiet_accumulation = (
        obv_divergence == "bullish"
        and (volume_ratio or 0) >= 0.8
        and abs(price_chg_pct) <= 2.0
    )

    stance = "neutral"
    if obv_divergence == "bullish" or quiet_accumulation:
        stance = "accumulation"
    elif obv_divergence == "bearish" or ad_divergence == "bearish":
        stance = "distribution"

    bullets: list[str] = []
    if obv_divergence:
        bullets.append(f"OBV divergence ({_LOOKBACK}d): {obv_divergence}.")
    if ad_divergence:
        bullets.append(f"A/D line divergence ({_LOOKBACK}d): {ad_divergence}.")
    if vwap_dev_pct is not None:
        bullets.append(f"Price vs {_LOOKBACK}d VWAP: {vwap_dev_pct:+.1f}%.")
    if quiet_accumulation:
        bullets.append("Quiet accumulation: OBV rising while price flat/down.")

    return VolumeFootprint(
        current_price=price,
        obv_divergence=obv_divergence,
        ad_divergence=ad_divergence,
        vwap_deviation_pct=vwap_dev_pct,
        vwap_signal=vwap_signal,
        volume_ratio=volume_ratio,
        quiet_accumulation=quiet_accumulation,
        stance=stance,
        analysis_bullets=bullets,
        data_available=True,
    )


async def fetch_volume_footprint(ticker: str) -> VolumeFootprint:
    return await asyncio.to_thread(_fetch_sync, ticker.upper())


def _fetch_sync(ticker: str, *, hist_prefetch: Any = None) -> VolumeFootprint:
    if hist_prefetch is None:
        hist_prefetch = _volume_hist_prefetch.get({}).get(ticker.upper())
    hist, price, volume_ratio = load_hist_only_sync(ticker, hist_prefetch=hist_prefetch)
    if is_polygon_enabled() and (hist is None or getattr(hist, "empty", True)):
        poly_hist = fetch_ohlcv(ticker, days=60)
        if poly_hist is not None and not poly_hist.empty:
            hist = poly_hist
            if price <= 0:
                price = float(hist["Close"].iloc[-1])
    return build_volume_footprint(
        hist,
        price=price or 0,
        volume_ratio=volume_ratio,
    )


def _volume_signal_filter(universe_key: str):
    if universe_key in ("sp100", "sp500"):
        return lambda row: (
            row.quiet_accumulation
            or row.obv_divergence is not None
            or row.ad_divergence is not None
            or row.stance == "accumulation"
        )
    return lambda _row: True


def _build_volume_result(
    rows: list[VolumeScanRow],
    universe_key: str,
    scanned_count: int,
    as_of: datetime,
    *,
    fetched_count: int = 0,
    signals_only: bool = True,
    partial: bool = False,
    provider_degraded: bool = False,
) -> VolumeScanResult:
    stance_rank = {"accumulation": 0, "neutral": 1, "distribution": 2}
    sorted_rows = sorted(rows, key=lambda r: (stance_rank.get(r.stance, 3), -(r.volume_ratio or 0)))
    message = None
    if not sorted_rows:
        if fetched_count == 0:
            message = "Volume data could not be fetched for this universe."
        elif signals_only:
            message = (
                f"No accumulation volume signals in {universe_key} today "
                f"({fetched_count} tickers scanned)."
            )
        else:
            message = "Volume footprint data unavailable."
    return VolumeScanResult(
        as_of=as_of,
        universe=universe_key,  # type: ignore[arg-type]
        rows=sorted_rows,
        scanned_count=scanned_count,
        fetched_count=fetched_count,
        data_available=len(sorted_rows) > 0,
        message=message,
        partial=partial,
        provider_degraded=provider_degraded,
    )


async def _scan_one_volume(symbol: str) -> VolumeScanRow | None:
    fp = await fetch_volume_footprint(symbol)
    if not fp.data_available:
        return None
    return VolumeScanRow(
        ticker=symbol,
        stance=fp.stance,
        obv_divergence=fp.obv_divergence,
        ad_divergence=fp.ad_divergence,
        vwap_deviation_pct=fp.vwap_deviation_pct,
        volume_ratio=fp.volume_ratio,
        quiet_accumulation=fp.quiet_accumulation,
    )


def _set_volume_hist_prefetch(hist_map: dict[str, Any]) -> None:
    _volume_hist_prefetch.set(hist_map)


async def scan_volume_universe(
    universe: str = "sp500",
    watchlist_name: str = "default",
    *,
    signals_only: bool = True,
    refresh: bool = False,
) -> VolumeScanResult:
    universe_key, tickers, cache_suffix = resolve_scan_universe(universe, watchlist_name=watchlist_name)
    cache_key = f"volume:{cache_suffix}"
    cached = get_cached("smart_money_volume", cache_key)
    if cached and isinstance(cached, dict) and not refresh:
        return apply_scan_response_filter(
            cached,
            VolumeScanResult,
            _build_volume_result,
            filter_row=_volume_signal_filter(universe_key),
            signals_only=signals_only,
        )

    if not tickers:
        return VolumeScanResult(
            as_of=datetime.now(UTC),
            universe=universe_key,  # type: ignore[arg-type]
            message="No tickers in selected universe.",
        )

    settings = get_settings()

    if universe_key == "watchlist":
        hist_map = await asyncio.to_thread(prefetch_hist_chunk, tickers, period="3y")
        token = _volume_hist_prefetch.set(hist_map)
        try:
            sem = asyncio.Semaphore(settings.smart_money_scan_concurrency)

            async def one(sym: str) -> VolumeScanRow | None:
                async with sem:
                    return await _scan_one_volume(sym)

            scanned = list(await asyncio.gather(*[one(t) for t in tickers]))
        finally:
            _volume_hist_prefetch.reset(token)
        fetched = [r for r in scanned if r is not None]
        provider_degraded = len(tickers) > 0 and len(fetched) == 0
        full_result = _build_volume_result(
            fetched,
            universe_key,
            len(tickers),
            datetime.now(UTC),
            fetched_count=len(fetched),
            signals_only=False,
            provider_degraded=provider_degraded,
        )
        ttl = (
            settings.scan_failure_cache_seconds
            if provider_degraded
            else settings.smart_money_volume_cache_minutes * 60
        )
        set_cached_ttl(
            "smart_money_volume",
            cache_key,
            {
                "as_of": full_result.as_of.isoformat(),
                "scanned_count": len(tickers),
                "partial": False,
                "result": full_result.model_dump(mode="json"),
            },
            ttl,
        )
        if signals_only:
            filt = _volume_signal_filter(universe_key)
            filtered = [r for r in fetched if filt(r)]
            return _build_volume_result(
                filtered,
                universe_key,
                len(tickers),
                full_result.as_of,
                fetched_count=len(fetched),
                signals_only=True,
                provider_degraded=provider_degraded,
            )
        return full_result

    ttl = scan_cache_ttl_seconds(universe_key, default_minutes=settings.smart_money_volume_cache_minutes)
    volume_job = {
        "watchlist": "volume_watchlist",
        "sp100": "volume_sp100",
        "sp500": "volume_sp500",
    }.get(universe_key, "volume_sp500")
    return await scan_universe_chunked(
        tickers,
        universe_key=universe_key,
        cache_prefix="smart_money_volume",
        cache_key=cache_key,
        cache_ttl_seconds=ttl,
        result_type=VolumeScanResult,
        scan_one=_scan_one_volume,
        build_result=_build_volume_result,
        filter_row=_volume_signal_filter(universe_key),
        signals_only=signals_only,
        refresh=refresh,
        job_resource="volume_scan",
        job_name=volume_job,
        prefetch_chunk=lambda chunk: prefetch_hist_chunk(chunk, period="3y"),
        on_chunk_prefetched=_set_volume_hist_prefetch,
    )
