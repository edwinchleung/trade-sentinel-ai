"""Analyst target valuation method."""

from trade_sentinel_api.services.valuation.methods import common as _c

globals().update({k: v for k, v in vars(_c).items() if not k.startswith("__")})

def _analyst_target_stale(upside: float | None) -> bool:
    if upside is None:
        return False
    return upside > _ANALYST_STALE_UPSIDE or upside < _ANALYST_STALE_DOWNSIDE


def _normalize_growth_pct(val: float | None) -> float | None:
    if val is None:
        return None
    g = val / 100 if abs(val) > 1.5 else val
    return g if g > 0 else None


def _median_pe_3y(fundamentals: FundamentalsSnapshot) -> float | None:
    bench = fundamentals.benchmark
    if bench and bench.median_pe_3y is not None:
        return bench.median_pe_3y
    return None


def _historical_pe_is_reliable(fundamentals: FundamentalsSnapshot) -> bool:
    bench = fundamentals.benchmark
    if bench is None:
        return False
    return bench.historical_pe_reliable and bench.median_pe_3y is not None


def _analyst_method(fundamentals: FundamentalsSnapshot) -> ValuationMethodResult:
    target = fundamentals.target_price
    if target is None or target <= 0:
        return ValuationMethodResult(method="analyst_target", data_available=False)
    upside = fundamentals.target_upside_pct
    source = fundamentals.target_source or "consensus"
    detail = f"{source} mean target ${target:.2f}"
    if fundamentals.target_price_low and fundamentals.target_price_high:
        detail += (
            f" (range ${fundamentals.target_price_low:.2f}"
            f"–${fundamentals.target_price_high:.2f})"
        )
    if upside is not None:
        detail += f" ({upside:+.1f}% vs price)"
    stale = _analyst_target_stale(upside)
    if stale:
        detail += " — excluded from headline (stale or outlier vs price)"
    return ValuationMethodResult(
        method="analyst_target",
        fair_value=round(target, 2),
        detail=detail,
        data_available=True,
        reliable_for_composite=not stale,
    )


