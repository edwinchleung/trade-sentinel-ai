"""Merged from: test_market_data.py, test_technicals.py, test_technical_assessment.py, test_sector_context.py"""

# --- from test_market_data.py ---

import pandas as pd

from trade_sentinel_api.services.market_data import _resolve_live_quote


def _hist(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=len(closes), freq="B")
    return pd.DataFrame({"Close": closes, "Volume": [1000] * len(closes)}, index=idx)


def test_resolve_pre_market_price():
    hist = _hist([100.0, 102.0])
    info = {
        "marketState": "PRE",
        "preMarketPrice": 104.0,
        "previousClose": 102.0,
    }
    q = _resolve_live_quote(info, hist)
    assert q["price"] == 104.0
    assert q["price_source"] == "pre_market"
    assert q["is_extended_hours"] is True
    assert q["change_pct"] == round((104 - 102) / 102 * 100, 2)


def test_resolve_post_market_price():
    hist = _hist([100.0, 105.0])
    info = {
        "marketState": "POST",
        "postMarketPrice": 103.0,
        "previousClose": 105.0,
        "regularMarketPrice": 105.0,
    }
    q = _resolve_live_quote(info, hist)
    assert q["price"] == 103.0
    assert q["price_source"] == "post_market"
    assert q["change_pct"] == round((103 - 105) / 105 * 100, 2)


def test_resolve_regular_session():
    hist = _hist([100.0, 102.0])
    info = {
        "marketState": "REGULAR",
        "regularMarketPrice": 106.0,
        "previousClose": 102.0,
    }
    q = _resolve_live_quote(info, hist)
    assert q["price"] == 106.0
    assert q["price_source"] == "regular_market"
    assert q["is_extended_hours"] is False

# --- from test_technicals.py ---

import numpy as np
import pandas as pd

from trade_sentinel_api.services.technicals import (
    compute_macd_series,
    compute_rsi,
    compute_sma,
    detect_macd_divergence,
)


def _sample_close(n: int = 60, start: float = 100.0) -> pd.Series:
    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.02, n)
    prices = start * np.cumprod(1 + returns)
    return pd.Series(prices)


def test_compute_sma_returns_latest_average():
    close = _sample_close(30)
    sma = compute_sma(close, 20)
    expected = float(close.tail(20).mean())
    assert sma is not None
    assert abs(sma - expected) < 1e-6


def test_compute_rsi_wilder_in_range():
    close = _sample_close(80)
    rsi = compute_rsi(close)
    assert rsi is not None
    assert 0 <= rsi <= 100


def test_compute_rsi_insufficient_data():
    close = _sample_close(10)
    assert compute_rsi(close) is None


def test_detect_macd_divergence_bullish_pattern():
    n = 40
    # Price makes lower low in second half; MACD makes higher low
    close_vals = np.concatenate([
        np.linspace(110, 100, n // 2),
        np.linspace(98, 95, n // 2),
    ])
    close = pd.Series(close_vals)
    macd_line = pd.Series(np.concatenate([
        np.linspace(-2, -4, n // 2),
        np.linspace(-3, -2, n // 2),
    ]))
    result = detect_macd_divergence(close, macd_line, lookback=20)
    assert result == "bullish"


def test_detect_macd_divergence_bearish_pattern():
    n = 40
    close_vals = np.concatenate([
        np.linspace(100, 105, n // 2),
        np.linspace(106, 112, n // 2),
    ])
    close = pd.Series(close_vals)
    macd_line = pd.Series(np.concatenate([
        np.linspace(1, 3, n // 2),
        np.linspace(2, 1, n // 2),
    ]))
    result = detect_macd_divergence(close, macd_line, lookback=20)
    assert result == "bearish"


def test_compute_macd_series_length():
    close = _sample_close(30)
    series = compute_macd_series(close)
    assert len(series) == 30

# --- from test_technical_assessment.py ---

import pandas as pd

from trade_sentinel_api.services.technical_assessment import build_technical_assessment


def _make_hist(n: int = 60, base: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    returns = rng.normal(0.002, 0.015, n)
    close = base * np.cumprod(1 + returns)
    high = close * 1.01
    low = close * 0.99
    volume = rng.integers(1_000_000, 5_000_000, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Close": close, "High": high, "Low": low, "Volume": volume},
        index=idx,
    )


def test_build_technical_assessment_data_available():
    hist = _make_hist(60, 150.0)
    price = float(hist["Close"].iloc[-1])
    ta = build_technical_assessment(
        hist,
        price=price,
        week52={"low": 120.0, "high": 180.0},
    )
    assert ta.data_available is True
    assert ta.trend_label in ("bullish", "bearish", "neutral", "mixed")
    assert ta.rsi_14 is not None
    assert ta.sma_20 is not None
    assert ta.sma_50 is not None
    assert ta.support_level is not None
    assert ta.resistance_level is not None
    assert ta.range_position_pct is not None
    assert ta.short_term_trend is not None
    assert ta.mid_term_trend is not None
    assert ta.horizon_summary is not None


def test_build_technical_assessment_insufficient_history():
    hist = _make_hist(30)
    ta = build_technical_assessment(hist, price=100.0, week52={})
    assert ta.data_available is False
    assert "technical_history_short" in ta.data_gaps


def test_bullish_trend_when_price_above_smas():
    n = 60
    close = np.linspace(90, 120, n)
    hist = pd.DataFrame(
        {
            "Close": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Volume": np.full(n, 2_000_000),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="B"),
    )
    price = float(close[-1])
    ta = build_technical_assessment(hist, price=price, week52={"low": 80.0, "high": 125.0})
    assert ta.data_available
    assert ta.trend_label in ("bullish", "mixed", "neutral")
    assert ta.price_vs_sma_20_pct is not None
    assert ta.price_vs_sma_20_pct > 0

# --- from test_sector_context.py ---

"""Sector peer percentile from cached screener rows."""

from trade_sentinel_api.models.schemas import DigestTickerRow, FundamentalsSnapshot
from trade_sentinel_api.services.sector_context import (
    _percentile_rank,
    _SectorBucket,
    build_sector_context,
)


def test_percentile_rank_requires_min_peers():
    assert _percentile_rank(25.0, [20.0, 22.0, 24.0, 26.0, 28.0, 30.0, 32.0, 34.0]) is not None
    assert _percentile_rank(25.0, [20.0, 30.0]) is None


def test_build_sector_context_with_stats():
    fundamentals = FundamentalsSnapshot(
        sector="Technology",
        industry="Software",
        pe_forward=30.0,
        data_available=True,
    )
    stats = {
        "Technology": _SectorBucket(
            pe_forwards=[20.0, 22.0, 25.0, 28.0, 30.0, 32.0, 35.0, 40.0, 45.0],
            mos_pcts=[-10.0, 0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0],
        )
    }
    ctx = build_sector_context(
        "TEST",
        fundamentals,
        None,
        universe="sp500",
        stats=stats,
    )
    assert ctx.data_available
    assert ctx.pe_forward_sector_percentile is not None
    assert ctx.peer_count == 9
    assert ctx.sector == "Technology"


def test_enrich_digest_row_fields_via_build():
    from trade_sentinel_api.services.sector_context import enrich_digest_row_sector_fields

    row = DigestTickerRow(ticker="AAPL", sector="Technology", pe_forward=30.0)
    stats = {
        "Technology": _SectorBucket(pe_forwards=[20.0] * 10, mos_pcts=[]),
    }
    enriched = enrich_digest_row_sector_fields(row, stats=stats)
    assert enriched.pe_sector_percentile is not None
