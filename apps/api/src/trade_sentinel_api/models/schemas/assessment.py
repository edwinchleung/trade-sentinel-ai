from typing import Literal

from pydantic import BaseModel, Field

from trade_sentinel_api.models.schemas.common import TrendLabel

FundamentalQualityLabel = Literal["strong", "adequate", "weak", "unavailable"]


FundamentalOverallLabel = Literal["favorable", "neutral", "caution", "unavailable"]


RealityCheckBias = Literal["constructive", "cautious", "mixed", "unavailable"]


class FundamentalAssessment(BaseModel):
    quality_label: FundamentalQualityLabel | None = None
    growth_label: TrendLabel | None = None
    balance_sheet_label: TrendLabel | None = None
    valuation_context_label: Literal["rich", "fair", "cheap", "unavailable"] | None = None
    overall_label: FundamentalOverallLabel | None = None
    summary: str | None = None
    signals: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None


class RealityCheck(BaseModel):
    overall_bias: RealityCheckBias | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    headline: str | None = None
    key_catalysts: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    invalidation_triggers: list[str] = Field(default_factory=list)
    tensions: list[str] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None

