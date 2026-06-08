"""DCF fair-value methods."""

from trade_sentinel_api.services.valuation.methods import common as _c
from trade_sentinel_api.services.valuation.methods.composite import _normalize_growth_rate

globals().update({k: v for k, v in vars(_c).items() if not k.startswith("__")})

def _dcf_enterprise_value(
    fcf: float,
    start_growth: float,
    terminal_growth: float,
    discount: float,
    *,
    years: int = _DCF_PROJECTION_YEARS,
    fade: bool = True,
) -> tuple[float, float, float] | None:
    if discount <= terminal_growth:
        return None
    pv_explicit = 0.0
    f = fcf
    for year in range(1, years + 1):
        g = (
            _fade_growth_year(start_growth, terminal_growth, year, years)
            if fade
            else start_growth
        )
        f *= 1 + g
        pv_explicit += f / ((1 + discount) ** year)
    terminal_val = f * (1 + terminal_growth) / (discount - terminal_growth)
    pv_terminal = terminal_val / ((1 + discount) ** years)
    return pv_explicit + pv_terminal, pv_explicit, pv_terminal


def _dcf_shares(
    fundamentals: FundamentalsSnapshot,
    price: float | None,
) -> float | None:
    shares = fundamentals.shares_outstanding
    if shares and shares > 0:
        return shares
    if fundamentals.market_cap and price and price > 0:
        implied = fundamentals.market_cap / price
        return implied if implied > 0 else None
    return None


def _dcf_per_share(
    fcf: float,
    start_growth: float,
    terminal_growth: float,
    discount: float,
    fundamentals: FundamentalsSnapshot,
    price: float | None,
    *,
    fade: bool = True,
) -> tuple[float | None, float | None]:
    ev_result = _dcf_enterprise_value(
        fcf, start_growth, terminal_growth, discount, fade=fade
    )
    if ev_result is None:
        return None, None
    total_pv, _, pv_terminal = ev_result
    shares = _dcf_shares(fundamentals, price)
    if not shares:
        return None, None
    tv_pct = round(pv_terminal / total_pv * 100, 2) if total_pv > 0 else None
    return round(total_pv / shares, 2), tv_pct


def _solve_implied_start_growth(
    fcf: float,
    target_price: float,
    terminal_growth: float,
    discount: float,
    growth_cap: float,
    fundamentals: FundamentalsSnapshot,
    price: float | None,
) -> float | None:
    if target_price <= 0 or growth_cap <= 0:
        return None
    lo, hi = 0.0, growth_cap
    best_g: float | None = None
    for _ in range(48):
        mid = (lo + hi) / 2
        fair, _ = _dcf_per_share(
            fcf, mid, terminal_growth, discount, fundamentals, price, fade=True
        )
        if fair is None:
            return None
        best_g = mid
        if abs(fair - target_price) < 0.05:
            return round(mid, 4)
        if fair > target_price:
            hi = mid
        else:
            lo = mid
    return round(best_g, 4) if best_g is not None else None


def _fetch_risk_free_yield_sync() -> float | None:
    cached = get_cached("valuation", "risk_free_yield")
    if isinstance(cached, dict) and cached.get("yield") is not None:
        return float(cached["yield"])

    yield_val: float | None = None
    for symbol in ("^TNX", "^IRX"):
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if hist is not None and not hist.empty:
                y = float(hist["Close"].iloc[-1])
                if y > 0:
                    yield_val = y / 100 if y > 1 else y
                    break
        except Exception as exc:
            logger.debug("Risk-free fetch failed for %s: %s", symbol, exc)

    if yield_val is not None:
        set_cached_ttl("valuation", "risk_free_yield", {"yield": yield_val}, 14400)
    return yield_val


def derive_dcf_assumptions(fundamentals: FundamentalsSnapshot) -> dict[str, float | str]:
    bench = fundamentals.benchmark
    rev_g = _normalize_growth_rate(fundamentals.revenue_growth)
    earn_g = _normalize_growth_rate(fundamentals.earnings_growth)
    cagr = bench.revenue_cagr_3y / 100 if bench and bench.revenue_cagr_3y is not None else None

    growth_candidates = sorted(g for g in (cagr, rev_g, earn_g) if g is not None and g > 0)
    if growth_candidates:
        mid = growth_candidates[len(growth_candidates) // 2]
        if rev_g and earn_g and rev_g > 0.15 and earn_g > 0.15:
            anchor = min(_GROWTH_CAP_CEILING, max(0.12, mid))
        else:
            anchor = min(0.12, mid)
    else:
        anchor = 0.05
    cap_ceiling = _GROWTH_CAP_CEILING
    if fundamentals.sector and "utilit" in fundamentals.sector.lower():
        cap_ceiling = 0.08
    growth_cap = round(
        min(cap_ceiling, max(_GROWTH_CAP_FLOOR, anchor * 1.1)),
        4,
    )

    terminal_growth = round(
        min(
            _TERMINAL_GROWTH_MAX,
            max(_TERMINAL_GROWTH_MIN, min(growth_cap * 0.35, anchor * 0.5, 0.025)),
        ),
        4,
    )

    risk_free = _fetch_risk_free_yield_sync() or _DEFAULT_RISK_FREE
    discount = round(
        min(_DISCOUNT_MAX, max(_DISCOUNT_MIN, risk_free + _EQUITY_RISK_PREMIUM)),
        4,
    )

    return {
        "discount_rate": discount,
        "terminal_growth": terminal_growth,
        "projection_years": _DCF_PROJECTION_YEARS,
        "growth_cap": growth_cap,
        "risk_free_yield": round(risk_free, 4),
        "equity_risk_premium": _EQUITY_RISK_PREMIUM,
        "derived_from": "fundamentals_and_tnx",
    }


def _build_dcf(
    fundamentals: FundamentalsSnapshot,
    price: float | None,
) -> tuple[
    float | None,
    dict | None,
    list[DcfSensitivityPoint],
    list[str],
    bool,
    float | None,
]:
    gaps: list[str] = []
    fcf, fcf_gaps = _latest_ttm_fcf(fundamentals)
    gaps.extend(fcf_gaps)
    if fcf is None or fcf <= 0:
        return None, None, [], gaps, False, None

    dcf_reliable = not _fcf_cv_excludes_composite(fundamentals)
    if not dcf_reliable:
        gaps.append("dcf_fcf_volatile")

    params = derive_dcf_assumptions(fundamentals)
    discount = float(params["discount_rate"])
    terminal_growth = float(params["terminal_growth"])
    growth_cap = float(params["growth_cap"])

    growth_candidates = sorted(
        g
        for g in (
            _normalize_growth_rate(fundamentals.revenue_growth),
            _normalize_growth_rate(fundamentals.earnings_growth),
            fundamentals.benchmark.revenue_cagr_3y / 100
            if fundamentals.benchmark and fundamentals.benchmark.revenue_cagr_3y
            else None,
        )
        if g is not None and g > 0
    )
    base_growth = growth_candidates[len(growth_candidates) // 2] if growth_candidates else 0.05
    base_growth = min(max(base_growth, 0.0), growth_cap)

    fair, tv_pct = _dcf_per_share(
        fcf, base_growth, terminal_growth, discount, fundamentals, price, fade=True
    )
    implied_growth: float | None = None
    if price and price > 0:
        implied_growth = _solve_implied_start_growth(
            fcf, price, terminal_growth, discount, growth_cap, fundamentals, price
        )

    assumptions: dict[str, float | str | bool] = {
        **params,
        "growth_rate": round(base_growth, 4),
        "growth_curve": "linear_fade_to_terminal",
        "base_fcf": fcf,
        "terminal_value_pct_of_ev": tv_pct if tv_pct is not None else 0.0,
        "trading_currency": fundamentals.trading_currency or "",
        "financial_currency": fundamentals.financial_currency or "",
        "monetary_values_normalized": fundamentals.monetary_values_normalized,
    }
    if implied_growth is not None:
        assumptions["implied_start_growth_at_price"] = round(implied_growth, 4)
        assumptions["model_vs_market_growth_gap"] = round(base_growth - implied_growth, 4)
    if fundamentals.fx_rate_financial_to_trading is not None:
        assumptions["fx_rate_financial_to_trading"] = fundamentals.fx_rate_financial_to_trading

    def _scenario_fair(
        start_g: float,
        rate: float,
        terminal: float,
    ) -> float | None:
        v, _ = _dcf_per_share(
            fcf, start_g, terminal, rate, fundamentals, price, fade=True
        )
        return v

    sensitivity: list[DcfSensitivityPoint] = []
    scenarios = [
        ("bear", max(base_growth - 0.03, 0), discount + 0.02, max(_TERMINAL_GROWTH_MIN, terminal_growth - 0.005)),
        ("base", base_growth, discount, terminal_growth),
        ("bull", min(base_growth + 0.02, growth_cap), max(discount - 0.02, 0.06), min(_TERMINAL_GROWTH_MAX, terminal_growth + 0.005)),
        ("growth-2%", max(base_growth - 0.02, 0), discount, terminal_growth),
        ("growth+2%", min(base_growth + 0.02, growth_cap), discount, terminal_growth),
        (
            "terminal+0.5%",
            base_growth,
            discount,
            min(_TERMINAL_GROWTH_MAX, terminal_growth + 0.005),
        ),
        (
            "terminal-0.5%",
            base_growth,
            discount,
            max(_TERMINAL_GROWTH_MIN, terminal_growth - 0.005),
        ),
        ("discount+2%", base_growth, discount + 0.02, terminal_growth),
        ("discount-2%", base_growth, max(discount - 0.02, 0.06), terminal_growth),
    ]
    for label, g, r, tg in scenarios:
        v = _scenario_fair(g, r, tg)
        if v is not None:
            sensitivity.append(DcfSensitivityPoint(label=label, fair_value=round(v, 2)))

    if fair is None:
        gaps.append("dcf_invalid_assumptions")
    return (fair, assumptions, sensitivity, gaps, dcf_reliable, implied_growth)
