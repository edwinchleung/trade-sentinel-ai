"""Unit tests for fundamentals service and historical benchmark."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from trade_sentinel_api.models.schemas import QuarterlyMetric
from trade_sentinel_api.services.fundamentals import (
    _analyst_counts_from_yfinance,
    _build_benchmark,
    _build_quarterly_trends,
    _eps_trend,
    _margin_vs_history,
    _revenue_cagr_3y,
    _revenue_growth_acceleration,
    _valuation_label,
    fetch_fundamentals_snapshot,
)


def test_valuation_label():
    assert _valuation_label(50) == "premium"
    assert _valuation_label(10) == "discount"
    assert _valuation_label(25) == "moderate"
    assert _valuation_label(None) is None


def test_build_quarterly_trends_from_dataframe():
    q_inc = pd.DataFrame(
        {
            pd.Timestamp("2025-03-31"): [100.0, 1.0],
            pd.Timestamp("2024-12-31"): [90.0, 0.9],
            pd.Timestamp("2024-09-30"): [85.0, 0.85],
            pd.Timestamp("2024-06-30"): [80.0, 0.8],
        },
        index=["Total Revenue", "Diluted EPS"],
    )
    trends = _build_quarterly_trends(q_inc, limit=4)
    assert len(trends) == 4
    assert trends[0].revenue == 100.0
    assert trends[0].eps == 1.0
    assert trends[0].revenue_qoq_pct is not None


def test_build_quarterly_trends_yoy_with_five_quarters():
    q_inc = pd.DataFrame(
        {
            pd.Timestamp("2025-03-31"): [150.0, 1.5],
            pd.Timestamp("2024-12-31"): [140.0, 1.4],
            pd.Timestamp("2024-09-30"): [130.0, 1.3],
            pd.Timestamp("2024-06-30"): [120.0, 1.2],
            pd.Timestamp("2023-06-30"): [100.0, 1.0],
        },
        index=["Total Revenue", "Diluted EPS"],
    )
    trends = _build_quarterly_trends(q_inc, limit=4)
    assert trends[0].revenue_yoy_pct is not None
    assert trends[0].revenue_yoy_pct == 50.0


def test_analyst_counts_from_yfinance_recommendations():
    stock = MagicMock()
    stock.recommendations = pd.DataFrame(
        [{"strongBuy": 10, "buy": 5, "hold": 3, "sell": 2, "strongSell": 1}],
        index=pd.to_datetime(["2025-01-01"]),
    )
    buy, sell = _analyst_counts_from_yfinance(stock)
    assert buy == 15
    assert sell == 3


def test_analyst_counts_from_yfinance_empty():
    stock = MagicMock()
    stock.recommendations = pd.DataFrame()
    assert _analyst_counts_from_yfinance(stock) == (None, None)


def test_revenue_cagr_3y():
    annual = pd.DataFrame(
        {
            pd.Timestamp("2024-12-31"): [121.0],
            pd.Timestamp("2023-12-31"): [110.0],
            pd.Timestamp("2022-12-31"): [100.0],
            pd.Timestamp("2021-12-31"): [90.0],
        },
        index=["Total Revenue"],
    )
    cagr = _revenue_cagr_3y(annual, None)
    assert cagr is not None
    assert cagr > 0


def test_eps_trend_up():
    quarters = [
        QuarterlyMetric(period="2025-Q1", eps=0.5),
        QuarterlyMetric(period="2024-Q4", eps=0.4),
        QuarterlyMetric(period="2024-Q3", eps=0.35),
        QuarterlyMetric(period="2024-Q2", eps=0.3),
    ]
    assert _eps_trend(quarters) == "up"


def test_margin_vs_history():
    q_inc = pd.DataFrame(
        {pd.Timestamp(f"2024-{m}-30"): [100.0, 30.0 + i] for i, m in enumerate([3, 6, 9, 12], 1)},
        index=["Total Revenue", "Operating Income"],
    )
    delta = _margin_vs_history(q_inc)
    assert delta is not None


def test_build_benchmark_insufficient_history():
    bench = _build_benchmark([], None, None, None, None, 100.0, 20.0, 18.0)
    assert bench.data_available is False


def test_build_benchmark_with_quarters():
    hist = [
        QuarterlyMetric(period="2025-Q1", revenue=120, eps=1.2, revenue_yoy_pct=20.0),
        QuarterlyMetric(period="2024-Q4", revenue=110, eps=1.0, revenue_yoy_pct=15.0),
        QuarterlyMetric(period="2024-Q3", revenue=100, eps=0.9, revenue_yoy_pct=12.0),
        QuarterlyMetric(period="2024-Q2", revenue=95, eps=0.85, revenue_yoy_pct=10.0),
    ]
    q_inc = pd.DataFrame(
        {pd.Timestamp("2025-03-31"): [120.0, 36.0, 1.2]},
        index=["Total Revenue", "Operating Income", "Diluted EPS"],
    )
    bench = _build_benchmark(hist, q_inc, None, None, None, 150.0, 25.0, 22.0)
    assert bench.data_available is True
    assert len(bench.benchmark_bullets) >= 1


def test_revenue_growth_acceleration_fallback_from_q_inc():
    q_inc = pd.DataFrame(
        {
            pd.Timestamp("2025-03-31"): [150.0],
            pd.Timestamp("2024-12-31"): [140.0],
            pd.Timestamp("2024-09-30"): [130.0],
            pd.Timestamp("2024-06-30"): [120.0],
            pd.Timestamp("2024-03-31"): [110.0],
            pd.Timestamp("2023-03-31"): [100.0],
        },
        index=["Total Revenue"],
    )
    hist = [
        QuarterlyMetric(period="2025-Q1", revenue=150),
        QuarterlyMetric(period="2024-Q4", revenue=140),
        QuarterlyMetric(period="2024-Q3", revenue=130),
        QuarterlyMetric(period="2024-Q2", revenue=120),
    ]
    accel = _revenue_growth_acceleration(hist, q_inc)
    assert accel is not None


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.fundamentals._fetch_yfinance_fundamentals_sync")
@patch("trade_sentinel_api.services.fundamentals._fetch_finnhub_enrichment", return_value=None)
async def test_fetch_fundamentals_snapshot(mock_finnhub, mock_yf):
    from trade_sentinel_api.models.schemas import FundamentalsSnapshot

    mock_yf.return_value = FundamentalsSnapshot(
        sector="Technology",
        pe_forward=30.0,
        data_available=True,
    )
    snap = await fetch_fundamentals_snapshot("AAPL", 150.0)
    assert snap.data_available is True
    assert snap.sector == "Technology"
