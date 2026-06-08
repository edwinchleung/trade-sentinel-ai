from datetime import datetime

from pydantic import BaseModel, Field


class TradeJournalEntry(BaseModel):
    id: str | None = None
    ticker: str
    direction: str
    quantity: float
    entry_price: float
    account_size: float
    instrument_type: str
    ai_warnings: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class TradeJournalCreate(BaseModel):
    ticker: str
    direction: str
    quantity: float
    entry_price: float
    account_size: float
    instrument_type: str
    ai_warnings: list[str] = Field(default_factory=list)

