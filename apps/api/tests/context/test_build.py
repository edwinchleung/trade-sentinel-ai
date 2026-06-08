"""Merged from: test_balance_sheet_and_synthesis.py, test_forward_outlook.py, test_reality_check.py, test_context_visuals.py, test_data_gaps.py, test_warnings.py"""

# --- from test_balance_sheet_and_synthesis.py ---

"""Balance sheet trends and synthesis hints for context LLM facts."""

import pandas as pd

from trade_sentinel_api.models.schemas import (
    CashFlowQuarter,
    FundamentalBenchmark,
    FundamentalsSnapshot,
    IncomeStatementQuarter,
    NewsItem,
    QuarterlyMetric,
    ValuationAssessment,
    Warning,
    WarningSeverity,
)
from trade_sentinel_api.services.context import (
    _build_qualitative_hints,
    _build_synthesis_hints,
)
from trade_sentinel_api.services.fundamentals import (
    _build_balance_sheet_trends,
    _build_cash_flow_trends,
    _build_income_statement_trends,
)


def test_build_balance_sheet_trends_four_quarters():
    q_bal = pd.DataFrame(
        {
            pd.Timestamp("2025-03-31"): [10e9, 50e9, 40e9, 80e9, 30e9],
            pd.Timestamp("2024-12-31"): [11e9, 48e9, 38e9, 75e9, 28e9],
            pd.Timestamp("2024-09-30"): [12e9, 45e9, 35e9, 70e9, 26e9],
            pd.Timestamp("2024-06-30"): [13e9, 42e9, 32e9, 65e9, 24e9],
        },
        index=[
            "Total Debt",
            "Stockholders Equity",
            "Cash And Cash Equivalents",
            "Current Assets",
            "Current Liabilities",
        ],
    )
    trends = _build_balance_sheet_trends(q_bal, limit=4)
    assert len(trends) == 4
    assert trends[0].total_debt == 10e9
    assert trends[0].cash == 40e9
    assert trends[0].net_debt == -30e9
    assert trends[0].debt_to_equity is not None
    assert trends[0].current_ratio is not None


def test_build_income_statement_trends_four_quarters():
    q_inc = pd.DataFrame(
        {
            pd.Timestamp("2025-03-31"): [100e9, 70e9, 50e9, 40e9],
            pd.Timestamp("2024-12-31"): [90e9, 63e9, 45e9, 36e9],
            pd.Timestamp("2024-09-30"): [80e9, 56e9, 40e9, 32e9],
            pd.Timestamp("2024-06-30"): [70e9, 49e9, 35e9, 28e9],
        },
        index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"],
    )
    trends = _build_income_statement_trends(q_inc, limit=4)
    assert len(trends) == 4
    assert trends[0].revenue == 100e9
    assert trends[0].operating_income == 50e9
    assert trends[0].operating_margin_pct == 50.0
    assert trends[0].net_margin_pct == 40.0
    assert trends[0].gross_margin_pct == 70.0


def test_build_cash_flow_trends_four_quarters():
    q_cf = pd.DataFrame(
        {
            pd.Timestamp("2025-03-31"): [55e9, -15e9, 40e9],
            pd.Timestamp("2024-12-31"): [50e9, -12e9, 38e9],
            pd.Timestamp("2024-09-30"): [45e9, -10e9, 35e9],
            pd.Timestamp("2024-06-30"): [40e9, -8e9, 32e9],
        },
        index=["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"],
    )
    q_inc = pd.DataFrame(
        {pd.Timestamp("2025-03-31"): [100e9]},
        index=["Total Revenue"],
    )
    trends = _build_cash_flow_trends(q_cf, q_inc, limit=4)
    assert len(trends) == 4
    assert trends[0].operating_cash_flow == 55e9
    assert trends[0].capital_expenditure == -15e9
    assert trends[0].free_cash_flow == 40e9
    assert trends[0].fcf_margin_pct == 40.0


def test_synthesis_hints_fcf_compression():
    fundamentals = FundamentalsSnapshot(
        data_available=True,
        quarterly_trends=[
            QuarterlyMetric(period="2025-Q1", revenue_yoy_pct=25.0),
        ],
        cash_flow_trends=[
            CashFlowQuarter(period="2025-Q1", free_cash_flow=30e9),
            CashFlowQuarter(period="2024-Q4", free_cash_flow=40e9),
        ],
    )
    hints = _build_synthesis_hints(
        fundamentals=fundamentals,
        valuation=None,
        warnings=[],
        macro_overlay=None,
        market={},
        forward_outlook=None,
    )
    assert any("compressed" in h.lower() or "capex" in h.lower() for h in hints)


def test_synthesis_hints_margin_expansion():
    fundamentals = FundamentalsSnapshot(
        data_available=True,
        income_statement_trends=[
            IncomeStatementQuarter(period="2025-Q1", operating_margin_pct=45.0),
            IncomeStatementQuarter(period="2024-Q4", operating_margin_pct=40.0),
            IncomeStatementQuarter(period="2024-Q3", operating_margin_pct=38.0),
            IncomeStatementQuarter(period="2024-Q2", operating_margin_pct=42.0),
        ],
    )
    hints = _build_synthesis_hints(
        fundamentals=fundamentals,
        valuation=None,
        warnings=[],
        macro_overlay=None,
        market={},
        forward_outlook=None,
    )
    assert any("margin" in h.lower() and "expand" in h.lower() for h in hints)


def test_build_qualitative_hints_sector_and_news():
    fundamentals = FundamentalsSnapshot(
        data_available=True,
        sector="Technology",
        industry="Semiconductors",
        valuation_label="premium",
        recommendation="buy",
        fundamental_flags=["GROWTH_DECELERATING"],
    )
    news = [NewsItem(title="AI chip demand drives record data-center revenue")]
    hints = _build_qualitative_hints(
        fundamentals=fundamentals,
        news=news,
        sec_filings=None,
        insider_summary=None,
        forward_outlook=None,
        warnings=[],
        fundamental_warnings=[
            Warning(
                code="GROWTH_DECELERATING",
                message="Revenue growth is decelerating vs recent YoY trends.",
                severity=WarningSeverity.MEDIUM,
            )
        ],
    )
    assert any("Technology" in h for h in hints)
    assert any("headline" in h.lower() for h in hints)
    assert len(hints) <= 5


def test_synthesis_hints_nvda_like_disagreement():
    fundamentals = FundamentalsSnapshot(
        data_available=True,
        sector="Technology",
        target_upside_pct=38.0,
        revenue_growth=0.85,
        total_cash=53e9,
        total_debt=12e9,
        fundamental_flags=["VALUATION_BELOW_HISTORY"],
        benchmark=FundamentalBenchmark(debt_trend="improving", data_available=True),
    )
    valuation = ValuationAssessment(
        data_available=True,
        mos_label="overvalued",
        mos_pct=119.0,
        confidence="low",
        method_spread_pct=434.0,
    )
    hints = _build_synthesis_hints(
        fundamentals=fundamentals,
        valuation=valuation,
        warnings=[
            Warning(
                code="PRICE_ABOVE_FAIR_VALUE",
                message="above fair mid",
                severity=WarningSeverity.MEDIUM,
            )
        ],
        macro_overlay=None,
        market={"macd": type("M", (), {"histogram": -1.29})()},
        forward_outlook=None,
    )
    assert any("disagree" in h.lower() for h in hints)
    assert any("low confidence" in h.lower() or "wide range" in h.lower() for h in hints)
    assert len(hints) <= 6

# --- from test_forward_outlook.py ---

"""Deterministic forward outlook from snapshot fields."""

from trade_sentinel_api.models.schemas import (
    EarningsSnapshot,
    InsiderSummary,
    SecFilingHighlight,
    SecFilingsFeed,
)
from trade_sentinel_api.services.forward_outlook import build_forward_outlook


def test_forward_outlook_watch_items():
    outlook = build_forward_outlook(
        price=100.0,
        change_pct=2.5,
        earnings=EarningsSnapshot(
            next_report_date="2026-07-01",
            days_until=28,
            data_available=True,
        ),
        fundamentals=FundamentalsSnapshot(
            target_price=120.0,
            target_upside_pct=20.0,
            recommendation="buy",
            revenue_growth=0.15,
            data_available=True,
        ),
        news=[NewsItem(title="NVDA beats estimates", url="https://x.com")],
        sec_filings=SecFilingsFeed(
            ticker="NVDA",
            data_available=True,
            filings=[
                SecFilingHighlight(
                    form="8-K",
                    filing_date="2026-06-01",
                    title="Material event",
                    excerpt_available=True,
                    excerpt="Company announced partnership.",
                )
            ],
        ),
        insider_summary=InsiderSummary(
            data_available=True,
            sentiment="accumulation",
            buy_count=3,
            sell_count=1,
        ),
        warnings=[
            Warning(
                code="RSI_OVERBOUGHT",
                message="RSI high",
                severity=WarningSeverity.HIGH,
            )
        ],
    )
    assert outlook.data_available is True
    assert outlook.next_earnings_date == "2026-07-01"
    assert any("Earnings" in w for w in outlook.watch_items)
    assert any("News:" in w for w in outlook.watch_items)
    assert len(outlook.outlook_bullets) >= 1

# --- from test_reality_check.py ---

from trade_sentinel_api.models.schemas import (
    FundamentalAssessment,
    NewsDigest,
    TechnicalAssessment,
)
from trade_sentinel_api.services.reality_check import build_reality_check


def test_reality_check_mixed_bias():
    rc = build_reality_check(
        valuation=ValuationAssessment(
            data_available=True,
            mos_label="undervalued",
            confidence="medium",
        ),
        technical_assessment=TechnicalAssessment(
            data_available=True,
            trend_label="bearish",
            short_term_trend="bearish",
            mid_term_trend="mixed",
        ),
        fundamental_assessment=FundamentalAssessment(
            data_available=True,
            overall_label="favorable",
            highlights=["Strong revenue growth"],
        ),
        news_digest=NewsDigest(data_available=True, overall_sentiment="neutral"),
        warnings=[],
    )
    assert rc.data_available
    assert rc.overall_bias in ("mixed", "constructive", "cautious")
    assert rc.headline


def test_reality_check_includes_warnings():
    rc = build_reality_check(
        valuation=ValuationAssessment(data_available=True, mos_label="overvalued"),
        technical_assessment=TechnicalAssessment(data_available=True, trend_label="bullish"),
        fundamental_assessment=None,
        news_digest=None,
        warnings=[
            Warning(code="RSI_OVERBOUGHT", message="RSI elevated", severity=WarningSeverity.HIGH),
        ],
    )
    assert any("RSI" in r for r in rc.key_risks)

# --- from test_context_visuals.py ---

"""Tests for deterministic context visual snapshot builder."""

from trade_sentinel_api.models.schemas import (
    MacdSnapshot,
)
from trade_sentinel_api.services.context.visuals import build_context_visuals


def _overvalued_valuation() -> ValuationAssessment:
    return ValuationAssessment(
        current_price=150.0,
        fair_value_low=80.0,
        fair_value_mid=98.0,
        fair_value_high=197.0,
        mos_pct=53.1,
        mos_label="overvalued",
        confidence="low",
        methods=[],
        dcf_sensitivity=[],
        is_fund=False,
        data_gaps=[],
        data_available=True,
    )


def test_valuation_pillar_caution_when_overvalued():
    visuals = build_context_visuals(
        valuation=_overvalued_valuation(),
        fundamentals=None,
        macro_overlay=None,
        earnings=None,
        sec_filings=None,
        insider_summary=None,
        options_flow=None,
        forward_outlook=None,
        market={},
        warnings=[],
    )
    val_pillar = next(p for p in visuals.pillars if p.id == "valuation")
    assert val_pillar.stance == "caution"
    val_section = next(s for s in visuals.sections if s.id == "valuation")
    assert val_section.stance == "caution"
    assert any(m.label == "Premium vs mid" for m in val_section.metrics)


def test_growth_sparkline_from_income_trends():
    fundamentals = FundamentalsSnapshot(
        data_available=True,
        quarterly_trends=[],
        income_statement_trends=[
            IncomeStatementQuarter(period="Q4", operating_margin_pct=28.0),
            IncomeStatementQuarter(period="Q3", operating_margin_pct=24.0),
            IncomeStatementQuarter(period="Q2", operating_margin_pct=22.0),
        ],
        fundamental_flags=[],
    )
    visuals = build_context_visuals(
        valuation=None,
        fundamentals=fundamentals,
        macro_overlay=None,
        earnings=None,
        sec_filings=None,
        insider_summary=None,
        options_flow=None,
        forward_outlook=None,
        market={},
        warnings=[],
    )
    growth = next(s for s in visuals.sections if s.id == "growth")
    assert len(growth.sparkline) == 3
    assert growth.sparkline[0].period == "Q2"
    assert growth.sparkline[-1].period == "Q4"


def test_missing_fundamentals_sections_unavailable():
    visuals = build_context_visuals(
        valuation=None,
        fundamentals=None,
        macro_overlay=None,
        earnings=None,
        sec_filings=None,
        insider_summary=None,
        options_flow=None,
        forward_outlook=None,
        market={},
        warnings=[],
    )
    growth = next(s for s in visuals.sections if s.id == "growth")
    assert growth.stance == "unavailable"
    assert growth.metrics == []
    fund_pillar = next(p for p in visuals.pillars if p.id == "fundamentals")
    assert fund_pillar.stance == "unavailable"


def test_earnings_catalyst_metrics():
    visuals = build_context_visuals(
        valuation=None,
        fundamentals=None,
        macro_overlay=None,
        earnings=EarningsSnapshot(
            data_available=True,
            days_until=5,
            surprise_pct=12.5,
        ),
        sec_filings=None,
        insider_summary=None,
        options_flow=None,
        forward_outlook=None,
        market={},
        warnings=[],
    )
    catalysts = next(s for s in visuals.sections if s.id == "catalysts")
    assert catalysts.stance == "caution"
    assert any(m.label == "Earnings" and m.value == "5d" for m in catalysts.metrics)


def test_technical_section_uses_assessment_metrics():
    ta = TechnicalAssessment(
        data_available=True,
        trend_label="bullish",
        rsi_14=55.0,
        macd=MacdSnapshot(macd=1.0, signal=0.5, histogram=0.5),
        atr_pct=2.5,
        range_position_pct=72.0,
        signals=[],
    )
    visuals = build_context_visuals(
        valuation=None,
        fundamentals=None,
        macro_overlay=None,
        earnings=None,
        sec_filings=None,
        insider_summary=None,
        options_flow=None,
        forward_outlook=None,
        market={"rsi": 55.0},
        warnings=[],
        technical_assessment=ta,
        price_history=[
            {"date": "2024-01-01", "close": 100.0},
            {"date": "2024-01-02", "close": 101.0},
        ],
    )
    tech = next(s for s in visuals.sections if s.id == "technical")
    assert tech.stance == "favorable"
    assert any(m.label == "Trend" and m.value == "Bullish" for m in tech.metrics)
    assert any(m.label == "RSI" for m in tech.metrics)
    assert any(m.label == "MACD hist" for m in tech.metrics)
    assert len(tech.sparkline) == 2

# --- from test_data_gaps.py ---

from trade_sentinel_api.models.schemas import MacroContextOverlay
from trade_sentinel_api.services.data_gaps import (
    collapse_cpi_gaps,
    gap_display_label,
    macro_facts_data_gaps,
    sanitize_briefing_data_gaps,
    sanitize_context_data_gaps,
)
from trade_sentinel_api.services.macro.context import macro_context_facts


def test_sanitize_drops_t10y2y_when_curve_available():
    gaps = sanitize_context_data_gaps(
        ["fred_T10Y2Y_fetch_failed", "fred_auth_failed"],
        ["fred_T10Y2Y_fetch_failed"],
        yield_curve_available=True,
        cpi_yoy_available=False,
    )
    assert "fred_T10Y2Y_fetch_failed" not in gaps
    assert gaps == ["fred_auth_failed"]


def test_context_allowlist_drops_infra_gaps():
    gaps = sanitize_context_data_gaps(
        ["fred_CPIAUCSL_fetch_failed", "yfinance_macro_news_empty", "rss_bls_fetch_failed"],
        ["fred_auth_failed"],
        yield_curve_available=True,
        cpi_yoy_available=False,
    )
    assert gaps == ["fred_auth_failed"]


def test_sanitize_blocks_llm_invented_gaps():
    gaps = sanitize_context_data_gaps(
        [
            "insider_transaction_details_unavailable",
            "ISM_Services_PMI_actual_not_yet_released",
        ],
        [],
        yield_curve_available=False,
        insider_quality={"level": "partial", "insider_requested": True},
    )
    assert gaps == []


def test_sanitize_adds_insider_feed_empty_when_feed_unavailable():
    gaps = sanitize_context_data_gaps(
        [],
        [],
        yield_curve_available=False,
        insider_quality={
            "level": "none",
            "insider_requested": True,
            "feed_unavailable": True,
        },
    )
    assert gaps == ["insider_feed_empty"]


def test_sanitize_no_insider_gap_when_filings_present():
    gaps = sanitize_context_data_gaps(
        [],
        [],
        yield_curve_available=False,
        insider_quality={
            "level": "partial",
            "insider_requested": True,
            "feed_unavailable": False,
        },
    )
    assert "insider_feed_empty" not in gaps


def test_context_cap_at_three():
    gaps = sanitize_context_data_gaps(
        ["fred_auth_failed", "fundamentals_unavailable", "earnings_unavailable", "llm_parse_error"],
        [],
        yield_curve_available=False,
    )
    assert len(gaps) == 3


def test_collapse_cpi_gaps():
    assert collapse_cpi_gaps(
        ["fred_CPIAUCSL_fetch_failed", "fred_UNRATE_fetch_failed"]
    ) == ["fred_UNRATE_fetch_failed", "fred_cpi_yoy_unavailable"]


def test_macro_facts_data_gaps_filters_infra():
    assert macro_facts_data_gaps(
        ["fred_CPIAUCSL_fetch_failed", "fred_auth_failed", "yfinance_macro_news_empty"]
    ) == ["fred_auth_failed"]


def test_macro_context_facts_omits_infra_gaps():
    overlay = MacroContextOverlay(
        trading_date="2026-06-03",
        has_content=True,
        relevant_events=[],
        data_gaps=["fred_CPIAUCSL_fetch_failed", "rss_bls_fetch_failed"],
    )
    facts = macro_context_facts(overlay)
    assert "fred_CPIAUCSL_fetch_failed" not in facts.get("data_gaps", [])
    assert "data_gaps" not in facts or facts["data_gaps"] == []


def test_macro_context_facts_keeps_fred_auth():
    overlay = MacroContextOverlay(
        trading_date="2026-06-03",
        has_content=True,
        relevant_events=[],
        data_gaps=["fred_auth_failed", "yfinance_macro_news_empty"],
    )
    facts = macro_context_facts(overlay)
    assert facts.get("data_gaps") == ["fred_auth_failed"]


def test_gap_display_label():
    assert "FRED" in gap_display_label("fred_auth_failed")
    assert "macro news" in gap_display_label("macro_news_all_sources_empty").lower()


def test_briefing_keeps_cpi_gap():
    gaps = sanitize_briefing_data_gaps(
        ["fred_CPIAUCSL_fetch_failed", "yfinance_macro_news_empty"],
        yield_curve_available=True,
        cpi_yoy_available=False,
    )
    assert "fred_CPIAUCSL_fetch_failed" in gaps
    assert "yfinance_macro_news_empty" in gaps


def test_briefing_sanitize_drops_t10y2y_when_curve_ok():
    raw = ["fred_T10Y2Y_fetch_failed"] * 10
    gaps = sanitize_briefing_data_gaps(raw, yield_curve_available=True)
    assert gaps == []

# --- from test_warnings.py ---

from trade_sentinel_api.services.warnings import build_technical_warnings


def test_rsi_overbought():
    w = build_technical_warnings(rsi=75.0, volume_ratio=1.0)
    assert any(x.code == "RSI_OVERBOUGHT" for x in w)


def test_rsi_oversold():
    w = build_technical_warnings(rsi=25.0, volume_ratio=1.0)
    assert any(x.code == "RSI_OVERSOLD" for x in w)


def test_volume_spike():
    w = build_technical_warnings(rsi=50.0, volume_ratio=2.5)
    assert any(x.code == "VOLUME_SPIKE" for x in w)


def test_macd_bearish():
    macd = MacdSnapshot(macd=1.0, signal=2.0, histogram=-0.5)
    w = build_technical_warnings(rsi=50.0, volume_ratio=1.0, macd=macd)
    assert any(x.code == "MACD_BEARISH" for x in w)


def test_macd_bullish():
    macd = MacdSnapshot(macd=3.0, signal=2.0, histogram=0.5)
    w = build_technical_warnings(rsi=50.0, volume_ratio=1.0, macd=macd)
    assert any(x.code == "MACD_BULLISH" for x in w)


def test_macd_bearish_divergence_from_assessment():
    ta = TechnicalAssessment(
        data_available=True,
        macd_divergence="bearish",
        trend_label="mixed",
        signals=["MACD_BEARISH_DIVERGENCE"],
    )
    w = build_technical_warnings(50.0, 1.0, technical_assessment=ta)
    assert any(x.code == "MACD_BEARISH_DIVERGENCE" for x in w)


def test_below_sma50_warning():
    ta = TechnicalAssessment(
        data_available=True,
        sma_50=110.0,
        price_vs_sma_50_pct=-5.0,
        trend_label="bearish",
    )
    w = build_technical_warnings(50.0, 1.0, technical_assessment=ta)
    assert any(x.code == "BELOW_SMA50" for x in w)


def test_near_52w_high_warning():
    ta = TechnicalAssessment(
        data_available=True,
        range_position_pct=95.0,
        trend_label="bullish",
    )
    w = build_technical_warnings(50.0, 1.0, technical_assessment=ta)
    assert any(x.code == "NEAR_52W_HIGH" for x in w)


# --- context build: fundamentals None (NVDA 500 regression) ---

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.context.summarize_context", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.resolve_ticker_valuation", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.fetch_sec_filings", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.fetch_earnings_snapshot", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.aggregate_market_context", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.get_cached", return_value=None)
@patch("trade_sentinel_api.services.context.set_cached")
async def test_build_ticker_context_survives_missing_fundamentals(
    _set,
    _get,
    mock_market,
    mock_earnings,
    mock_sec,
    mock_resolve,
    mock_summarize,
):
    from trade_sentinel_api.models.schemas import (
        ContextSummary,
        EarningsSnapshot,
        SecFilingsFeed,
        ValuationAssessment,
    )
    from trade_sentinel_api.services.context import build_ticker_context

    mock_market.return_value = {
        "price": None,
        "change_pct": 0,
        "volume": 0,
        "volume_avg_30d": 0,
        "volume_ratio": 0,
        "news": [],
    }
    mock_earnings.return_value = EarningsSnapshot(data_available=False)
    mock_sec.return_value = SecFilingsFeed(ticker="NVDA", filings=[], data_available=False)
    mock_resolve.return_value = (None, ValuationAssessment(data_available=False))
    mock_summarize.return_value = ContextSummary(
        bullets=["a", "b", "c", "d", "e", "f"],
        model="test",
    )

    ctx = await build_ticker_context("NVDA", summarize=True)

    assert ctx.ticker == "NVDA"
    mock_summarize.assert_called_once()
    assert mock_summarize.call_args.kwargs.get("prompt_version") != "v3"
