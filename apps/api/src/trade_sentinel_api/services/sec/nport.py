"""Fund-level N-PORT holdings for ETF/mutual fund tickers."""

from __future__ import annotations

import asyncio

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import FundHoldingRow, FundHoldingsSnapshot
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.sec.nport_bulk import fund_cik_for_ticker, query_nport_holdings


def _fetch_fund_holdings_sync(ticker: str) -> FundHoldingsSnapshot:
    sym = ticker.upper()
    fund_cik = fund_cik_for_ticker(sym)
    if not fund_cik:
        return FundHoldingsSnapshot(
            fund_ticker=sym,
            message=f"No fund CIK mapping for {sym}.",
        )

    rows = query_nport_holdings(fund_cik)
    if not rows:
        return FundHoldingsSnapshot(
            fund_ticker=sym,
            fund_cik=fund_cik,
            message="No N-PORT holdings in index; run N-PORT bulk ingest.",
        )

    report_date = rows[0].get("report_date")
    holdings = [
        FundHoldingRow(
            name=r.get("holding_name") or r.get("ticker"),
            cusip=r.get("cusip"),
            ticker=r.get("ticker"),
            asset_category=r.get("asset_category"),
            fair_value_usd=float(r["fair_value_usd"]) if r.get("fair_value_usd") is not None else None,
            pct_of_nav=float(r["pct_of_nav"]) if r.get("pct_of_nav") is not None else None,
        )
        for r in rows
    ]

    equity = fixed = deriv = 0.0
    total = sum(h.fair_value_usd or 0 for h in holdings) or 1.0
    for h in holdings:
        cat = (h.asset_category or "").upper()
        val = h.fair_value_usd or 0
        if "EC" in cat or "ST" in cat or cat.startswith("E"):
            equity += val
        elif "DB" in cat or "FI" in cat:
            fixed += val
        elif "DE" in cat or "DR" in cat:
            deriv += val

    return FundHoldingsSnapshot(
        fund_ticker=sym,
        fund_cik=fund_cik,
        fund_name=rows[0].get("fund_name"),
        report_date=report_date,
        holdings=holdings[:30],
        equity_pct=round(equity / total * 100, 1),
        fixed_income_pct=round(fixed / total * 100, 1),
        derivatives_pct=round(deriv / total * 100, 1),
        data_available=True,
    )


async def fetch_fund_holdings(ticker: str) -> FundHoldingsSnapshot:
    cache_key = f"v1:{ticker.upper()}"
    cached = get_cached("smart_money_nport", cache_key)
    if cached:
        return FundHoldingsSnapshot(**cached)
    result = await asyncio.to_thread(_fetch_fund_holdings_sync, ticker.upper())
    ttl = get_settings().smart_money_13f_cache_hours * 3600
    set_cached_ttl("smart_money_nport", cache_key, result.model_dump(mode="json"), ttl)
    return result
