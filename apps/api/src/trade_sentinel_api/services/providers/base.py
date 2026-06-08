"""Vendor provider protocols for smart-money data sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ProviderResult:
    data_available: bool = False
    data_source: str = "none"
    message: str | None = None
    payload: Any = None


@runtime_checkable
class OptionsTickProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def fetch_trades(self, underlying: str, *, limit: int = 500) -> ProviderResult: ...


@runtime_checkable
class GammaExposureProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def fetch_gex(self, symbol: str) -> ProviderResult: ...

    def fetch_dix(self, symbol: str) -> ProviderResult: ...


@runtime_checkable
class DarkPoolProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def fetch_prints(self, ticker: str, *, days: int = 5) -> ProviderResult: ...


@runtime_checkable
class CongressionalTradesProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def fetch_trades(self, *, days: int = 30) -> ProviderResult: ...


@dataclass
class NullProvider:
    name: str = "null"
    kind: str = ""

    def is_available(self) -> bool:
        return False

    def fetch_trades(self, *args: Any, **kwargs: Any) -> ProviderResult:
        return ProviderResult(message=f"No {self.kind} provider configured.")

    def fetch_gex(self, *args: Any, **kwargs: Any) -> ProviderResult:
        return ProviderResult(message=f"No {self.kind} provider configured.")

    def fetch_dix(self, *args: Any, **kwargs: Any) -> ProviderResult:
        return ProviderResult(message=f"No {self.kind} provider configured.")

    def fetch_prints(self, *args: Any, **kwargs: Any) -> ProviderResult:
        return ProviderResult(message=f"No {self.kind} provider configured.")


@dataclass
class SweepCandidate:
    underlying: str
    strike: float
    expiry: str
    side: str
    total_size: float
    trade_count: int
    premium_usd: float
    execution_side: str | None = None
    is_sweep: bool = False


@dataclass
class OptionsTickBundle:
    trades: list[dict[str, Any]] = field(default_factory=list)
    sweeps: list[SweepCandidate] = field(default_factory=list)
    aggressive_call_pct: float | None = None
    aggressive_put_pct: float | None = None
