"""Merged from: test_fundamental_assessment.py, test_fundamental_benchmark.py, test_fundamental_warnings.py"""

# --- from test_fundamental_assessment.py ---

from trade_sentinel_api.models.schemas import (
    FundamentalBenchmark,
    FundamentalsSnapshot,
    NewsItem,
    QuarterlyMetric,
)
from trade_sentinel_api.services.fundamental_assessment import build_fundamental_assessment
from trade_sentinel_api.services.news_sentiment import build_news_digest, enrich_news_item


def test_enrich_news_bullish():
    item = enrich_news_item(NewsItem(title="Company beats earnings expectations"))
    assert item.sentiment_label == "bullish"
    assert "earnings" in item.themes


def test_build_news_digest_mixed():
    items = [
        enrich_news_item(NewsItem(title="Stock surges on upgrade")),
        enrich_news_item(NewsItem(title="Company misses revenue, cuts guidance")),
    ]
    digest = build_news_digest(items)
    assert digest.data_available
    assert digest.overall_sentiment == "mixed"
    assert digest.bullish_count >= 1
    assert digest.bearish_count >= 1


def test_fundamental_assessment_available():
    fund = FundamentalsSnapshot(
        data_available=True,
        revenue_growth=0.2,
        roe=0.18,
        profit_margin=0.15,
        operating_margin=0.12,
        total_cash=100,
        total_debt=50,
        benchmark=FundamentalBenchmark(
            eps_trend="up",
            debt_trend="improving",
            benchmark_bullets=["Revenue CAGR above 3Y avg"],
            data_available=True,
        ),
        quarterly_trends=[QuarterlyMetric(period="2024-Q4", revenue_yoy_pct=15)],
    )
    fa = build_fundamental_assessment(fund)
    assert fa.data_available
    assert fa.overall_label in ("favorable", "neutral", "caution")
    assert fa.summary

# --- from test_fundamental_benchmark.py ---

"""Edge cases for historical self-benchmark calculations."""

import pandas as pd

from trade_sentinel_api.services.fundamentals import _build_benchmark, _pe_vs_history


def test_pe_vs_history_skips_negative_eps():
    q_inc = pd.DataFrame(
        {
            pd.Timestamp("2025-03-31"): [-0.5],
            pd.Timestamp("2024-12-31"): [1.0],
        },
        index=["Diluted EPS"],
    )
    hist = pd.DataFrame({"Close": [100.0, 90.0]}, index=q_inc.columns)
    result, current_pe, median_pe, pe_pctiles, pe_rank = _pe_vs_history(
        hist, q_inc, 100.0, 20.0, 18.0
    )
    assert result is None or isinstance(result, float)
    assert current_pe == 20.0
    assert median_pe is None or isinstance(median_pe, float)


def test_benchmark_data_available_false_when_few_quarters():
    bench = _build_benchmark(
        [QuarterlyMetric(period="2025-Q1", revenue=100)],
        None,
        None,
        None,
        None,
        50.0,
        15.0,
        14.0,
    )
    assert bench.data_available is False


def test_benchmark_bullets_populated():
    quarters = [
        QuarterlyMetric(period=f"2024-Q{i}", revenue=100 + i * 10, eps=1.0, revenue_yoy_pct=10.0 + i)
        for i in range(1, 5)
    ]
    q_inc = pd.DataFrame(
        {
            pd.Timestamp("2025-03-31"): [140.0, 42.0, 1.4],
            pd.Timestamp("2024-12-31"): [130.0, 39.0, 1.3],
            pd.Timestamp("2024-09-30"): [120.0, 36.0, 1.2],
            pd.Timestamp("2024-06-30"): [110.0, 33.0, 1.1],
        },
        index=["Total Revenue", "Operating Income", "Diluted EPS"],
    )
    annual = pd.DataFrame(
        {
            pd.Timestamp("2024-12-31"): [500.0],
            pd.Timestamp("2023-12-31"): [400.0],
            pd.Timestamp("2022-12-31"): [300.0],
            pd.Timestamp("2021-12-31"): [200.0],
        },
        index=["Total Revenue"],
    )
    bench = _build_benchmark(quarters, q_inc, None, annual, None, 100.0, 22.0, 20.0)
    assert bench.revenue_cagr_3y is not None
    assert bench.data_available is True


def test_benchmark_pe_percentiles_when_history_available():
    quarters = [
        QuarterlyMetric(period=f"2024-Q{i}", revenue=100 + i * 10, eps=1.0, revenue_yoy_pct=10.0)
        for i in range(1, 5)
    ]
    cols = [pd.Timestamp(f"2024-{m:02d}-28") for m in (3, 6, 9, 12)]
    q_inc = pd.DataFrame(
        {c: [110.0, 33.0, 1.1] for c in cols},
        index=["Total Revenue", "Operating Income", "Diluted EPS"],
    )
    hist = pd.DataFrame({"Close": [100.0] * len(cols)}, index=cols)
    bench = _build_benchmark(quarters, q_inc, None, None, hist, 100.0, 22.0, 20.0)
    if bench.pe_percentiles is not None:
        assert bench.pe_percentiles.p50 is not None
        assert bench.pe_current_percentile is not None

# --- from test_fundamental_warnings.py ---

"""Fundamental warnings builder tests."""

from trade_sentinel_api.models.schemas import EarningsSnapshot
from trade_sentinel_api.services.warnings import build_fundamental_warnings


def test_high_valuation_warning():
    fund = FundamentalsSnapshot(pe_forward=55.0, data_available=True)
    warnings = build_fundamental_warnings(fund)
    assert any(w.code == "HIGH_VALUATION" for w in warnings)


def test_earnings_soon_warning():
    fund = FundamentalsSnapshot(data_available=True)
    earnings = EarningsSnapshot(days_until=3, data_available=True)
    warnings = build_fundamental_warnings(fund, earnings)
    assert any(w.code == "EARNINGS_DATE_SOON" for w in warnings)


def test_benchmark_flag_warnings():
    fund = FundamentalsSnapshot(
        data_available=True,
        fundamental_flags=["VALUATION_ABOVE_HISTORY", "MARGIN_CONTRACTING"],
    )
    warnings = build_fundamental_warnings(fund)
    codes = {w.code for w in warnings}
    assert "VALUATION_ABOVE_HISTORY" in codes
    assert "MARGIN_CONTRACTING" in codes
