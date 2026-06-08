"""Deterministic Pre-Trade Reality Check synthesis."""

from __future__ import annotations

from trade_sentinel_api.models.schemas import (
    FundamentalAssessment,
    NewsDigest,
    RealityCheck,
    TechnicalAssessment,
    ValuationAssessment,
    Warning,
)


def build_reality_check(
    *,
    valuation: ValuationAssessment | None,
    technical_assessment: TechnicalAssessment | None,
    fundamental_assessment: FundamentalAssessment | None,
    news_digest: NewsDigest | None,
    warnings: list[Warning],
    forward_watch: list[str] | None = None,
) -> RealityCheck:
    if not any(
        (
            valuation and valuation.data_available,
            technical_assessment and technical_assessment.data_available,
            fundamental_assessment and fundamental_assessment.data_available,
        )
    ):
        return RealityCheck(
            data_available=False,
            message="Insufficient data for reality check.",
        )

    constructive = cautious = 0
    tensions: list[str] = []
    catalysts: list[str] = []
    risks: list[str] = []
    invalidations: list[str] = []

    if valuation and valuation.data_available and not valuation.is_fund:
        if valuation.mos_label == "undervalued":
            constructive += 1
        elif valuation.mos_label == "overvalued":
            cautious += 1
        if valuation.confidence == "low":
            risks.append("Fair-value methods disagree — treat MOS band as low confidence.")
        if valuation.reliability_notes:
            risks.extend(valuation.reliability_notes[:1])

    if technical_assessment and technical_assessment.data_available:
        ta = technical_assessment
        if ta.short_term_trend == "bullish":
            constructive += 1
        elif ta.short_term_trend == "bearish":
            cautious += 1
        if ta.mid_term_trend == "bearish" and ta.short_term_trend == "bullish":
            tensions.append("Short-term bounce vs bearish mid-term trend.")
        if ta.support_level is not None:
            invalidations.append(f"Break below support near ${ta.support_level:.2f} weakens the base case.")
        if ta.resistance_level is not None:
            catalysts.append(f"Clearing resistance near ${ta.resistance_level:.2f} would improve momentum.")

    if fundamental_assessment and fundamental_assessment.data_available:
        fa = fundamental_assessment
        if fa.overall_label == "favorable":
            constructive += 2
        elif fa.overall_label == "caution":
            cautious += 2
        for h in fa.highlights[:2]:
            if h not in catalysts:
                catalysts.append(h)

    if news_digest and news_digest.data_available:
        if news_digest.overall_sentiment == "bullish":
            constructive += 1
        elif news_digest.overall_sentiment == "bearish":
            cautious += 1
        if news_digest.summary_line:
            catalysts.append(news_digest.summary_line)

    if valuation and valuation.data_available and technical_assessment and technical_assessment.data_available:
        if valuation.mos_label == "undervalued" and technical_assessment.trend_label == "bearish":
            tensions.append("Model undervaluation vs bearish technical trend — value may need time.")
        elif valuation.mos_label == "overvalued" and technical_assessment.trend_label == "bullish":
            tensions.append("Rich vs model band but bullish tape — momentum may run ahead of fundamentals.")

    for w in warnings:
        sev = w.severity.value if hasattr(w.severity, "value") else str(w.severity)
        if sev in ("high", "medium") and len(risks) < 3:
            risks.append(w.message)

    if forward_watch:
        for item in forward_watch[:2]:
            if item not in catalysts:
                catalysts.append(item)

    if constructive > cautious + 1:
        bias = "constructive"
    elif cautious > constructive + 1:
        bias = "cautious"
    else:
        bias = "mixed"

    conf = "high"
    if tensions or (valuation and valuation.confidence == "low"):
        conf = "medium"
    if len(risks) >= 2 and bias == "mixed":
        conf = "low"

    headline = f"{bias.capitalize()}: "
    if tensions:
        headline += tensions[0]
    elif valuation and valuation.mos_label:
        headline += f"model band reads {valuation.mos_label}"
        if technical_assessment and technical_assessment.horizon_summary:
            headline += f"; {technical_assessment.horizon_summary.lower()}"
    else:
        headline += "mixed signals across value, quality, and tape."

    return RealityCheck(
        overall_bias=bias,
        confidence=conf,
        headline=headline,
        key_catalysts=catalysts[:3],
        key_risks=risks[:3],
        invalidation_triggers=invalidations[:3],
        tensions=tensions[:3],
        data_available=True,
    )
