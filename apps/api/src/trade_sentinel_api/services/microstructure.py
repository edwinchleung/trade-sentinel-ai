"""Microstructure snapshot (GEX + DIX) for market-wide context."""

from __future__ import annotations

from datetime import UTC, datetime

from trade_sentinel_api.models.schemas import (
    DixProxySnapshot,
    GammaExposureSnapshot,
    MicrostructureSnapshot,
)
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.finra_short_volume import compute_dix_proxy
from trade_sentinel_api.services.gex_compute import compute_gex_snapshot
from trade_sentinel_api.services.microstructure_adjustments import microstructure_adjustment
from trade_sentinel_api.services.providers import get_provider


async def fetch_microstructure(symbol: str = "SPY") -> MicrostructureSnapshot:
    cache_key = f"v1:{symbol.upper()}"
    cached = get_cached("smart_money_micro", cache_key)
    if cached:
        return MicrostructureSnapshot(**cached)

    sym = symbol.upper()
    gex: GammaExposureSnapshot | None = None
    dix: DixProxySnapshot | None = None

    gamma_provider = get_provider("gamma")
    if getattr(gamma_provider, "is_available", lambda: False)():
        if gamma_provider.name == "squeezemetrics":
            gex_result = gamma_provider.fetch_gex(sym)  # type: ignore[attr-defined]
            if gex_result.data_available and isinstance(gex_result.payload, dict):
                net = gex_result.payload.get("gex") or gex_result.payload.get("net_gex")
                regime = "positive" if net and float(net) > 0 else "negative"
                gex = GammaExposureSnapshot(
                    symbol=sym,
                    as_of=datetime.now(UTC),
                    net_gex_usd=float(net) if net is not None else None,
                    regime=regime,  # type: ignore[arg-type]
                    data_source="squeezemetrics",
                    data_available=True,
                )
            dix_result = gamma_provider.fetch_dix(sym)  # type: ignore[attr-defined]
            if dix_result.data_available and isinstance(dix_result.payload, dict):
                ratio = dix_result.payload.get("dix") or dix_result.payload.get("ratio")
                dix = DixProxySnapshot(
                    ticker=sym,
                    as_of=datetime.now(UTC),
                    short_volume_ratio=float(ratio) * 100 if ratio and float(ratio) < 1 else float(ratio or 0),
                    elevated_dark_accumulation=bool(ratio and float(ratio) >= 0.45),
                    data_source="squeezemetrics",
                    data_available=True,
                )
        else:
            gex_result = gamma_provider.fetch_gex(sym)  # type: ignore[attr-defined]
            if gex_result.data_available and isinstance(gex_result.payload, GammaExposureSnapshot):
                gex = gex_result.payload

    if gex is None:
        gex = compute_gex_snapshot(sym)
    if dix is None:
        dix = compute_dix_proxy(sym)

    adj = microstructure_adjustment(gex, dix)
    snap = MicrostructureSnapshot(
        as_of=datetime.now(UTC),
        gex=gex,
        dix=dix,
        conviction_multiplier=adj.conviction_multiplier,
        notes=adj.notes or [],
    )
    set_cached_ttl("smart_money_micro", cache_key, snap.model_dump(mode="json"), 3600)
    return snap
