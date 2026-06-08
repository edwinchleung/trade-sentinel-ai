"""Multiple-based valuation methods."""

from trade_sentinel_api.services.valuation.methods import common as _c
from trade_sentinel_api.services.valuation.methods.analyst import (
    _historical_pe_is_reliable,
    _median_pe_3y,
)

globals().update({k: v for k, v in vars(_c).items() if not k.startswith("__")})

def _fcf_yield_method(
    fundamentals: FundamentalsSnapshot,
    price: float | None,
) -> ValuationMethodResult:
    if not _monetary_ok_for_valuation(fundamentals):
        return ValuationMethodResult(
            method="fcf_yield",
            data_available=False,
            reliable_for_composite=False,
            detail="FCF yield skipped — reporting currency not aligned with quote currency",
        )
    fcf = fundamentals.free_cash_flow
    mcap = fundamentals.market_cap
    if fcf is None or mcap is None or mcap <= 0 or price is None or price <= 0:
        return ValuationMethodResult(
            method="fcf_yield",
            data_available=False,
            reliable_for_composite=False,
        )
    if fcf <= 0:
        return ValuationMethodResult(
            method="fcf_yield",
            data_available=False,
            detail="FCF not positive — yield method skipped",
            reliable_for_composite=False,
        )
    current_yield = fcf / mcap
    required_yield = max(0.03, min(0.08, current_yield * 2))
    mid_fair = price * (current_yield / required_yield)
    return ValuationMethodResult(
        method="fcf_yield",
        fair_value=round(mid_fair, 2),
        detail=(
            f"Implied @ {required_yield * 100:.1f}% required FCF yield "
            f"(current {current_yield * 100:.1f}%) — diagnostic, not in headline band"
        ),
        data_available=True,
        reliable_for_composite=False,
    )


def _graham_method(
    fundamentals: FundamentalsSnapshot,
    price: float | None,
) -> ValuationMethodResult:
    eps = _eps_for_valuation(fundamentals)
    if eps is None or eps <= 0:
        return ValuationMethodResult(method="graham_eps", data_available=False)
    median_pe = _median_pe_3y(fundamentals)
    cap_pe = min(15.0, median_pe) if median_pe and median_pe > 0 else 15.0
    cap_pe = max(8.0, cap_pe)
    fair = eps * cap_pe
    return ValuationMethodResult(
        method="graham_eps",
        fair_value=round(fair, 2),
        detail=f"TTM EPS × conservative P/E cap ({cap_pe:.1f})",
        data_available=True,
        reliable_for_composite=True,
    )


def _historical_pe_method(
    fundamentals: FundamentalsSnapshot,
    price: float | None,
) -> ValuationMethodResult:
    median_pe = _median_pe_3y(fundamentals)
    eps = _eps_for_valuation(fundamentals)
    reliable = _historical_pe_is_reliable(fundamentals)

    if median_pe is None or eps is None or eps <= 0:
        return ValuationMethodResult(
            method="historical_pe",
            data_available=False,
            reliable_for_composite=False,
        )

    fair = eps * median_pe
    detail = f"TTM EPS × 3Y TTM P/E median ({median_pe:.1f})"
    if not reliable:
        detail += " — excluded from headline band (distorted vs forward P/E)"

    return ValuationMethodResult(
        method="historical_pe",
        fair_value=round(fair, 2),
        detail=detail,
        data_available=True,
        reliable_for_composite=reliable,
    )


def _ps_method(
    fundamentals: FundamentalsSnapshot,
    price: float | None,
) -> ValuationMethodResult:
    if not _monetary_ok_for_valuation(fundamentals):
        return ValuationMethodResult(
            method="price_to_sales",
            data_available=False,
            detail="P/S skipped — reporting currency not aligned with quote currency",
        )
    revenue = fundamentals.ttm_revenue
    mcap = fundamentals.market_cap
    ps = fundamentals.price_to_sales
    if revenue is None or revenue <= 0 or mcap is None or mcap <= 0 or price is None:
        return ValuationMethodResult(method="price_to_sales", data_available=False)
    current_ps = mcap / revenue
    if current_ps <= 0:
        return ValuationMethodResult(method="price_to_sales", data_available=False)
    sector = fundamentals.sector or ""
    sector_ps = _sector_multiple(sector, "ps")
    if sector_ps is None:
        sector_ps = ps if ps and ps > 0 else current_ps * 0.85
    fair = price * (sector_ps / current_ps)
    return ValuationMethodResult(
        method="price_to_sales",
        fair_value=round(fair, 2),
        detail=f"TTM revenue P/S re-rate (current {current_ps:.2f}× → {sector_ps:.2f}×)",
        data_available=True,
        reliable_for_composite=_eps_for_valuation(fundamentals) is None
        or (_eps_for_valuation(fundamentals) or 0) <= 0,
    )


def _peg_method(fundamentals: FundamentalsSnapshot) -> ValuationMethodResult:
    eps = _eps_for_valuation(fundamentals)
    growth = _normalize_growth_pct(fundamentals.earnings_growth)
    if eps is None or eps <= 0 or growth is None:
        return ValuationMethodResult(method="peg", data_available=False)
    if growth < 0.05 or growth > 0.40:
        return ValuationMethodResult(
            method="peg",
            data_available=False,
            detail="Earnings growth outside 5–40% band for PEG",
        )
    payout = fundamentals.payout_ratio
    if payout is not None and payout > 0.8:
        return ValuationMethodResult(
            method="peg",
            data_available=False,
            detail="Payout ratio >80% — dividend growth unsustainable for PEG",
        )
    implied_pe = growth * 100
    if implied_pe > 40:
        return ValuationMethodResult(
            method="peg",
            data_available=False,
            detail=f"PEG=1 implies P/E {implied_pe:.0f}× — capped above 40×",
        )
    peg_fair = eps * implied_pe
    return ValuationMethodResult(
        method="peg",
        fair_value=round(peg_fair, 2),
        detail=f"PEG=1 fair @ {growth * 100:.1f}% growth (TTM EPS × {implied_pe:.0f}×)",
        data_available=True,
        reliable_for_composite=True,
    )


def _enterprise_value(fundamentals: FundamentalsSnapshot) -> float | None:
    if fundamentals.enterprise_value and fundamentals.enterprise_value > 0:
        return fundamentals.enterprise_value
    mcap = fundamentals.market_cap
    if mcap is None or mcap <= 0:
        return None
    debt = fundamentals.total_debt or 0
    cash = fundamentals.total_cash or 0
    return mcap + debt - cash


def _ev_ebitda_method(
    fundamentals: FundamentalsSnapshot,
    price: float | None,
) -> ValuationMethodResult:
    if not _monetary_ok_for_valuation(fundamentals):
        return ValuationMethodResult(
            method="ev_ebitda",
            data_available=False,
            detail="EV/EBITDA skipped — reporting currency not aligned with quote currency",
        )
    ebitda = fundamentals.ebitda
    ev = _enterprise_value(fundamentals)
    mcap = fundamentals.market_cap
    if ebitda is None or ebitda <= 0 or ev is None or ev <= 0 or mcap is None or price is None:
        return ValuationMethodResult(method="ev_ebitda", data_available=False)
    current_mult = ev / ebitda
    if current_mult <= 0:
        return ValuationMethodResult(method="ev_ebitda", data_available=False)
    sector = fundamentals.sector or ""
    target_mult = _sector_multiple(sector, "ev_ebitda")
    if target_mult is None:
        return ValuationMethodResult(
            method="ev_ebitda",
            data_available=False,
            detail="No sector EV/EBITDA prior",
        )
    target_ev = ebitda * target_mult
    net_debt = ev - mcap
    target_mcap = target_ev - net_debt
    if target_mcap <= 0:
        return ValuationMethodResult(
            method="ev_ebitda",
            data_available=False,
            detail="Target EV implies negative equity value",
        )
    fair = price * (target_mcap / mcap)
    return ValuationMethodResult(
        method="ev_ebitda",
        fair_value=round(fair, 2),
        detail=(
            f"EV/EBITDA re-rate (current {current_mult:.1f}× → {target_mult:.1f}×, "
            f"debt-aware)"
        ),
        data_available=True,
        reliable_for_composite=True,
    )


def _pb_method(
    fundamentals: FundamentalsSnapshot,
    price: float | None,
) -> ValuationMethodResult:
    pb = fundamentals.price_to_book
    if pb is None or pb <= 0 or price is None or price <= 0:
        return ValuationMethodResult(method="price_to_book", data_available=False)
    priors = _load_sector_pe_priors()
    sector = fundamentals.sector or ""
    target_pb = priors.get(sector, 1.2)
    if _is_bank_or_reit(fundamentals):
        target_pb = min(target_pb, 1.5)
    fair = price * (target_pb / pb)
    return ValuationMethodResult(
        method="price_to_book",
        fair_value=round(fair, 2),
        detail=f"P/B re-rate toward {target_pb:.1f}× (current {pb:.2f}×)",
        data_available=True,
        reliable_for_composite=_is_bank_or_reit(fundamentals),
    )


def _sector_pe_prior_method(fundamentals: FundamentalsSnapshot) -> ValuationMethodResult:
    eps = _eps_for_valuation(fundamentals)
    priors = _load_sector_pe_priors()
    sector = fundamentals.sector or ""
    prior_pe = priors.get(sector)
    bench = fundamentals.benchmark
    pe_points = 0
    if bench and bench.median_pe_3y:
        pe_points = 1
    if prior_pe is None or eps is None or eps <= 0:
        return ValuationMethodResult(method="sector_pe_prior", data_available=False)
    if pe_points >= 2:
        return ValuationMethodResult(
            method="sector_pe_prior",
            data_available=False,
            detail="Skipped — sufficient issuer P/E history",
        )
    fair = eps * prior_pe
    return ValuationMethodResult(
        method="sector_pe_prior",
        fair_value=round(fair, 2),
        detail=f"TTM EPS × sector prior P/E ({prior_pe:.1f} for {sector})",
        data_available=True,
        reliable_for_composite=not _historical_pe_is_reliable(fundamentals),
    )


