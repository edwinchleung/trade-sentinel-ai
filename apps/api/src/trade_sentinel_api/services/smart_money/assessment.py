"""Composite Smart Money assessment per ticker."""

from __future__ import annotations

from trade_sentinel_api.models.schemas import (
    DarkPoolSummary,
    FundHoldingsSnapshot,
    InsiderSummary,
    MicrostructureSnapshot,
    OptionsFlowFlag,
    SmartMoneyAssessment,
    SmartMoneyLayerScore,
    VolumeFootprint,
)
from trade_sentinel_api.services.calendar_adjustments import get_calendar_context
from trade_sentinel_api.services.microstructure_adjustments import microstructure_adjustment


def build_smart_money_assessment(
    *,
    ticker: str,
    insider_summary: InsiderSummary | None = None,
    options_flow: OptionsFlowFlag | None = None,
    volume_footprint: VolumeFootprint | None = None,
    institutional_conviction: bool = False,
    activist_alert: bool = False,
    crowding_risk: str | None = None,
    fund_holdings: FundHoldingsSnapshot | None = None,
    dark_pool: DarkPoolSummary | None = None,
    microstructure: MicrostructureSnapshot | None = None,
) -> SmartMoneyAssessment:
    calendar = get_calendar_context()
    ms_adj = microstructure_adjustment(
        microstructure.gex if microstructure else None,
        microstructure.dix if microstructure else None,
    )
    layers: list[SmartMoneyLayerScore] = []
    score = 0.0
    max_score = 0.0

    if insider_summary and insider_summary.data_available:
        w = 25.0
        max_score += w
        layer_score = 0.0
        if insider_summary.sentiment == "accumulation":
            layer_score = w * 0.8
        elif insider_summary.sentiment == "distribution":
            layer_score = w * 0.2
        else:
            layer_score = w * 0.5
        if insider_summary.cluster_buying:
            layer_score = min(w, layer_score + 10)
        if insider_summary.new_insiders_90d:
            layer_score = min(w, layer_score + 5)
        layers.append(
            SmartMoneyLayerScore(
                layer="insider_open_market",
                label="Open-market insiders",
                score=round(layer_score, 1),
                max_score=w,
                stance=insider_summary.sentiment,
                detail=insider_summary.analysis_bullets[0] if insider_summary.analysis_bullets else None,
            )
        )
        score += layer_score

    if options_flow and (
        options_flow.unusual
        or options_flow.unusual_contracts
        or options_flow.put_call_ratio is not None
    ):
        w = 20.0
        max_score += w
        if options_flow.high_conviction or options_flow.institutional_grade:
            layer_score = w * 0.95
            stance = "high_conviction"
        elif options_flow.unusual:
            layer_score = w * 0.7
            stance = "unusual"
        else:
            layer_score = w * 0.4
            stance = "neutral"
        if options_flow.sweep_candidates:
            layer_score = min(w, layer_score + 5)
        if options_flow.max_vol_oi_ratio and options_flow.max_vol_oi_ratio >= 5:
            layer_score = min(w, layer_score + 5)
        detail = options_flow.unusual_reason
        if options_flow.conviction_band:
            detail = f"{detail or 'Options activity'}; DTE band: {options_flow.conviction_band}"
        if options_flow.data_source == "polygon_ticks":
            detail = f"{detail or 'Options'}; tick-level Polygon data"
        layers.append(
            SmartMoneyLayerScore(
                layer="options_flow",
                label="Options activity",
                score=round(layer_score, 1),
                max_score=w,
                stance=stance,
                detail=detail,
            )
        )
        score += layer_score

    if volume_footprint and volume_footprint.data_available:
        w = 15.0
        max_score += w
        layer_score = w * 0.5
        if volume_footprint.stance == "accumulation":
            layer_score = w * 0.85
        elif volume_footprint.stance == "distribution":
            layer_score = w * 0.2
        layers.append(
            SmartMoneyLayerScore(
                layer="volume_footprint",
                label="Volume footprint",
                score=round(layer_score, 1),
                max_score=w,
                stance=volume_footprint.stance,
                detail=volume_footprint.analysis_bullets[0] if volume_footprint.analysis_bullets else None,
            )
        )
        score += layer_score

    if institutional_conviction:
        w = 15.0
        max_score += w
        detail = "Multiple institutional filers hold/increased position."
        if crowding_risk == "high":
            detail += " High 13F crowding risk (concentrated ownership)."
        layers.append(
            SmartMoneyLayerScore(
                layer="institutional_13f",
                label="Institutional 13F",
                score=w,
                max_score=w,
                stance="conviction",
                detail=detail,
            )
        )
        score += w

    if activist_alert:
        w = 10.0
        max_score += w
        layers.append(
            SmartMoneyLayerScore(
                layer="activist_13d",
                label="Activist stake",
                score=w,
                max_score=w,
                stance="alert",
                detail="Recent Schedule 13D filing.",
            )
        )
        score += w

    if fund_holdings and fund_holdings.data_available:
        w = 5.0
        max_score += w
        layers.append(
            SmartMoneyLayerScore(
                layer="fund_holdings",
                label="Fund holdings (N-PORT)",
                score=w * 0.7,
                max_score=w,
                stance="info",
                detail=f"Equity {fund_holdings.equity_pct}% / FI {fund_holdings.fixed_income_pct}%",
            )
        )
        score += w * 0.7

    if crowding_risk == "high":
        w = 5.0
        max_score += w
        layers.append(
            SmartMoneyLayerScore(
                layer="institutional_crowding",
                label="Ownership crowding",
                score=w * 0.3,
                max_score=w,
                stance="high_risk",
                detail="HHI indicates concentrated institutional ownership.",
            )
        )
        score += w * 0.3

    if dark_pool and dark_pool.data_available and dark_pool.bullish_signature_count:
        w = 5.0
        max_score += w
        layers.append(
            SmartMoneyLayerScore(
                layer="dark_pool",
                label="Dark pool / off-exchange",
                score=w * 0.8,
                max_score=w,
                stance="accumulation",
                detail=dark_pool.message or f"{dark_pool.print_count} print(s); source={dark_pool.data_source}",
            )
        )
        score += w * 0.8

    multiplier = calendar.conviction_multiplier * ms_adj.conviction_multiplier
    score *= multiplier
    notes = list(calendar.notes or [])
    if ms_adj.notes:
        notes.extend(ms_adj.notes)

    conviction_pct = round(score / max_score * 100, 1) if max_score > 0 else None
    if conviction_pct is not None:
        if conviction_pct >= 70:
            headline = "High smart-money conviction"
        elif conviction_pct >= 45:
            headline = "Mixed smart-money signals"
        else:
            headline = "Low smart-money conviction"
    else:
        headline = "Insufficient smart-money data"

    return SmartMoneyAssessment(
        ticker=ticker,
        conviction_pct=conviction_pct,
        headline=headline,
        layers=layers,
        calendar_notes=notes or [],
        data_available=len(layers) > 0,
    )
