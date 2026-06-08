"""Polygon.io options tick provider."""

from __future__ import annotations

from collections import defaultdict

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.providers.base import (
    OptionsTickBundle,
    ProviderResult,
    SweepCandidate,
)

_BASE = "https://api.polygon.io"


class PolygonOptionsTickProvider:
    name = "polygon_ticks"

    def is_available(self) -> bool:
        settings = get_settings()
        return bool(settings.polygon_api_key.strip() and settings.polygon_options_ticks_enabled)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {get_settings().polygon_api_key}"}

    def fetch_trades(self, underlying: str, *, limit: int = 500) -> ProviderResult:
        if not self.is_available():
            return ProviderResult(message="Polygon options ticks not configured.")
        symbol = underlying.upper()
        url = f"{_BASE}/v3/trades"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    url,
                    params={
                        "underlying_ticker": symbol,
                        "limit": min(limit, 1000),
                        "order": "desc",
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                trades = resp.json().get("results") or []
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return ProviderResult(message=f"Polygon tick fetch failed: {exc}")

        sweeps = _detect_sweeps(trades, underlying=symbol)
        bundle = OptionsTickBundle(trades=trades, sweeps=sweeps)
        bundle.aggressive_call_pct, bundle.aggressive_put_pct = _aggressive_pcts(trades)
        return ProviderResult(
            data_available=bool(trades),
            data_source=self.name,
            payload=bundle,
        )


def _detect_sweeps(trades: list[dict], *, underlying: str, window_ms: int = 500) -> list[SweepCandidate]:
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for t in trades:
        details = t.get("details") or {}
        strike = details.get("strike_price") or t.get("strike_price")
        exp = details.get("expiration_date") or t.get("expiration_date")
        cp = (details.get("contract_type") or t.get("contract_type") or "").lower()
        if not strike or not exp:
            continue
        side = "call" if cp == "call" else "put"
        ts = t.get("sip_timestamp") or t.get("participant_timestamp") or 0
        bucket_key = (underlying, float(strike), str(exp)[:10], side, int(ts) // (window_ms * 1_000_000))
        buckets[bucket_key].append(t)

    sweeps: list[SweepCandidate] = []
    for (sym, strike, expiry, side, _), group in buckets.items():
        if len(group) < 2:
            continue
        total_size = sum(float(g.get("size") or 0) for g in group)
        premium = sum(float(g.get("price") or 0) * float(g.get("size") or 0) * 100 for g in group)
        sweeps.append(
            SweepCandidate(
                underlying=sym,
                strike=strike,
                expiry=expiry,
                side=side,
                total_size=total_size,
                trade_count=len(group),
                premium_usd=premium,
                is_sweep=True,
            )
        )
    return sweeps


def _aggressive_pcts(trades: list[dict]) -> tuple[float | None, float | None]:
    call_ask = call_total = put_ask = put_total = 0
    for t in trades:
        details = t.get("details") or {}
        cp = (details.get("contract_type") or "").lower()
        conditions = t.get("conditions") or []
        at_ask = any(c in (14, 41) for c in conditions) if conditions else False
        size = float(t.get("size") or 0)
        if cp == "call":
            call_total += size
            if at_ask:
                call_ask += size
        elif cp == "put":
            put_total += size
            if at_ask:
                put_ask += size
    call_pct = round(call_ask / call_total * 100, 1) if call_total else None
    put_pct = round(put_ask / put_total * 100, 1) if put_total else None
    return call_pct, put_pct
