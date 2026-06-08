from typing import Literal

from pydantic import BaseModel, Field

from trade_sentinel_api.models.schemas.common import Warning


class RiskEvaluateRequest(BaseModel):
    ticker: str
    direction: Literal["long", "short"] = "long"
    quantity: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    account_size: float = Field(gt=0)
    instrument_type: Literal["stock", "option", "leveraged_etf"] = "stock"
    holding_days: int | None = None


class RiskEvaluateResponse(BaseModel):
    ticker: str
    position_value: float
    portfolio_pct: float
    exceeds_risk_limit: bool
    risk_limit_pct: float = 2.0
    suggested_stop_loss: float | None = None
    suggested_position_size: float | None = None
    atr: float | None = None
    warnings: list[Warning] = Field(default_factory=list)
    derivative_note: str | None = None

