import numpy as np
import pandas as pd


def compute_rsi(close: pd.Series, period: int = 14) -> float | None:
    """Wilder-smoothed RSI (industry standard)."""
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else None


def compute_sma(close: pd.Series, period: int) -> float | None:
    if len(close) < period:
        return None
    val = close.rolling(period).mean().iloc[-1]
    return float(val) if pd.notna(val) else None


def compute_macd(close: pd.Series) -> dict[str, float | None]:
    if len(close) < 26:
        return {"macd": None, "signal": None, "histogram": None}
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    return {
        "macd": float(macd_line.iloc[-1]) if pd.notna(macd_line.iloc[-1]) else None,
        "signal": float(signal.iloc[-1]) if pd.notna(signal.iloc[-1]) else None,
        "histogram": float(hist.iloc[-1]) if pd.notna(hist.iloc[-1]) else None,
    }


def compute_macd_series(close: pd.Series) -> pd.Series:
    """Full MACD line series for divergence detection."""
    if len(close) < 26:
        return pd.Series(dtype=float)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    return ema12 - ema26


def detect_macd_divergence(
    close: pd.Series,
    macd_line: pd.Series | None = None,
    *,
    lookback: int = 20,
) -> str | None:
    """
    Detect bullish/bearish MACD divergence over lookback window.
    Bullish: price makes lower low, MACD makes higher low.
    Bearish: price makes higher high, MACD makes lower high.
    """
    if len(close) < lookback + 5:
        return None
    if macd_line is None or macd_line.empty:
        macd_line = compute_macd_series(close)
    if macd_line.empty or len(macd_line) < lookback:
        return None

    window_close = close.iloc[-lookback:]
    window_macd = macd_line.iloc[-lookback:]
    mid = lookback // 2

    first_close = window_close.iloc[:mid]
    second_close = window_close.iloc[mid:]
    first_macd = window_macd.iloc[:mid]
    second_macd = window_macd.iloc[mid:]

    price_low1, price_low2 = float(first_close.min()), float(second_close.min())
    price_high1, price_high2 = float(first_close.max()), float(second_close.max())
    macd_low1, macd_low2 = float(first_macd.min()), float(second_macd.min())
    macd_high1, macd_high2 = float(first_macd.max()), float(second_macd.max())

    if price_low2 < price_low1 and macd_low2 > macd_low1:
        return "bullish"
    if price_high2 > price_high1 and macd_high2 < macd_high1:
        return "bearish"
    return "none"


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean().iloc[-1]
    return float(atr) if pd.notna(atr) else None
