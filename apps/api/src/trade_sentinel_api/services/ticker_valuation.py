"""Shared fair-value resolution for context, digest, and screener."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    DigestTickerRow,
    FundamentalsSnapshot,
    ValuationAssessment,
)
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.fundamentals import fetch_fundamentals_snapshot
from trade_sentinel_api.services.market_data import aggregate_market_context
from trade_sentinel_api.services.valuation import (
    build_valuation_assessment,
    build_valuation_summary,
)


def _valuation_settings_fingerprint() -> str:
    s = get_settings()
    payload = {
        "composite_mode": s.valuation_composite_mode,
        "include_dcf": s.valuation_include_dcf,
        "mos_tech": (s.valuation_mos_tech_over, s.valuation_mos_tech_under),
        "mos_def": (s.valuation_mos_defensive_over, s.valuation_mos_defensive_under),
        "mos_default": (s.valuation_mos_default_over, s.valuation_mos_default_under),
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def _price_cache_key(price: float) -> str:
    return f"{round(price, 2):.2f}"


def _valuation_cache_key(symbol: str, price: float) -> str:
    sym = symbol.upper().strip()
    return f"{sym}:{_price_cache_key(price)}:{_valuation_settings_fingerprint()}"


def valuation_digest_fields(
    valuation: ValuationAssessment | None,
    fundamentals: FundamentalsSnapshot | None,
) -> dict[str, Any]:
    """Lite projection for digest/screener rows."""
    fields: dict[str, Any] = {
        "valuation_label": fundamentals.valuation_label if fundamentals else None,
    }
    if not valuation:
        return {
            **fields,
            "mos_pct": None,
            "mos_label": None,
            "valuation_confidence": None,
            "fair_value_low": None,
            "fair_value_mid": None,
            "fair_value_high": None,
        }
    return {
        **fields,
        "mos_pct": valuation.mos_pct,
        "mos_label": valuation.mos_label,
        "valuation_confidence": valuation.confidence,
        "fair_value_low": valuation.fair_value_low,
        "fair_value_mid": valuation.fair_value_mid,
        "fair_value_high": valuation.fair_value_high,
    }


def resolve_ticker_valuation_sync(
    symbol: str,
    price: float,
    fundamentals: FundamentalsSnapshot | None = None,
) -> tuple[FundamentalsSnapshot | None, ValuationAssessment]:
    """Sync fair-value resolution with shared cache (digest batch path)."""
    sym = symbol.upper().strip()
    settings = get_settings()
    if price <= 0:
        empty = ValuationAssessment(
            data_available=False,
            message="Insufficient price for valuation.",
        )
        return fundamentals, empty

    cache_key = _valuation_cache_key(sym, price)
    cached = get_cached("valuation", cache_key)
    if cached:
        fund = (
            FundamentalsSnapshot(**cached["fundamentals"])
            if cached.get("fundamentals")
            else fundamentals
        )
        val = ValuationAssessment(**cached["valuation"])
        return fund, val

    if fundamentals is None:
        from trade_sentinel_api.services.yfinance_bundle import (
            fundamentals_from_bundle,
            load_ticker_bundle_sync,
            market_from_bundle,
        )

        bundle = load_ticker_bundle_sync(sym)
        market = market_from_bundle(bundle)
        p = market.get("price") or price
        fundamentals = fundamentals_from_bundle(bundle, p)
        price = p if p and p > 0 else price

    valuation = build_valuation_assessment(
        fundamentals,
        price,
        include_dcf=settings.valuation_include_dcf,
    )
    set_cached_ttl(
        "valuation",
        cache_key,
        {
            "fundamentals": fundamentals.model_dump(mode="json") if fundamentals else None,
            "valuation": valuation.model_dump(mode="json"),
        },
        settings.cache_ttl_seconds,
    )
    return fundamentals, valuation


async def resolve_ticker_valuation(
    symbol: str,
    *,
    price: float | None = None,
) -> tuple[FundamentalsSnapshot | None, ValuationAssessment]:
    """Single source of truth for fundamentals + fair-value assessment."""
    sym = symbol.upper().strip()
    settings = get_settings()

    if price is None or price <= 0:
        market = await aggregate_market_context(sym)
        price = market.get("price")

    if price is None or price <= 0:
        empty = ValuationAssessment(
            data_available=False,
            message="Insufficient price for valuation.",
        )
        return None, empty

    cache_key = _valuation_cache_key(sym, price)
    cached = get_cached("valuation", cache_key)
    if cached:
        fund = (
            FundamentalsSnapshot(**cached["fundamentals"])
            if cached.get("fundamentals")
            else None
        )
        val = ValuationAssessment(**cached["valuation"])
        return fund, val

    fundamentals = await fetch_fundamentals_snapshot(sym, price)
    valuation = build_valuation_assessment(
        fundamentals,
        price,
        include_dcf=settings.valuation_include_dcf,
    )
    set_cached_ttl(
        "valuation",
        cache_key,
        {
            "fundamentals": fundamentals.model_dump(mode="json") if fundamentals else None,
            "valuation": valuation.model_dump(mode="json"),
        },
        settings.cache_ttl_seconds,
    )
    return fundamentals, valuation


async def hydrate_digest_row(row: DigestTickerRow) -> DigestTickerRow:
    """Refresh price, MOS, and band fields from shared valuation cache (or recompute)."""
    if not row.ticker:
        return row
    market = await aggregate_market_context(row.ticker)
    price = market.get("price") or row.price
    fundamentals, valuation = await resolve_ticker_valuation(row.ticker, price=price)
    updates = valuation_digest_fields(valuation, fundamentals)
    if price is not None:
        updates["price"] = price
    change = market.get("change_pct")
    if change is not None:
        updates["change_pct"] = change
    return row.model_copy(update=updates)


def valuation_summary_for_digest(
    valuation: ValuationAssessment | None,
) -> dict[str, Any] | None:
    if not valuation or not valuation.data_available:
        return None
    return build_valuation_summary(valuation)
