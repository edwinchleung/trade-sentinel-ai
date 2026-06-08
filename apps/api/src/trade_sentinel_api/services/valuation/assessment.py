"""Valuation assessment orchestration."""

from __future__ import annotations

import asyncio
import logging

import yfinance as yf

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    FundamentalsSnapshot,
    FundValuationSnapshot,
    ValuationAssessment,
)
from trade_sentinel_api.services.valuation.helpers import (
    _METHOD_SPREAD_LOW_CONFIDENCE,
    _analyst_method,
    _build_dcf,
    _confidence,
    _currency_mismatch_unresolved,
    _ev_ebitda_method,
    _fcf_yield_method,
    _graham_method,
    _headline_composite_band,
    _historical_pe_method,
    _is_bank_or_reit,
    _method_spread_ratio,
    _monetary_ok_for_valuation,
    _mos_label,
    _pb_method,
    _peg_method,
    _premium_vs_mid_pct,
    _ps_method,
    _sector_pe_prior_method,
    _stress_composite_band,
    _weighted_composite_band,
)

logger = logging.getLogger(__name__)

_FUND_QUOTE_TYPES = frozenset({"ETF", "MUTUALFUND", "INDEX"})

def build_valuation_assessment(
    fundamentals: FundamentalsSnapshot | None,
    price: float | None,
    *,
    include_dcf: bool | None = None,
) -> ValuationAssessment:
    settings = get_settings()
    if include_dcf is None:
        include_dcf = settings.valuation_include_dcf

    if not fundamentals or not fundamentals.data_available or price is None or price <= 0:
        return ValuationAssessment(
            data_available=False,
            message="Insufficient fundamentals or price for valuation.",
        )

    if fundamentals.quote_type and fundamentals.quote_type.upper() in _FUND_QUOTE_TYPES:
        fund = fundamentals.fund_valuation
        if fund and fund.nav_price and fund.nav_price > 0:
            prem = (fund.premium_discount_pct or 0) / 100
            band = max(0.02, abs(prem) * 2 + 0.01)
            nav = fund.nav_price
            fund = fund.model_copy(
                update={
                    "fair_value_mid": round(nav, 2),
                    "fair_value_low": round(nav * (1 - band), 2),
                    "fair_value_high": round(nav * (1 + band), 2),
                }
            )
        return ValuationAssessment(
            is_fund=True,
            fund=fund,
            current_price=price,
            fair_value_low=fund.fair_value_low if fund else None,
            fair_value_mid=fund.fair_value_mid if fund else None,
            fair_value_high=fund.fair_value_high if fund else None,
            data_available=fund is not None and fund.data_available,
            message=fund.message if fund else "Fund metrics unavailable.",
        )

    skip_dcf = _is_bank_or_reit(fundamentals)
    reliability_notes: list[str] = []
    gaps: list[str] = []
    if _currency_mismatch_unresolved(fundamentals):
        gaps.append("valuation_currency_mismatch")
        fin = fundamentals.financial_currency or "?"
        trd = fundamentals.trading_currency or "?"
        reliability_notes.append(
            f"Financials reported in {fin}; quote in {trd} — FX conversion unavailable."
        )
    elif "currency_converted" in fundamentals.fundamental_flags:
        fin = fundamentals.financial_currency or "?"
        trd = fundamentals.trading_currency or "?"
        fx = fundamentals.fx_rate_financial_to_trading
        if fx is not None:
            reliability_notes.append(
                f"Statement amounts converted {fin}→{trd} @ {fx:.4f} for fair-value models."
            )
    if not _monetary_ok_for_valuation(fundamentals):
        skip_dcf = True
        gaps.append("dcf_fcf_unavailable")

    methods = [
        _analyst_method(fundamentals),
        _fcf_yield_method(fundamentals, price),
        _graham_method(fundamentals, price),
        _historical_pe_method(fundamentals, price),
        _peg_method(fundamentals),
        _ev_ebitda_method(fundamentals, price),
        _ps_method(fundamentals, price),
        _pb_method(fundamentals, price),
        _sector_pe_prior_method(fundamentals),
    ]

    dcf_fair = None
    dcf_assumptions = None
    dcf_sensitivity: list[DcfSensitivityPoint] = []
    dcf_reliable = False
    dcf_implied_growth: float | None = None
    if include_dcf and not skip_dcf:
        (
            dcf_fair,
            dcf_assumptions,
            dcf_sensitivity,
            dcf_gaps,
            dcf_reliable,
            dcf_implied_growth,
        ) = _build_dcf(fundamentals, price)
        gaps.extend(dcf_gaps)
    elif skip_dcf:
        gaps.append("dcf_skipped_financial")

    if skip_dcf and _is_bank_or_reit(fundamentals):
        reliability_notes.append("DCF skipped — bank/REIT/financial; P/B method preferred.")

    bench = fundamentals.benchmark
    if bench is not None and not bench.data_available:
        gaps.append("valuation_limited_history")

    analyst = methods[0]
    if dcf_fair and analyst.fair_value and analyst.fair_value > 2 * dcf_fair:
        methods[0] = analyst.model_copy(
            update={
                "reliable_for_composite": False,
                "detail": (analyst.detail or "") + " — excluded from headline (>> DCF mid)",
            }
        )
        reliability_notes.append("Analyst target excluded — far above DCF anchor.")

    weighted: list[tuple[str, float]] = []
    composite_anchors: list[float] = []
    composite_drivers: list[str] = []
    for m in methods:
        if m.data_available and m.fair_value and m.reliable_for_composite:
            composite_anchors.append(m.fair_value)
            weighted.append((m.method, m.fair_value))
            composite_drivers.append(m.method)

    if include_dcf and dcf_fair and dcf_reliable:
        composite_anchors.append(dcf_fair)
        weighted.append(("dcf", dcf_fair))
        composite_drivers.append("dcf")
    elif include_dcf and dcf_fair and not dcf_reliable:
        reliability_notes.append("DCF excluded — FCF too volatile for headline band.")

    spread_ratio, spread_pct = _method_spread_ratio(composite_anchors)
    if spread_ratio is not None and spread_ratio > 2.5 and methods[0].reliable_for_composite:
        methods[0] = methods[0].model_copy(
            update={
                "reliable_for_composite": False,
                "detail": (methods[0].detail or "") + " — excluded (wide method spread)",
            }
        )
        composite_anchors = [
            m.fair_value
            for m in methods
            if m.data_available and m.fair_value and m.reliable_for_composite
        ]
        weighted = [
            (m.method, m.fair_value)
            for m in methods
            if m.data_available and m.fair_value and m.reliable_for_composite
        ]
        composite_drivers = [m.method for m in methods if m.reliable_for_composite]
        if dcf_fair and dcf_reliable and dcf_fair not in composite_anchors:
            composite_anchors.append(dcf_fair)
            weighted.append(("dcf", dcf_fair))
            composite_drivers.append("dcf")
        spread_ratio, spread_pct = _method_spread_ratio(composite_anchors)
        reliability_notes.append("Analyst target excluded — methods span wide range.")

    composite_mode = settings.valuation_composite_mode.strip().lower()
    if composite_mode == "weighted" and len(weighted) >= 2:
        fair_low, fair_mid, fair_high = _weighted_composite_band(weighted)
        stress_low, stress_high = _stress_composite_band(composite_anchors)
    else:
        composite_mode = "iqr"
        fair_low, fair_mid, fair_high = _headline_composite_band(composite_anchors)
        stress_low, stress_high = _stress_composite_band(composite_anchors)

    hist_pe = _historical_pe_method(fundamentals, price)
    sector_prior = _sector_pe_prior_method(fundamentals)
    if (
        hist_pe.data_available
        and sector_prior.data_available
        and hist_pe.reliable_for_composite != sector_prior.reliable_for_composite
    ):
        reliability_notes.append(
            "Historical P/E and sector prior disagree on composite eligibility — headline favors issuer history when reliable."
        )

    premium_pct = None
    if fair_mid and fair_mid > 0:
        premium_pct = _premium_vs_mid_pct(price, fair_mid)

    if len(composite_anchors) < 2:
        gaps.append("valuation_few_methods")

    confidence = _confidence(len(composite_anchors), spread_ratio)
    if "valuation_currency_mismatch" in gaps:
        confidence = "low"
    elif "valuation_limited_history" in gaps and confidence == "high":
        confidence = "medium"

    if not reliability_notes and spread_ratio and spread_ratio > _METHOD_SPREAD_LOW_CONFIDENCE:
        reliability_notes.append("Methods disagree widely — use band as directional only.")

    mos_threshold = settings.valuation_mos_buy_threshold_pct
    margin_of_safety_met: bool | None = None
    if fair_mid and fair_mid > 0 and price and price > 0:
        margin_of_safety_met = price <= fair_mid * (1 - mos_threshold / 100)

    return ValuationAssessment(
        current_price=round(price, 2),
        fair_value_low=fair_low,
        fair_value_mid=fair_mid,
        fair_value_high=fair_high,
        fair_value_stress_low=stress_low,
        fair_value_stress_high=stress_high,
        mos_pct=premium_pct,
        mos_label=_mos_label(premium_pct, fundamentals.sector),
        method_spread_pct=spread_pct,
        confidence=confidence,
        methods=methods,
        dcf_fair_value=dcf_fair,
        dcf_implied_growth_at_price=dcf_implied_growth,
        dcf_assumptions=dcf_assumptions,
        dcf_sensitivity=dcf_sensitivity,
        margin_of_safety_met=margin_of_safety_met,
        mos_buy_threshold_pct=mos_threshold,
        reliability_notes=reliability_notes,
        data_gaps=gaps,
        composite_drivers=composite_drivers,
        composite_mode=composite_mode,
        data_available=fair_mid is not None,
        message=None if fair_mid else "Could not derive fair-value band from available methods.",
    )


async def fetch_fund_valuation(ticker: str) -> FundValuationSnapshot:
    return await asyncio.to_thread(_fetch_fund_valuation_sync, ticker)


def _fetch_fund_valuation_sync(ticker: str) -> FundValuationSnapshot:
    symbol = ticker.upper().strip()
    try:
        stock = yf.Ticker(symbol)
        info = stock.info or {}
    except Exception:
        return FundValuationSnapshot(data_available=False, message="Fund data unavailable.")

    quote_type = (info.get("quoteType") or "").upper()
    expense = _safe_float(info.get("annualReportExpenseRatio") or info.get("expenseRatio"))
    total_assets = _safe_float(info.get("totalAssets"))
    nav = _safe_float(info.get("navPrice"))
    price = _safe_float(info.get("regularMarketPrice") or info.get("currentPrice"))
    premium = None
    if nav and price and nav > 0:
        premium = round((price - nav) / nav * 100, 2)

    top_pct = None
    try:
        holdings = stock.fund_holdings
        if holdings is not None and not holdings.empty and "Holding Percent" in holdings.columns:
            top_pct = round(float(holdings["Holding Percent"].head(5).sum()) * 100, 2)
    except Exception:
        pass

    return FundValuationSnapshot(
        quote_type=quote_type or None,
        expense_ratio=round(expense * 100, 3) if expense and expense < 1 else expense,
        total_assets=total_assets,
        nav_price=nav,
        premium_discount_pct=premium,
        top_holdings_pct=top_pct,
        data_available=bool(expense or nav or total_assets),
        message=None,
    )
