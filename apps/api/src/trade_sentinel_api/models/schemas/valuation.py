from typing import Literal

from pydantic import BaseModel, Field


class ValuationMethodResult(BaseModel):
    method: str
    fair_value: float | None = None
    detail: str | None = None
    data_available: bool = False
    reliable_for_composite: bool = True


class DcfSensitivityPoint(BaseModel):
    label: str
    fair_value: float | None = None


class FundValuationSnapshot(BaseModel):
    quote_type: str | None = None
    expense_ratio: float | None = None
    total_assets: float | None = None
    nav_price: float | None = None
    premium_discount_pct: float | None = None
    top_holdings_pct: float | None = None
    fair_value_low: float | None = None
    fair_value_mid: float | None = None
    fair_value_high: float | None = None
    message: str | None = None
    data_available: bool = False


class ValuationAssessment(BaseModel):
    current_price: float | None = None
    fair_value_low: float | None = None
    fair_value_mid: float | None = None
    fair_value_high: float | None = None
    fair_value_stress_low: float | None = None
    fair_value_stress_high: float | None = None
    mos_pct: float | None = None
    mos_label: Literal["undervalued", "fair", "overvalued"] | None = None
    method_spread_pct: float | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    methods: list[ValuationMethodResult] = Field(default_factory=list)
    dcf_fair_value: float | None = None
    dcf_implied_growth_at_price: float | None = None
    dcf_assumptions: dict[str, float | str] | None = None
    dcf_sensitivity: list[DcfSensitivityPoint] = Field(default_factory=list)
    margin_of_safety_met: bool | None = None
    mos_buy_threshold_pct: float | None = None
    fund: FundValuationSnapshot | None = None
    is_fund: bool = False
    reliability_notes: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    composite_drivers: list[str] = Field(default_factory=list)
    composite_mode: str | None = None
    data_available: bool = False
    message: str | None = None

