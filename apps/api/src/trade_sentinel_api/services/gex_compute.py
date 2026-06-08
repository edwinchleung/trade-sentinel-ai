"""Computed gamma exposure from options open interest."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import yfinance as yf

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import GammaExposureSnapshot
from trade_sentinel_api.services.polygon_client import fetch_options_snapshot, is_polygon_enabled
from trade_sentinel_api.services.providers.base import ProviderResult


class ComputedGammaProvider:
    name = "computed_gex"

    def is_available(self) -> bool:
        return get_settings().gex_compute_enabled

    def fetch_gex(self, symbol: str) -> ProviderResult:
        snap = compute_gex_snapshot(symbol)
        return ProviderResult(
            data_available=snap.data_available,
            data_source=self.name,
            payload=snap,
        )

    def fetch_dix(self, symbol: str) -> ProviderResult:
        from trade_sentinel_api.services.finra_short_volume import compute_dix_proxy

        snap = compute_dix_proxy(symbol)
        return ProviderResult(
            data_available=snap.data_available,
            data_source=snap.data_source,
            payload=snap,
        )


def _approx_gamma(spot: float, strike: float, t_years: float, iv: float = 0.25) -> float:
    if spot <= 0 or strike <= 0 or t_years <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (0.05 + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    pdf = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
    return pdf / (spot * iv * math.sqrt(t_years))


def compute_gex_snapshot(symbol: str) -> GammaExposureSnapshot:
    sym = symbol.upper()
    spot = _spot_price(sym)
    if spot is None:
        return GammaExposureSnapshot(
            symbol=sym,
            as_of=datetime.now(UTC),
            message="No spot price for GEX compute.",
        )

    net_gex = 0.0
    contracts = _option_contracts(sym)
    for c in contracts:
        strike = float(c.get("strike") or c.get("details", {}).get("strike_price") or 0)
        oi = float(c.get("open_interest") or c.get("day", {}).get("open_interest") or 0)
        cp = (c.get("contract_type") or c.get("details", {}).get("contract_type") or "").lower()
        dte = float(c.get("dte") or 30)
        t = max(dte / 365.0, 1 / 365.0)
        gamma = _approx_gamma(spot, strike, t)
        sign = 1 if cp == "call" else -1
        net_gex += sign * oi * gamma * spot * 100

    regime = "neutral"
    if net_gex > 0:
        regime = "positive"
    elif net_gex < 0:
        regime = "negative"

    return GammaExposureSnapshot(
        symbol=sym,
        as_of=datetime.now(UTC),
        net_gex_usd=round(net_gex, 2),
        regime=regime,  # type: ignore[arg-type]
        data_source="computed",
        data_available=True,
    )


def _spot_price(symbol: str) -> float | None:
    try:
        info = yf.Ticker(symbol).fast_info
        last = getattr(info, "last_price", None) or info.get("lastPrice")
        return float(last) if last else None
    except Exception:
        return None


def _option_contracts(symbol: str) -> list[dict]:
    if is_polygon_enabled():
        snap = fetch_options_snapshot(symbol)
        if snap:
            return snap[:200]
    try:
        t = yf.Ticker(symbol)
        exps = (t.options or [])[:2]
        out: list[dict] = []
        for exp in exps:
            chain = t.option_chain(exp)
            for side, df in (("call", chain.calls), ("put", chain.puts)):
                for _, row in df.head(50).iterrows():
                    out.append(
                        {
                            "strike": row.get("strike"),
                            "open_interest": row.get("openInterest"),
                            "contract_type": side,
                            "dte": 30,
                        }
                    )
        return out
    except Exception:
        return []
