from pydantic import BaseModel, Field


class Watchlist(BaseModel):
    name: str = "default"
    tickers: list[str] = Field(default_factory=list)


class WatchlistUpdate(BaseModel):
    tickers: list[str] = Field(default_factory=list)


class WatchlistPatch(BaseModel):
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)

