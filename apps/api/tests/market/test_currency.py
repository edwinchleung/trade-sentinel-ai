"""Currency normalization — all statement amounts in USD."""

from unittest.mock import patch

import pandas as pd
import pytest

from trade_sentinel_api.models.schemas import (
    CashFlowQuarter,
    FundamentalBenchmark,
    FundamentalsSnapshot,
    QuarterlyMetric,
)
from trade_sentinel_api.services.fundamentals import (
    _apply_currency_normalization,
    _build_quarterly_trends,
    _ttm_eps_at,
)
from trade_sentinel_api.services.valuation import (
    _eps_for_valuation,
    build_valuation_assessment,
)


def _adr_snapshot(**kwargs) -> FundamentalsSnapshot:
    rate = 0.032
    defaults = dict(
        data_available=True,
        trading_currency="USD",
        financial_currency="TWD",
        market_cap=500_000_000_000,
        free_cash_flow=1_000_000_000_000 * rate,
        ttm_revenue=2_000_000_000_000 * rate,
        trailing_eps_quote=5.5,
        shares_outstanding=5_000_000_000,
        target_price=220.0,
        target_upside_pct=10.0,
        quarterly_trends=[
            QuarterlyMetric(
                period="2024-Q4",
                eps=35.0 * rate,
                revenue=500_000_000_000 * rate,
            ),
            QuarterlyMetric(period="2024-Q3", eps=34.0 * rate, revenue=480_000_000_000 * rate),
            QuarterlyMetric(period="2024-Q2", eps=33.0 * rate, revenue=470_000_000_000 * rate),
            QuarterlyMetric(period="2024-Q1", eps=32.0 * rate, revenue=460_000_000_000 * rate),
        ],
        cash_flow_trends=[
            CashFlowQuarter(period="2024-Q4", free_cash_flow=250_000_000_000 * rate),
            CashFlowQuarter(period="2024-Q3", free_cash_flow=240_000_000_000 * rate),
            CashFlowQuarter(period="2024-Q2", free_cash_flow=230_000_000_000 * rate),
            CashFlowQuarter(period="2024-Q1", free_cash_flow=220_000_000_000 * rate),
        ],
        benchmark=FundamentalBenchmark(median_pe_3y=20.0, historical_pe_reliable=True, data_available=True),
    )
    defaults.update(kwargs)
    return FundamentalsSnapshot(**defaults)


@patch("trade_sentinel_api.services.fundamentals.fx_rate_financial_to_usd", return_value=0.032)
def test_apply_currency_sets_usd_metadata(mock_fx):
    snap = _adr_snapshot()
    out = _apply_currency_normalization(snap)
    assert out.monetary_values_normalized is True
    assert out.amounts_currency == "USD"
    assert out.fx_rate_financial_to_trading == 0.032
    assert "currency_converted" in out.fundamental_flags


@patch("trade_sentinel_api.services.fundamentals.fx_rate_financial_to_usd", return_value=None)
def test_apply_currency_unresolved_when_no_fx(mock_fx):
    snap = _adr_snapshot(
        free_cash_flow=1_000_000_000_000,
        quarterly_trends=[QuarterlyMetric(period="2024-Q4", eps=110.0, revenue=500e9)],
    )
    out = _apply_currency_normalization(snap)
    assert out.monetary_values_normalized is False
    assert "currency_mismatch_unresolved" in out.fundamental_flags


def test_build_quarterly_trends_converts_eps_to_usd():
    col = pd.Timestamp("2024-12-31")
    q_inc = pd.DataFrame(
        [[500e9], [110.0]],
        index=["Total Revenue", "Diluted EPS"],
        columns=[col],
    )
    out = _build_quarterly_trends(q_inc, limit=1, usd_rate=0.032)
    assert len(out) == 1
    assert out[0].eps == pytest.approx(110.0 * 0.032)
    assert out[0].revenue == pytest.approx(500e9 * 0.032)


def test_ttm_eps_at_converts_to_usd():
    cols = [pd.Timestamp(f"2024-{m}-01") for m in (12, 9, 6, 3)]
    q_inc = pd.DataFrame(
        [[110.0] * 4],
        index=["Diluted EPS"],
        columns=cols,
    )
    ttm = _ttm_eps_at(q_inc, 0, usd_rate=0.032)
    assert ttm == pytest.approx(110.0 * 4 * 0.032)
    assert 200.0 / ttm < 50


def test_eps_for_valuation_uses_quote_eps_when_currencies_differ():
    snap = _adr_snapshot()
    assert _eps_for_valuation(snap) == 5.5


def test_eps_for_valuation_uses_ttm_when_same_currency():
    snap = _adr_snapshot(
        trading_currency="USD",
        financial_currency="USD",
        quarterly_trends=[
            QuarterlyMetric(period="2024-Q4", eps=35.0, revenue=500e9),
            QuarterlyMetric(period="2024-Q3", eps=34.0, revenue=480e9),
            QuarterlyMetric(period="2024-Q2", eps=33.0, revenue=470e9),
            QuarterlyMetric(period="2024-Q1", eps=32.0, revenue=460e9),
        ],
    )
    assert _eps_for_valuation(snap) == 35.0 + 34.0 + 33.0 + 32.0


@patch("trade_sentinel_api.services.fundamentals.fx_rate_financial_to_usd", return_value=0.032)
def test_build_valuation_adr_fair_mid_not_absurd(mock_fx):
    snap = _apply_currency_normalization(_adr_snapshot())
    v = build_valuation_assessment(snap, 200.0, include_dcf=True)
    assert v.data_available
    assert v.fair_value_mid is not None
    assert v.fair_value_mid < 2000
    assert v.fair_value_mid > 20


def test_fx_cache_hit():
    from trade_sentinel_api.services.currency import fetch_fx_rate_sync

    with patch(
        "trade_sentinel_api.services.currency.get_cached",
        return_value={"rate": 0.032},
    ):
        with patch("trade_sentinel_api.services.currency._yahoo_fx_rate") as mock_yahoo:
            rate = fetch_fx_rate_sync("TWD", "USD")
    assert rate == 0.032
    mock_yahoo.assert_not_called()
