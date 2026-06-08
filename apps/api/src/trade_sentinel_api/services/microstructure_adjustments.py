"""Microstructure conviction adjustments from GEX/DIX."""

from __future__ import annotations

from dataclasses import dataclass

from trade_sentinel_api.models.schemas import DixProxySnapshot, GammaExposureSnapshot


@dataclass
class MicrostructureAdjustment:
    conviction_multiplier: float = 1.0
    notes: list[str] | None = None


def microstructure_adjustment(
    gex: GammaExposureSnapshot | None,
    dix: DixProxySnapshot | None,
) -> MicrostructureAdjustment:
    multiplier = 1.0
    notes: list[str] = []
    if gex and gex.data_available and gex.regime == "negative":
        multiplier = min(multiplier, 0.9)
        notes.append("Negative GEX regime — elevated volatility risk.")
    if dix and dix.elevated_dark_accumulation:
        notes.append("Elevated FINRA short-volume ratio (DIX proxy) — possible dark accumulation.")
    return MicrostructureAdjustment(conviction_multiplier=multiplier, notes=notes or None)
