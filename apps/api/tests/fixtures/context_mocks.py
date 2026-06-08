"""Shared mocks and patch helpers for context endpoint tests."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import wraps
from unittest.mock import AsyncMock, patch

from trade_sentinel_api.models.schemas import (
    ContextSummary,
    EarningsSnapshot,
    FundamentalsSnapshot,
    InsiderTimeline,
    Institutional13FChange,
    Institutional13FChanges,
    MacdSnapshot,
    NewsItem,
    SecFilingsFeed,
    ValuationAssessment,
)

MOCK_MARKET = {
    "price": 150.25,
    "change_pct": 1.2,
    "volume": 50_000_000,
    "volume_avg_30d": 40_000_000.0,
    "volume_ratio": 1.25,
    "rsi": 72.5,
    "macd": MacdSnapshot(macd=1.1, signal=0.9, histogram=0.2),
    "price_history": [
        {"date": "2026-06-01", "close": 148.0},
        {"date": "2026-06-02", "close": 150.25},
    ],
    "news": [NewsItem(title="Test headline", url="https://example.com", source="Test")],
}

MOCK_SUMMARY = ContextSummary(
    bullets=["Bullet one.", "Bullet two.", "Bullet three."],
    model="test",
    cached_at=datetime.now(UTC),
    data_gaps=[],
)

MOCK_EARNINGS = EarningsSnapshot(data_available=False, message="Earnings data unavailable.")

MOCK_FUNDAMENTALS = FundamentalsSnapshot(
    sector="Technology",
    pe_forward=30.0,
    data_available=True,
)

MOCK_VALUATION = ValuationAssessment(
    data_available=True,
    fair_value_mid=140.0,
    mos_pct=5.0,
    mos_label="fair",
)

MOCK_SEC_FILINGS = SecFilingsFeed(ticker="TEST", data_available=False, message="No filings.")

MOCK_13F = Institutional13FChanges(
    ticker="TEST",
    as_of=datetime.now(UTC),
    changes=[
        Institutional13FChange(
            filer_name="BlackRock",
            filer_cik="0001364742",
            ticker="TEST",
            change_type="increased",
            pct_change=5.0,
        )
    ],
    conviction_buy=True,
    data_available=True,
)


def patch_context_pipeline(*, include_smart_money: bool = False, summarize: bool = True):
    """Decorator stacking patches for GET /api/v1/context tests."""

    def decorator(fn):
        @wraps(fn)
        @patch(
            "trade_sentinel_api.services.context.resolve_activist_filing",
            new_callable=AsyncMock,
            return_value=None,
        )
        @patch(
            "trade_sentinel_api.services.context.fetch_13f_changes",
            new_callable=AsyncMock,
            return_value=MOCK_13F if include_smart_money else None,
        )
        @patch(
            "trade_sentinel_api.services.context.fetch_insider_timeline",
            new_callable=AsyncMock,
            return_value=InsiderTimeline(ticker="TEST", transactions=[], data_available=False),
        )
        @patch(
            "trade_sentinel_api.services.context.analyze_options_flow",
            new_callable=AsyncMock,
            return_value=(None, []),
        )
        @patch(
            "trade_sentinel_api.services.context.fetch_sec_filings",
            new_callable=AsyncMock,
            return_value=MOCK_SEC_FILINGS,
        )
        @patch(
            "trade_sentinel_api.services.context.resolve_ticker_valuation",
            new_callable=AsyncMock,
            return_value=(MOCK_FUNDAMENTALS, MOCK_VALUATION),
        )
        @patch(
            "trade_sentinel_api.services.context.fetch_earnings_snapshot",
            new_callable=AsyncMock,
            return_value=MOCK_EARNINGS,
        )
        @patch(
            "trade_sentinel_api.services.context.summarize_context",
            new_callable=AsyncMock,
            return_value=MOCK_SUMMARY if summarize else None,
        )
        @patch(
            "trade_sentinel_api.services.context.aggregate_market_context",
            new_callable=AsyncMock,
            return_value={**MOCK_MARKET, "_hist": None},
        )
        def wrapped(*_mocks, **kwargs):
            return fn(**kwargs)

        return wrapped

    return decorator
