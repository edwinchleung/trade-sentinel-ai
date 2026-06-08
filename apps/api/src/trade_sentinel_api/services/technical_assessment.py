"""Deterministic technical assessment from OHLCV history."""

from __future__ import annotations

import pandas as pd

from trade_sentinel_api.models.schemas import (
    MacdDivergence,
    MacdSnapshot,
    TechnicalAssessment,
    TrendLabel,
)
from trade_sentinel_api.services.technicals import (
    compute_atr,
    compute_macd,
    compute_macd_series,
    compute_rsi,
    compute_sma,
    detect_macd_divergence,
)

_MIN_BARS = 50
_SMA50_PERIOD = 50


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _pct_vs(price: float, level: float | None) -> float | None:
    if level is None or level == 0:
        return None
    return round((price - level) / level * 100, 2)


def _range_position(price: float, low: float | None, high: float | None) -> float | None:
    if low is None or high is None or high <= low:
        return None
    return round((price - low) / (high - low) * 100, 1)


def _classify_trend(
    *,
    price: float,
    sma_20: float | None,
    sma_50: float | None,
    macd_hist: float | None,
) -> TrendLabel:
    bullish = 0
    bearish = 0
    if sma_20 is not None:
        if price > sma_20:
            bullish += 1
        elif price < sma_20:
            bearish += 1
    if sma_50 is not None:
        if price > sma_50:
            bullish += 1
        elif price < sma_50:
            bearish += 1
    if sma_20 is not None and sma_50 is not None:
        if sma_20 > sma_50:
            bullish += 1
        elif sma_20 < sma_50:
            bearish += 1
    if macd_hist is not None:
        if macd_hist > 0:
            bullish += 1
        elif macd_hist < 0:
            bearish += 1

    if bullish >= 3 and bearish == 0:
        return "bullish"
    if bearish >= 3 and bullish == 0:
        return "bearish"
    if bullish > bearish and bullish >= 2:
        return "bullish"
    if bearish > bullish and bearish >= 2:
        return "bearish"
    if bullish > 0 and bearish > 0:
        return "mixed"
    return "neutral"


def _classify_short_term(
    *,
    price: float,
    sma_20: float | None,
    rsi: float | None,
    close: pd.Series,
) -> TrendLabel:
    bullish = bearish = 0
    if sma_20 is not None:
        if price > sma_20:
            bullish += 1
        elif price < sma_20:
            bearish += 1
    if rsi is not None:
        if rsi > 55:
            bullish += 1
        elif rsi < 45:
            bearish += 1
    if len(close) >= 6:
        ret5 = (price - float(close.iloc[-6])) / float(close.iloc[-6])
        if ret5 > 0.01:
            bullish += 1
        elif ret5 < -0.01:
            bearish += 1
    return _score_horizon(bullish, bearish)


def _classify_mid_term(
    *,
    price: float,
    sma_20: float | None,
    sma_50: float | None,
    macd_hist: float | None,
) -> TrendLabel:
    bullish = bearish = 0
    if sma_50 is not None:
        if price > sma_50:
            bullish += 1
        elif price < sma_50:
            bearish += 1
    if sma_20 is not None and sma_50 is not None:
        if sma_20 > sma_50:
            bullish += 1
        elif sma_20 < sma_50:
            bearish += 1
    if macd_hist is not None:
        if macd_hist > 0:
            bullish += 1
        elif macd_hist < 0:
            bearish += 1
    return _score_horizon(bullish, bearish)


def _classify_long_term(
    *,
    price: float,
    sma_200: float | None,
    range_pos: float | None,
) -> TrendLabel:
    if sma_200 is None and range_pos is None:
        return "neutral"
    bullish = bearish = 0
    if sma_200 is not None:
        if price > sma_200:
            bullish += 1
        elif price < sma_200:
            bearish += 1
    if range_pos is not None:
        if range_pos > 60:
            bullish += 1
        elif range_pos < 40:
            bearish += 1
    return _score_horizon(bullish, bearish)


def _score_horizon(bullish: int, bearish: int) -> TrendLabel:
    if bullish >= 2 and bearish == 0:
        return "bullish"
    if bearish >= 2 and bullish == 0:
        return "bearish"
    if bullish > bearish and bullish >= 2:
        return "bullish"
    if bearish > bullish and bearish >= 2:
        return "bearish"
    if bullish > 0 and bearish > 0:
        return "mixed"
    return "neutral"


def _build_horizon_summary(
    short: TrendLabel,
    mid: TrendLabel,
    long: TrendLabel | None,
) -> str:
    parts = [f"Short: {short}", f"Mid: {mid}"]
    if long:
        parts.append(f"Long: {long}")
    return "; ".join(parts)


def _build_trend_summary(
    trend: TrendLabel,
    *,
    price: float,
    sma_20: float | None,
    sma_50: float | None,
    macd_hist: float | None,
) -> str:
    parts: list[str] = []
    if sma_20 is not None and sma_50 is not None:
        if price > sma_20 and price > sma_50:
            parts.append("Price above SMA20 and SMA50")
        elif price < sma_20 and price < sma_50:
            parts.append("Price below SMA20 and SMA50")
        else:
            parts.append("Price mixed vs SMA20/SMA50")
    elif sma_20 is not None:
        parts.append(f"Price {'above' if price > sma_20 else 'below'} SMA20")
    if macd_hist is not None:
        parts.append(f"MACD histogram {'positive' if macd_hist > 0 else 'negative' if macd_hist < 0 else 'flat'}")
    if not parts:
        return f"Trend classified as {trend}."
    return "; ".join(parts) + f" ({trend})."


def _build_signals(
    *,
    rsi: float | None,
    price: float,
    sma_50: float | None,
    range_pos: float | None,
    divergence: MacdDivergence | None,
    macd: MacdSnapshot | None,
) -> list[str]:
    signals: list[str] = []
    if rsi is not None:
        if rsi > 70:
            signals.append("RSI_OVERBOUGHT")
        elif rsi < 30:
            signals.append("RSI_OVERSOLD")
    if sma_50 is not None:
        pct = _pct_vs(price, sma_50)
        if pct is not None:
            if pct < -2:
                signals.append("BELOW_SMA50")
            elif pct > 2:
                signals.append("ABOVE_SMA50")
    if range_pos is not None:
        if range_pos > 90:
            signals.append("NEAR_52W_HIGH")
        elif range_pos < 10:
            signals.append("NEAR_52W_LOW")
    if divergence == "bullish":
        signals.append("MACD_BULLISH_DIVERGENCE")
    elif divergence == "bearish":
        signals.append("MACD_BEARISH_DIVERGENCE")
    if macd and macd.macd is not None and macd.signal is not None:
        hist = macd.histogram if macd.histogram is not None else (macd.macd - macd.signal)
        if macd.macd < macd.signal and hist < 0:
            signals.append("MACD_BEARISH")
        elif macd.macd > macd.signal and hist > 0:
            signals.append("MACD_BULLISH")
    return signals


def build_technical_assessment(
    hist: pd.DataFrame,
    *,
    price: float,
    week52: dict | None = None,
) -> TechnicalAssessment:
    empty = TechnicalAssessment(
        current_price=price,
        data_available=False,
        message="Insufficient price history for technical assessment (need ≥50 daily bars).",
        data_gaps=["technical_history_short"],
    )
    if hist is None or hist.empty or len(hist) < _MIN_BARS:
        return empty

    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]

    rsi = compute_rsi(close)
    macd_raw = compute_macd(close)
    macd = MacdSnapshot(**macd_raw)
    macd_line = compute_macd_series(close)
    div_raw = detect_macd_divergence(close, macd_line)
    divergence: MacdDivergence | None = div_raw if div_raw in ("bullish", "bearish", "none") else None

    sma_20 = compute_sma(close, 20)
    sma_50 = compute_sma(close, _SMA50_PERIOD)
    sma_200 = compute_sma(close, 200) if len(close) >= 200 else None

    atr = compute_atr(high, low, close)
    atr_pct = round(atr / price * 100, 2) if atr is not None and price > 0 else None

    w52 = week52 or {}
    range_low = _safe_float(w52.get("low"))
    range_high = _safe_float(w52.get("high"))
    if range_low is None or range_high is None:
        range_low = float(close.tail(252).min()) if len(close) >= 20 else None
        range_high = float(close.tail(252).max()) if len(close) >= 20 else None

    range_pos = _range_position(price, range_low, range_high)

    support = float(close.tail(20).min()) if len(close) >= 20 else None
    resistance = float(close.tail(20).max()) if len(close) >= 20 else None

    hist_val = macd.histogram
    trend = _classify_trend(
        price=price,
        sma_20=sma_20,
        sma_50=sma_50,
        macd_hist=hist_val,
    )
    short_term = _classify_short_term(price=price, sma_20=sma_20, rsi=rsi, close=close)
    mid_term = _classify_mid_term(
        price=price, sma_20=sma_20, sma_50=sma_50, macd_hist=hist_val
    )
    long_term: TrendLabel | None = None
    if sma_200 is not None or range_pos is not None:
        long_term = _classify_long_term(price=price, sma_200=sma_200, range_pos=range_pos)
    horizon_summary = _build_horizon_summary(short_term, mid_term, long_term)
    trend_summary = _build_trend_summary(
        trend,
        price=price,
        sma_20=sma_20,
        sma_50=sma_50,
        macd_hist=hist_val,
    )

    signals = _build_signals(
        rsi=rsi,
        price=price,
        sma_50=sma_50,
        range_pos=range_pos,
        divergence=divergence,
        macd=macd,
    )

    gaps: list[str] = []
    if sma_200 is None:
        gaps.append("sma200_unavailable")
    if range_low is None or range_high is None:
        gaps.append("range_52w_estimated")

    return TechnicalAssessment(
        current_price=round(price, 2),
        trend_label=trend,
        trend_summary=trend_summary,
        short_term_trend=short_term,
        mid_term_trend=mid_term,
        long_term_trend=long_term,
        horizon_summary=horizon_summary,
        rsi_14=round(rsi, 2) if rsi is not None else None,
        macd=macd,
        atr_14=round(atr, 4) if atr is not None else None,
        atr_pct=atr_pct,
        sma_20=round(sma_20, 2) if sma_20 is not None else None,
        sma_50=round(sma_50, 2) if sma_50 is not None else None,
        sma_200=round(sma_200, 2) if sma_200 is not None else None,
        price_vs_sma_20_pct=_pct_vs(price, sma_20),
        price_vs_sma_50_pct=_pct_vs(price, sma_50),
        range_52w_low=round(range_low, 2) if range_low is not None else None,
        range_52w_high=round(range_high, 2) if range_high is not None else None,
        range_position_pct=range_pos,
        support_level=round(support, 2) if support is not None else None,
        resistance_level=round(resistance, 2) if resistance is not None else None,
        macd_divergence=divergence,
        signals=signals,
        data_gaps=gaps,
        data_available=True,
        message=None,
    )
