"""Shared screener query parameters."""

from dataclasses import dataclass

from fastapi import Query


@dataclass(frozen=True)
class ScreenerFilters:
    mos_min: float | None = None
    mos_max: float | None = None
    pe_max: float | None = None
    valuation_label: str | None = None
    has_earnings_within_days: int | None = None
    insider_sentiment: str | None = None
    warning_any: str | None = None
    preset: str | None = None


def screener_filters(
    mos_min: float | None = None,
    mos_max: float | None = None,
    pe_max: float | None = None,
    valuation_label: str | None = None,
    has_earnings_within_days: int | None = None,
    insider_sentiment: str | None = None,
    warning_any: str | None = None,
    preset: str | None = None,
) -> ScreenerFilters:
    return ScreenerFilters(
        mos_min=mos_min,
        mos_max=mos_max,
        pe_max=pe_max,
        valuation_label=valuation_label,
        has_earnings_within_days=has_earnings_within_days,
        insider_sentiment=insider_sentiment,
        warning_any=warning_any,
        preset=preset,
    )


def screener_filters_query(
    mos_min: float | None = Query(None),
    mos_max: float | None = Query(None),
    pe_max: float | None = Query(None),
    valuation_label: str | None = Query(None),
    has_earnings_within_days: int | None = Query(None),
    insider_sentiment: str | None = Query(None),
    warning_any: str | None = Query(None),
    preset: str | None = Query(None),
) -> ScreenerFilters:
    return screener_filters(
        mos_min=mos_min,
        mos_max=mos_max,
        pe_max=pe_max,
        valuation_label=valuation_label,
        has_earnings_within_days=has_earnings_within_days,
        insider_sentiment=insider_sentiment,
        warning_any=warning_any,
        preset=preset,
    )
