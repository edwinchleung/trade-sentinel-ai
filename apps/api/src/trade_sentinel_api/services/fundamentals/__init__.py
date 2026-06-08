"""Fundamental snapshot assembly."""

from __future__ import annotations

import asyncio

from trade_sentinel_api.models.schemas import FundamentalsSnapshot
from trade_sentinel_api.services.currency import fx_rate_financial_to_usd
from trade_sentinel_api.services.fundamentals.benchmark import (
    _build_benchmark,
    _valuation_label,
)
from trade_sentinel_api.services.fundamentals.helpers import (
    _EPS_ROWS,
    _REVENUE_ROWS,
    _eps_trend,
    _historical_pe_reliable,
    _margin_vs_history,
    _pe_series_ttm,
    _pe_vs_history,
    _revenue_cagr_3y,
    _revenue_growth_acceleration,
    _row_value,
    _ttm_eps_at,
)
from trade_sentinel_api.services.fundamentals.parser import (
    _analyst_counts_from_yfinance,
    _apply_currency_normalization,
    _build_balance_sheet_trends,
    _build_cash_flow_trends,
    _build_income_statement_trends,
    _build_quarterly_trends,
    _fetch_finnhub_enrichment,
    _fetch_yfinance_fundamentals_sync,
    _fundamentals_from_yf_data,
    _merge_finnhub,
)


async def fetch_fundamentals_snapshot(
    ticker: str, current_price: float | None = None
) -> FundamentalsSnapshot:
    finnhub = await _fetch_finnhub_enrichment(ticker)
    snapshot = await asyncio.to_thread(_fetch_yfinance_fundamentals_sync, ticker, current_price)
    if finnhub:
        snapshot = _merge_finnhub(snapshot, finnhub)
    if snapshot.target_price and current_price and current_price > 0:
        upside = round((snapshot.target_price - current_price) / current_price * 100, 2)
        snapshot = snapshot.model_copy(update={"target_upside_pct": upside})
    return snapshot


__all__ = [
    "_EPS_ROWS",
    "_REVENUE_ROWS",
    "_analyst_counts_from_yfinance",
    "_apply_currency_normalization",
    "_build_balance_sheet_trends",
    "_build_benchmark",
    "_build_cash_flow_trends",
    "_build_income_statement_trends",
    "_build_quarterly_trends",
    "_eps_trend",
    "_fundamentals_from_yf_data",
    "_historical_pe_reliable",
    "_margin_vs_history",
    "_merge_finnhub",
    "_pe_series_ttm",
    "_pe_vs_history",
    "_revenue_cagr_3y",
    "_revenue_growth_acceleration",
    "_row_value",
    "_ttm_eps_at",
    "_valuation_label",
    "fetch_fundamentals_snapshot",
    "fx_rate_financial_to_usd",
]
