"""Merged from: test_valuation.py, test_valuation_improvements.py, test_valuation_archetypes.py"""

# --- from test_valuation.py ---

"""Unit tests for valuation service."""

from trade_sentinel_api.models.schemas import (
    FundamentalBenchmark,
    FundamentalsSnapshot,
    QuarterlyMetric,
)
from trade_sentinel_api.services.valuation import (
    _analyst_method,
    _fcf_yield_method,
    _graham_method,
    _headline_composite_band,
    _historical_pe_method,
    _mos_label,
    build_valuation_assessment,
    derive_dcf_assumptions,
)


def _sample_fundamentals(**kwargs) -> FundamentalsSnapshot:
    defaults = dict(
        data_available=True,
        market_cap=1_000_000_000_000,
        free_cash_flow=50_000_000_000,
        pe_forward=25.0,
        pe_trailing=24.0,
        target_price=220.0,
        target_upside_pct=10.0,
        quarterly_trends=[
            QuarterlyMetric(period="2024-Q4", eps=6.0),
            QuarterlyMetric(period="2024-Q3", eps=5.8),
            QuarterlyMetric(period="2024-Q2", eps=5.5),
            QuarterlyMetric(period="2024-Q1", eps=5.2),
        ],
        benchmark=FundamentalBenchmark(
            pe_vs_3y_median_pct=20.0,
            median_pe_3y=30.0,
            historical_pe_reliable=True,
            data_available=True,
        ),
    )
    defaults.update(kwargs)
    return FundamentalsSnapshot(**defaults)


def test_mos_label_premium_vs_fair_mid():
    assert _mos_label(-15) == "undervalued"
    assert _mos_label(15) == "overvalued"
    assert _mos_label(5) == "fair"


def test_analyst_method():
    m = _analyst_method(_sample_fundamentals())
    assert m.data_available
    assert m.fair_value == 220.0
    assert m.reliable_for_composite


def test_graham_method():
    m = _graham_method(_sample_fundamentals(), 200.0)
    assert m.data_available
    assert m.fair_value is not None


def test_historical_pe_reliable():
    m = _historical_pe_method(_sample_fundamentals(), 200.0)
    assert m.data_available
    assert m.reliable_for_composite


def test_historical_pe_unreliable_excluded_from_composite():
    fund = _sample_fundamentals(
        benchmark=FundamentalBenchmark(
            pe_vs_3y_median_pct=80.0,
            median_pe_3y=143.0,
            historical_pe_reliable=False,
            data_available=True,
        ),
        pe_forward=25.0,
        target_price=296.81,
    )
    m = _historical_pe_method(fund, 222.82)
    assert m.data_available
    assert m.fair_value is not None
    assert m.reliable_for_composite is False
    assert "excluded" in (m.detail or "").lower()


def test_fcf_yield_diagnostic_only():
    m = _fcf_yield_method(_sample_fundamentals(), 222.82)
    assert m.data_available
    assert m.reliable_for_composite is False


def test_headline_composite_band_trimmed_iqr():
    low, mid, high = _headline_composite_band([100.0, 120.0, 140.0, 900.0])
    assert mid is not None
    assert high is not None and high < 900.0
    assert low is not None


def test_build_valuation_assessment():
    v = build_valuation_assessment(_sample_fundamentals(), 200.0, include_dcf=False)
    assert v.data_available
    assert v.fair_value_mid is not None
    assert v.mos_pct is not None
    assert v.confidence in ("high", "medium", "low")
    assert len(v.methods) >= 4
    fcf = next(m for m in v.methods if m.method == "fcf_yield")
    assert fcf.reliable_for_composite is False


def test_growth_stock_headline_not_dominated_by_historical_pe():
    """NVDA-like: distorted 3Y median P/E excluded; headline band stays in analyst/DCF cluster."""
    fund = _sample_fundamentals(
        benchmark=FundamentalBenchmark(
            pe_vs_3y_median_pct=120.0,
            median_pe_3y=143.0,
            historical_pe_reliable=False,
            data_available=True,
        ),
        pe_forward=25.0,
        target_price=296.81,
        free_cash_flow=10_000_000_000,
        market_cap=2_000_000_000_000,
        revenue_growth=0.20,
    )
    v = build_valuation_assessment(fund, 222.82, include_dcf=True)
    assert v.data_available
    assert v.fair_value_mid is not None
    assert v.fair_value_high is not None
    assert v.fair_value_high < 400
    hist = next(m for m in v.methods if m.method == "historical_pe")
    assert hist.fair_value is not None and hist.fair_value > 500
    assert hist.reliable_for_composite is False
    assert v.confidence in ("medium", "low")


def test_build_valuation_no_data():
    v = build_valuation_assessment(None, 100.0)
    assert not v.data_available


def test_derive_dcf_assumptions_from_fundamentals():
    params = derive_dcf_assumptions(
        _sample_fundamentals(
            revenue_growth=0.12,
            benchmark=FundamentalBenchmark(
                revenue_cagr_3y=8.0,
                pe_vs_3y_median_pct=10,
                median_pe_3y=28.0,
                historical_pe_reliable=True,
                data_available=True,
            ),
        )
    )
    assert params["derived_from"] == "fundamentals_and_tnx"
    assert 0.08 <= params["discount_rate"] <= 0.14
    assert 0.015 <= params["terminal_growth"] <= 0.03
    assert 0.06 <= params["growth_cap"] <= 0.20


def test_fund_skips_equity_dcf():
    from trade_sentinel_api.models.schemas import FundValuationSnapshot

    f = _sample_fundamentals(
        quote_type="ETF",
        fund_valuation=FundValuationSnapshot(
            quote_type="ETF",
            expense_ratio=0.09,
            data_available=True,
        ),
    )
    v = build_valuation_assessment(f, 450.0)
    assert v.is_fund
    assert v.fund is not None

# --- from test_valuation_improvements.py ---

"""Tests for fair-value assessment improvements."""

from trade_sentinel_api.models.schemas import (
    FundamentalsSnapshot,
)
from trade_sentinel_api.services.fundamentals import _merge_finnhub
from trade_sentinel_api.services.valuation import (
    _analyst_target_stale,
    build_valuation_summary,
)


def _sample(**kwargs) -> FundamentalsSnapshot:
    defaults = dict(
        data_available=True,
        market_cap=1_000_000_000_000,
        free_cash_flow=50_000_000_000,
        pe_forward=25.0,
        shares_outstanding=1_000_000_000,
        quarterly_trends=[
            QuarterlyMetric(period="2024-Q4", eps=6.0),
            QuarterlyMetric(period="2024-Q3", eps=5.8),
            QuarterlyMetric(period="2024-Q2", eps=5.5),
            QuarterlyMetric(period="2024-Q1", eps=5.2),
        ],
        benchmark=FundamentalBenchmark(
            median_pe_3y=30.0,
            historical_pe_reliable=True,
            data_available=True,
        ),
        target_price=220.0,
        target_upside_pct=10.0,
    )
    defaults.update(kwargs)
    return FundamentalsSnapshot(**defaults)


def test_analyst_target_stale_flags():
    assert _analyst_target_stale(85.0) is True
    assert _analyst_target_stale(-55.0) is True
    assert _analyst_target_stale(15.0) is False


def test_analyst_stale_excluded_from_composite():
    m = _analyst_method(_sample(target_upside_pct=90.0))
    assert m.data_available
    assert m.reliable_for_composite is False


def test_merge_finnhub_price_target():
    snap = _sample(target_price=100.0, target_source="yfinance")
    merged = _merge_finnhub(
        snap,
        {
            "price_target": {
                "targetMean": 250.0,
                "targetLow": 200.0,
                "targetHigh": 300.0,
            }
        },
    )
    assert merged.target_price == 250.0
    assert merged.target_source == "finnhub"
    assert merged.target_price_low == 200.0


def test_build_valuation_summary_drivers():
    v = build_valuation_assessment(_sample(), 200.0, include_dcf=False)
    summary = build_valuation_summary(v)
    assert summary["confidence"] in ("high", "medium", "low")
    assert isinstance(summary["drivers"], list)


def test_preprofit_ps_method_in_band():
    fund = _sample(
        quarterly_trends=[
            QuarterlyMetric(period="2024-Q4", eps=-1.0),
            QuarterlyMetric(period="2024-Q3", eps=-0.5),
            QuarterlyMetric(period="2024-Q2", eps=-0.2),
            QuarterlyMetric(period="2024-Q1", eps=-0.1),
        ],
        ttm_revenue=100_000_000_000,
        price_to_sales=8.0,
    )
    v = build_valuation_assessment(fund, 200.0, include_dcf=False)
    assert v.data_available
    ps = next(m for m in v.methods if m.method == "price_to_sales")
    assert ps.data_available


def test_limited_history_adds_gap():
    fund = _sample(
        benchmark=FundamentalBenchmark(data_available=False, message="thin history"),
    )
    v = build_valuation_assessment(fund, 200.0, include_dcf=False)
    assert "valuation_limited_history" in v.data_gaps


def test_bank_skips_dcf():
    fund = _sample(sector="Financial Services", industry="Banks - Regional")
    v = build_valuation_assessment(fund, 50.0, include_dcf=True)
    assert v.dcf_fair_value is None or "dcf_skipped_financial" in v.data_gaps

# --- from test_valuation_archetypes.py ---

"""Archetype regression tests for fair-value realism improvements."""

from trade_sentinel_api.models.schemas import (
    FundamentalsSnapshot,
)
from trade_sentinel_api.services.valuation import (
    _build_dcf,
    _dcf_enterprise_value,
    _ev_ebitda_method,
    _fade_growth_year,
    _ps_method,
    _solve_implied_start_growth,
)


def _base(**kwargs) -> FundamentalsSnapshot:
    defaults = dict(
        data_available=True,
        sector="Technology",
        market_cap=1_000_000_000_000,
        shares_outstanding=1_000_000_000,
        free_cash_flow=50_000_000_000,
        pe_forward=25.0,
        target_price=220.0,
        target_upside_pct=10.0,
        quarterly_trends=[
            QuarterlyMetric(period="2024-Q4", eps=6.0),
            QuarterlyMetric(period="2024-Q3", eps=5.8),
            QuarterlyMetric(period="2024-Q2", eps=5.5),
            QuarterlyMetric(period="2024-Q1", eps=5.2),
        ],
        cash_flow_trends=[],
        benchmark=FundamentalBenchmark(
            median_pe_3y=30.0,
            historical_pe_reliable=True,
            revenue_cagr_3y=8.0,
            data_available=True,
        ),
    )
    defaults.update(kwargs)
    return FundamentalsSnapshot(**defaults)


def test_fade_growth_declines_toward_terminal():
    g1 = _fade_growth_year(0.12, 0.025, 1, 5)
    g5 = _fade_growth_year(0.12, 0.025, 5, 5)
    assert g1 == 0.12
    assert abs(g5 - 0.025) < 1e-9
    assert g1 > g5


def test_dcf_fade_produces_lower_value_than_flat_high_growth():
    fcf = 10_000_000_000
    faded = _dcf_enterprise_value(fcf, 0.15, 0.025, 0.10, fade=True)
    flat = _dcf_enterprise_value(fcf, 0.15, 0.025, 0.10, fade=False)
    assert faded is not None and flat is not None
    assert faded[0] < flat[0]


def test_build_dcf_includes_tv_pct_and_implied_growth():
    fund = _base(revenue_growth=0.10, earnings_growth=0.12)
    fair, assumptions, sensitivity, gaps, reliable, implied = _build_dcf(fund, 200.0)
    assert fair is not None
    assert assumptions is not None
    assert assumptions.get("growth_curve") == "linear_fade_to_terminal"
    assert assumptions.get("terminal_value_pct_of_ev") is not None
    assert float(assumptions["terminal_value_pct_of_ev"]) > 0
    assert implied is not None
    labels = [p.label for p in sensitivity]
    assert "bear" in labels and "base" in labels and "bull" in labels


def test_reverse_dcf_round_trip_near_price():
    fund = _base(revenue_growth=0.08)
    price = 180.0
    _, assumptions, _, _, _, implied = _build_dcf(fund, price)
    assert implied is not None
    params = derive_dcf_assumptions(fund)
    solved = _solve_implied_start_growth(
        float(assumptions["base_fcf"]),
        price,
        float(params["terminal_growth"]),
        float(params["discount_rate"]),
        float(params["growth_cap"]),
        fund,
        price,
    )
    assert solved is not None
    assert abs(solved - implied) < 0.02


def test_mature_utility_low_spread():
    fund = _base(
        sector="Utilities",
        industry="Utilities - Regulated Electric",
        revenue_growth=0.03,
        earnings_growth=0.04,
        benchmark=FundamentalBenchmark(
            median_pe_3y=16.0,
            historical_pe_reliable=True,
            revenue_cagr_3y=3.0,
            data_available=True,
        ),
    )
    v = build_valuation_assessment(fund, 100.0, include_dcf=True)
    assert v.data_available
    assert v.method_spread_pct is None or v.method_spread_pct < 150


def test_high_growth_tech_excludes_distorted_historical_pe():
    fund = _base(
        benchmark=FundamentalBenchmark(
            median_pe_3y=143.0,
            historical_pe_reliable=False,
            data_available=True,
        ),
        pe_forward=25.0,
        revenue_growth=0.20,
        target_price=296.0,
    )
    v = build_valuation_assessment(fund, 222.0, include_dcf=True)
    hist = next(m for m in v.methods if m.method == "historical_pe")
    assert hist.reliable_for_composite is False
    assert v.fair_value_high is not None and v.fair_value_high < 500


def test_preprofit_ps_in_band():
    fund = _base(
        quarterly_trends=[
            QuarterlyMetric(period="2024-Q4", eps=-1.0),
            QuarterlyMetric(period="2024-Q3", eps=-0.5),
            QuarterlyMetric(period="2024-Q2", eps=-0.2),
            QuarterlyMetric(period="2024-Q1", eps=-0.1),
        ],
        ttm_revenue=100_000_000_000,
        price_to_sales=8.0,
    )
    v = build_valuation_assessment(fund, 200.0, include_dcf=False)
    ps = next(m for m in v.methods if m.method == "price_to_sales")
    assert ps.data_available
    assert ps.reliable_for_composite is True


def test_bank_skips_dcf_uses_pb():
    fund = _base(
        sector="Financial Services",
        industry="Banks - Regional",
        price_to_book=1.1,
    )
    v = build_valuation_assessment(fund, 50.0, include_dcf=True)
    assert "dcf_skipped_financial" in v.data_gaps
    pb = next(m for m in v.methods if m.method == "price_to_book")
    assert pb.data_available


def test_leveraged_ev_ebitda_method():
    fund = _base(
        ebitda=80_000_000_000,
        enterprise_value=1_200_000_000_000,
        total_debt=300_000_000_000,
        total_cash=100_000_000_000,
        pe_forward=12.0,
    )
    m = _ev_ebitda_method(fund, 100.0)
    assert m.data_available
    assert m.fair_value is not None
    assert "debt-aware" in (m.detail or "")


def test_ps_uses_sector_prior_not_self_reference():
    fund = _base(
        sector="Technology",
        ttm_revenue=100_000_000_000,
        market_cap=600_000_000_000,
        price_to_sales=6.0,
    )
    m = _ps_method(fund, 200.0)
    assert m.data_available
    assert "6.00" in (m.detail or "")


def test_margin_of_safety_flag():
    fund = _base()
    v_cheap = build_valuation_assessment(fund, 120.0, include_dcf=False)
    assert v_cheap.margin_of_safety_met is True
    v_mid = build_valuation_assessment(fund, 120.0, include_dcf=False)
    assert v_mid.fair_value_mid is not None
    rich_price = v_mid.fair_value_mid * 0.9
    v_rich = build_valuation_assessment(fund, rich_price, include_dcf=False)
    assert v_rich.margin_of_safety_met is False
