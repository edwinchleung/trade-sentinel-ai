"""Merged from: test_ticker_valuation_sync.py, test_pe_vs_history.py"""

# --- from test_ticker_valuation_sync.py ---

"""Fair-value resolver shared by context and digest."""

from unittest.mock import AsyncMock, patch

import pytest

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    DigestTickerRow,
    FundamentalBenchmark,
    FundamentalsSnapshot,
    QuarterlyMetric,
    ValuationAssessment,
)
from trade_sentinel_api.services.ticker_valuation import (
    hydrate_digest_row,
    resolve_ticker_valuation,
    valuation_digest_fields,
)
from trade_sentinel_api.services.valuation import build_valuation_assessment


def _sample_fundamentals() -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
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
        valuation_label="moderate",
    )


@pytest.mark.asyncio
async def test_resolve_matches_direct_build():
    fund = _sample_fundamentals()
    with patch(
        "trade_sentinel_api.services.ticker_valuation.fetch_fundamentals_snapshot",
        new_callable=AsyncMock,
        return_value=fund,
    ):
        with patch(
            "trade_sentinel_api.services.ticker_valuation.get_cached",
            return_value=None,
        ):
            with patch("trade_sentinel_api.services.ticker_valuation.set_cached_ttl"):
                _, resolved = await resolve_ticker_valuation("AAPL", price=200.0)
    include_dcf = get_settings().valuation_include_dcf
    direct = build_valuation_assessment(fund, 200.0, include_dcf=include_dcf)
    assert resolved.mos_pct == direct.mos_pct
    assert resolved.fair_value_mid == direct.fair_value_mid


@pytest.mark.asyncio
async def test_resolve_uses_valuation_cache():
    fund = _sample_fundamentals()
    direct = build_valuation_assessment(fund, 200.0, include_dcf=False)
    cached_payload = {
        "fundamentals": fund.model_dump(mode="json"),
        "valuation": direct.model_dump(mode="json"),
    }
    fetch_mock = AsyncMock(return_value=fund)
    with patch(
        "trade_sentinel_api.services.ticker_valuation.fetch_fundamentals_snapshot",
        fetch_mock,
    ):
        with patch(
            "trade_sentinel_api.services.ticker_valuation.get_cached",
            return_value=cached_payload,
        ):
            _, resolved = await resolve_ticker_valuation("AAPL", price=200.0)
    fetch_mock.assert_not_called()
    assert resolved.fair_value_mid == direct.fair_value_mid


def test_valuation_digest_fields_maps_mos():
    v = build_valuation_assessment(_sample_fundamentals(), 200.0, include_dcf=False)
    fields = valuation_digest_fields(v, _sample_fundamentals())
    assert fields["mos_pct"] == v.mos_pct
    assert fields["mos_label"] == v.mos_label
    assert fields["fair_value_mid"] == v.fair_value_mid
    assert fields["valuation_label"] == "moderate"


@pytest.mark.asyncio
async def test_hydrate_digest_row_updates_mos():
    fund = _sample_fundamentals()
    v_old = ValuationAssessment(data_available=True, mos_pct=50.0, fair_value_mid=100.0)
    v_new = build_valuation_assessment(fund, 200.0, include_dcf=False)
    row = DigestTickerRow(ticker="AAPL", price=200.0, mos_pct=v_old.mos_pct)

    with patch(
        "trade_sentinel_api.services.ticker_valuation.aggregate_market_context",
        new_callable=AsyncMock,
        return_value={"price": 200.0, "change_pct": 1.0},
    ):
        with patch(
            "trade_sentinel_api.services.ticker_valuation.resolve_ticker_valuation",
            new_callable=AsyncMock,
            return_value=(fund, v_new),
        ):
            hydrated = await hydrate_digest_row(row)

    assert hydrated.mos_pct == v_new.mos_pct
    assert hydrated.fair_value_mid == v_new.fair_value_mid

# --- from test_pe_vs_history.py ---

"""P/E vs 3Y median — TTM P/E series, timezone alignment, and PE fallbacks."""

import pandas as pd

from trade_sentinel_api.services.fundamentals import (
    _historical_pe_reliable,
    _pe_series_ttm,
    _pe_vs_history,
)

_QUARTER_COLS = [
    pd.Timestamp("2025-03-31"),
    pd.Timestamp("2024-12-31"),
    pd.Timestamp("2024-09-30"),
    pd.Timestamp("2024-06-30"),
    pd.Timestamp("2024-03-31"),
    pd.Timestamp("2023-12-31"),
    pd.Timestamp("2023-09-30"),
    pd.Timestamp("2023-06-30"),
]


def _eps_frame(eps_values: list[float]) -> pd.DataFrame:
    assert len(eps_values) == len(_QUARTER_COLS)
    return pd.DataFrame(
        {col: [eps] for col, eps in zip(_QUARTER_COLS, eps_values)},
        index=["Diluted EPS"],
    )


def test_pe_vs_history_timezone_aware_index():
    q_inc = _eps_frame([2.0, 1.5, 1.2, 1.0, 0.9, 0.8, 0.7, 0.6])
    idx = pd.to_datetime(q_inc.columns).tz_localize("UTC")
    hist = pd.DataFrame(
        {"Close": [200.0, 190.0, 180.0, 170.0, 160.0, 150.0, 140.0, 130.0]},
        index=idx,
    )
    pct, pe, median, *_rest = _pe_vs_history(hist, q_inc, 210.0, None, 25.0)
    assert pe == 25.0
    assert pct is not None
    assert median is not None
    assert isinstance(pct, float)


def test_pe_vs_history_trailing_pe_from_price_eps():
    q_inc = _eps_frame([1.25] * 8)
    hist = pd.DataFrame(
        {"Close": [100.0, 95.0, 90.0, 85.0, 80.0, 75.0, 70.0, 65.0]},
        index=q_inc.columns,
    )
    pct, pe, median, *_rest = _pe_vs_history(hist, q_inc, 50.0, None, None)
    assert pe == 10.0
    assert median is not None
    assert pct is not None


def test_pe_series_ttm_not_single_quarter_spike():
    q_inc = _eps_frame([6.0, 5.0, 0.5, 0.1, 0.08, 0.06, 0.05, 0.04])
    hist = pd.DataFrame(
        {"Close": [200.0, 190.0, 180.0, 170.0, 160.0, 150.0, 140.0, 130.0]},
        index=q_inc.columns,
    )
    series = _pe_series_ttm(hist, q_inc, 200.0)
    assert len(series) >= 2
    assert max(series) <= 80


def test_historical_pe_reliable_flags_distortion():
    assert _historical_pe_reliable(143.0, 25.0) is False
    assert _historical_pe_reliable(35.0, 25.0) is True
    assert _historical_pe_reliable(70.0, 25.0) is False
