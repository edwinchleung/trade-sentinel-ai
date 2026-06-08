"""Composite band and summary assembly."""

from trade_sentinel_api.models.schemas import ValuationAssessment
from trade_sentinel_api.services.valuation.methods import common as _c

globals().update({k: v for k, v in vars(_c).items() if not k.startswith("__")})

def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * pct / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _trimmed_anchors(anchors: list[float]) -> list[float]:
    if not anchors:
        return []
    s = sorted(anchors)
    if len(s) >= 4:
        return s[1:-1]
    return s


def _headline_composite_band(anchors: list[float]) -> tuple[float | None, float | None, float | None]:
    """Trimmed median + IQR from composite-eligible anchors only."""
    trimmed = _trimmed_anchors(anchors)
    if not trimmed:
        return None, None, None

    mid = trimmed[len(trimmed) // 2]
    low = _percentile(trimmed, 25)
    high = _percentile(trimmed, 75)
    return round(low, 2), round(mid, 2), round(high, 2)


def _stress_composite_band(anchors: list[float]) -> tuple[float | None, float | None]:
    """P10/P90 stress range on trimmed composite-eligible anchors."""
    trimmed = _trimmed_anchors(anchors)
    if len(trimmed) < 2:
        return None, None
    return round(_percentile(trimmed, 10), 2), round(_percentile(trimmed, 90), 2)


def _weighted_composite_band(
    weighted: list[tuple[str, float]],
) -> tuple[float | None, float | None, float | None]:
    if not weighted:
        return None, None, None
    total_w = sum(_METHOD_WEIGHTS.get(k, 0.1) for k, _ in weighted)
    if total_w <= 0:
        return None, None, None
    mid = sum(_METHOD_WEIGHTS.get(k, 0.1) * v for k, v in weighted) / total_w
    vals = [v for _, v in weighted]
    low = min(vals)
    high = max(vals)
    return round(low, 2), round(mid, 2), round(high, 2)


def build_valuation_summary(assessment: ValuationAssessment) -> dict:
    drivers = list(assessment.composite_drivers)
    exclusions = list(assessment.reliability_notes)
    for m in assessment.methods:
        if m.data_available and not m.reliable_for_composite and m.detail:
            exclusions.append(f"{m.method}: {m.detail}")
    spread_note = None
    if assessment.method_spread_pct is not None and assessment.method_spread_pct > 150:
        spread_note = (
            f"Methods span {assessment.method_spread_pct:.0f}% — treat band as directional only."
        )
    premium_note = None
    if assessment.mos_pct is not None:
        premium_note = (
            f"Price is {abs(assessment.mos_pct):.1f}% "
            f"{'above' if assessment.mos_pct > 0 else 'below'} model fair mid (premium vs mid)."
        )
    mos_note = None
    if assessment.margin_of_safety_met is not None and assessment.mos_buy_threshold_pct is not None:
        thresh = assessment.mos_buy_threshold_pct
        if assessment.margin_of_safety_met:
            mos_note = f"Price meets {thresh:.0f}% margin-of-safety vs fair mid."
        else:
            mos_note = (
                f"Price does not meet {thresh:.0f}% margin-of-safety "
                f"(Graham-style discount below fair mid)."
            )

    return {
        "fair_value_mid": assessment.fair_value_mid,
        "fair_value_low": assessment.fair_value_low,
        "fair_value_high": assessment.fair_value_high,
        "fair_value_stress_low": assessment.fair_value_stress_low,
        "fair_value_stress_high": assessment.fair_value_stress_high,
        "mos_pct": assessment.mos_pct,
        "mos_label": assessment.mos_label,
        "premium_vs_mid_note": premium_note,
        "margin_of_safety_met": assessment.margin_of_safety_met,
        "mos_buy_threshold_pct": assessment.mos_buy_threshold_pct,
        "margin_of_safety_note": mos_note,
        "dcf_implied_growth_at_price": assessment.dcf_implied_growth_at_price,
        "confidence": assessment.confidence,
        "composite_mode": assessment.composite_mode,
        "drivers": drivers[:2],
        "exclusions": exclusions[:5],
        "spread_note": spread_note,
        "method_spread_pct": assessment.method_spread_pct,
        "data_gaps": assessment.data_gaps,
    }


def _premium_vs_mid_pct(price: float, fair_mid: float) -> float:
    """Positive = price above fair mid (premium)."""
    return round((price - fair_mid) / fair_mid * 100, 2)


def _mos_label(
    premium_pct: float | None,
    sector: str | None = None,
) -> Literal["undervalued", "fair", "overvalued"] | None:
    if premium_pct is None:
        return None
    over, under = _mos_thresholds(sector)
    if premium_pct < under:
        return "undervalued"
    if premium_pct > over:
        return "overvalued"
    return "fair"


def _method_spread_ratio(anchors: list[float]) -> tuple[float | None, float | None]:
    """Return (max/min ratio, spread as % of low)."""
    if len(anchors) < 2:
        return None, None
    lo, hi = min(anchors), max(anchors)
    if lo <= 0:
        return None, None
    ratio = hi / lo
    return round(ratio, 2), round((hi - lo) / lo * 100, 2)


def _confidence(
    composite_count: int,
    spread_ratio: float | None,
) -> Literal["high", "medium", "low"]:
    if composite_count < 2:
        return "low"
    if spread_ratio is not None and spread_ratio > _METHOD_SPREAD_LOW_CONFIDENCE:
        return "low"
    if composite_count >= 3 and (
        spread_ratio is None or spread_ratio <= _METHOD_SPREAD_HIGH_CONFIDENCE
    ):
        return "high"
    return "medium"


def _normalize_growth_rate(val: float | None) -> float | None:
    if val is None:
        return None
    if abs(val) > 1.5:
        return val / 100
    return val


