from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class WarningSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Warning(BaseModel):
    code: str
    message: str
    severity: WarningSeverity


class NewsItem(BaseModel):
    title: str
    url: str | None = None
    published_at: str | None = None
    source: str | None = None
    summary: str | None = None
    sentiment_label: Literal["bullish", "bearish", "neutral"] | None = None
    sentiment_score: float | None = None
    themes: list[str] = Field(default_factory=list)


NewsSentiment = Literal["bullish", "bearish", "mixed", "neutral"]


class NewsDigest(BaseModel):
    overall_sentiment: NewsSentiment | None = None
    summary_line: str | None = None
    top_themes: list[str] = Field(default_factory=list)
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    data_available: bool = False
    message: str | None = None


class MacdSnapshot(BaseModel):
    macd: float | None = None
    signal: float | None = None
    histogram: float | None = None


TrendLabel = Literal["bullish", "bearish", "neutral", "mixed"]


MacdDivergence = Literal["bullish", "bearish", "none"]

