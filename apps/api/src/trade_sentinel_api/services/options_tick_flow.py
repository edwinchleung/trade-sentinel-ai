"""Options tick flow orchestration with provider fallback."""

from __future__ import annotations

from trade_sentinel_api.models.schemas import OptionsFlowFlag
from trade_sentinel_api.services.options import analyze_options_flow
from trade_sentinel_api.services.providers import get_provider
from trade_sentinel_api.services.providers.base import OptionsTickBundle


async def enrich_options_flow_with_ticks(
    ticker: str,
    base: OptionsFlowFlag | None = None,
) -> tuple[OptionsFlowFlag, list]:
    flag, warnings = base if base else await analyze_options_flow(ticker)
    provider = get_provider("options_ticks")
    if not getattr(provider, "is_available", lambda: False)():
        return flag, warnings

    result = provider.fetch_trades(ticker)  # type: ignore[attr-defined]
    if not result.data_available or not isinstance(result.payload, OptionsTickBundle):
        return flag, warnings

    bundle: OptionsTickBundle = result.payload
    sweep_dicts = [
        {
            "underlying": s.underlying,
            "strike": s.strike,
            "expiry": s.expiry,
            "side": s.side,
            "total_size": s.total_size,
            "premium_usd": s.premium_usd,
            "is_sweep": s.is_sweep,
        }
        for s in bundle.sweeps
    ]
    updated = flag.model_copy(
        update={
            "data_source": "polygon_ticks",
            "sweep_candidates": sweep_dicts,
            "aggressive_call_pct": bundle.aggressive_call_pct,
            "aggressive_put_pct": bundle.aggressive_put_pct,
            "high_conviction": flag.high_conviction or len(sweep_dicts) > 0,
        }
    )
    return updated, warnings
