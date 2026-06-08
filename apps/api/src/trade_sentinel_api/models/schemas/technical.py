from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from trade_sentinel_api.models.schemas.common import MacdDivergence, MacdSnapshot, TrendLabel


class TechnicalAssessment(BaseModel):
    current_price: float | None = None
    trend_label: TrendLabel | None = None
    trend_summary: str | None = None
    short_term_trend: TrendLabel | None = None
    mid_term_trend: TrendLabel | None = None
    long_term_trend: TrendLabel | None = None
    horizon_summary: str | None = None
    rsi_14: float | None = None
    macd: MacdSnapshot | None = None
    atr_14: float | None = None
    atr_pct: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    price_vs_sma_20_pct: float | None = None
    price_vs_sma_50_pct: float | None = None
    range_52w_low: float | None = None
    range_52w_high: float | None = None
    range_position_pct: float | None = None
    support_level: float | None = None
    resistance_level: float | None = None
    macd_divergence: MacdDivergence | None = None
    signals: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None


VisualStance = Literal["favorable", "neutral", "caution", "unavailable"]


MetricTone = Literal["positive", "neutral", "negative", "muted"]


class ContextSectionLabel(BaseModel):
    stance: VisualStance
    headline: str


class ContextVisualMetric(BaseModel):
    label: str
    value: str
    tone: MetricTone | None = None


class ContextVisualSparkPoint(BaseModel):
    period: str
    value: float


class ContextVisualSection(BaseModel):
    id: str
    title: str
    stance: VisualStance
    metrics: list[ContextVisualMetric] = Field(default_factory=list)
    sparkline: list[ContextVisualSparkPoint] = Field(default_factory=list)


class ContextVisualPillar(BaseModel):
    id: str
    label: str
    stance: VisualStance


class ContextVisualSnapshot(BaseModel):
    pillars: list[ContextVisualPillar]
    sections: list[ContextVisualSection]


class ContextSummary(BaseModel):
    bullets: list[str] = Field(..., min_length=3, max_length=9)
    section_bullets: dict[str, str] | None = None
    qualitative_analysis: str | None = None
    technical_interpretation: str | None = None
    fundamental_interpretation: str | None = None
    reality_check_narrative: str | None = None
    scenario_bullets: list[str] = Field(default_factory=list)
    section_labels: list[ContextSectionLabel] = Field(default_factory=list)
    model: str
    cached_at: datetime | None = None
    data_gaps: list[str] = Field(default_factory=list)

