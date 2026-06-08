"""Calendar-driven behavioral anomaly flags for smart-money signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass
class CalendarContext:
    window_dressing_risk: bool = False
    tax_loss_season: bool = False
    conviction_multiplier: float = 1.0
    notes: list[str] | None = None


def _quarter_end(d: date) -> date:
    month = ((d.month - 1) // 3 + 1) * 3
    if month == 3:
        return date(d.year, 3, 31)
    if month == 6:
        return date(d.year, 6, 30)
    if month == 9:
        return date(d.year, 9, 30)
    return date(d.year, 12, 31)


def _trading_days_to_quarter_end(d: date) -> int:
    qe = _quarter_end(d)
    if d > qe:
        return 999
    try:
        bdays = pd.bdate_range(d, qe)
        return max(0, len(bdays) - 1)
    except Exception:
        return (qe - d).days


def get_calendar_context(reference: date | None = None) -> CalendarContext:
    """Detect window-dressing and tax-loss season windows."""
    ref = reference or date.today()
    notes: list[str] = []
    multiplier = 1.0

    days_to_qe = _trading_days_to_quarter_end(ref)
    window_dressing = days_to_qe <= 5
    tax_loss = ref.month == 12 and ref.day >= 15

    if window_dressing:
        notes.append("Quarter-end window: institutional window-dressing may distort flows.")
        multiplier = min(multiplier, 0.85)
    if tax_loss:
        notes.append("Tax-loss harvesting season (late December) may inflate selling pressure.")
        multiplier = min(multiplier, 0.85)

    return CalendarContext(
        window_dressing_risk=window_dressing,
        tax_loss_season=tax_loss,
        conviction_multiplier=multiplier,
        notes=notes or None,
    )
