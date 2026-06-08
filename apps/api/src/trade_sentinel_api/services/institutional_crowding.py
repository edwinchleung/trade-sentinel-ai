"""Herfindahl-Hirschman Index for 13F ownership concentration."""

from __future__ import annotations

from typing import Literal

CrowdingRisk = Literal["low", "medium", "high"]


def compute_hhi(shares_by_filer: list[float]) -> float | None:
    """HHI = sum of squared market shares (0-1 scale). Returns None if no holdings."""
    positive = [s for s in shares_by_filer if s and s > 0]
    if not positive:
        return None
    total = sum(positive)
    if total <= 0:
        return None
    return sum((s / total) ** 2 for s in positive)


def crowding_risk_from_hhi(hhi: float | None) -> CrowdingRisk | None:
    if hhi is None:
        return None
    if hhi >= 0.35:
        return "high"
    if hhi >= 0.20:
        return "medium"
    return "low"
