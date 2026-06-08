"""Sector peer ranks from cached market screener + sector P/E priors."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    DigestTickerRow,
    FundamentalsSnapshot,
    SectorContext,
    ValuationAssessment,
)
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl

_SECTOR_PRIORS_PATH = Path(__file__).resolve().parents[3] / "data" / "sector_pe_priors.json"
_MIN_PEERS = 8


def _trading_date_key() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(get_settings().macro_trading_timezone)
    return datetime.now(tz).date().isoformat()


def market_screener_cache_key(universe: str) -> str:
    return f"{_trading_date_key()}:{universe.strip().lower()}:lite"


@lru_cache(maxsize=1)
def _load_sector_pe_priors() -> dict[str, float]:
    try:
        with open(_SECTOR_PRIORS_PATH, encoding="utf-8") as f:
            return {k: float(v) for k, v in json.load(f).items()}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _normalize_sector(sector: str | None) -> str | None:
    if not sector or not str(sector).strip():
        return None
    return str(sector).strip()


def _percentile_rank(value: float, values: list[float]) -> float | None:
    if len(values) < _MIN_PEERS:
        return None
    s = sorted(values)
    below = sum(1 for v in s if v < value)
    return round(below / (len(s) - 1) * 100, 1)


@dataclass
class _SectorBucket:
    pe_forwards: list[float] = field(default_factory=list)
    mos_pcts: list[float] = field(default_factory=list)


def _rows_from_cache(universe: str) -> list[DigestTickerRow]:
    cache_key = market_screener_cache_key(universe)
    cached = get_cached("market_screener", cache_key)
    if not cached or not cached.get("rows"):
        return []
    return [DigestTickerRow(**r) for r in cached["rows"]]


def build_sector_universe_stats(universe: str = "sp500") -> dict[str, _SectorBucket]:
    """Aggregate peer distributions from cached market screener rows."""
    buckets: dict[str, _SectorBucket] = {}
    for row in _rows_from_cache(universe):
        sector = _normalize_sector(row.sector)
        if not sector:
            continue
        bucket = buckets.setdefault(sector, _SectorBucket())
        if row.pe_forward is not None and row.pe_forward > 0:
            bucket.pe_forwards.append(row.pe_forward)
        if row.mos_pct is not None:
            bucket.mos_pcts.append(row.mos_pct)
    return buckets


def _sector_stats_cache_key(universe: str) -> str:
    return f"{_trading_date_key()}:{universe.strip().lower()}"


def get_sector_universe_stats(universe: str = "sp500") -> dict[str, _SectorBucket]:
    """Cached sector buckets for the trading day."""
    key = _sector_stats_cache_key(universe)
    cached = get_cached("sector_stats", key)
    if cached and cached.get("buckets"):
        out: dict[str, _SectorBucket] = {}
        for sector, data in cached["buckets"].items():
            out[sector] = _SectorBucket(
                pe_forwards=list(data.get("pe_forwards") or []),
                mos_pcts=list(data.get("mos_pcts") or []),
            )
        return out

    buckets = build_sector_universe_stats(universe)
    if buckets:
        settings = get_settings()
        ttl = settings.market_screener_cache_minutes * 60
        set_cached_ttl(
            "sector_stats",
            key,
            {
                "buckets": {
                    s: {"pe_forwards": b.pe_forwards, "mos_pcts": b.mos_pcts}
                    for s, b in buckets.items()
                }
            },
            ttl,
        )
    return buckets


def _quartile_label(pct: float | None) -> str | None:
    if pct is None:
        return None
    if pct >= 75:
        return "top quartile"
    if pct >= 50:
        return "above median"
    if pct >= 25:
        return "below median"
    return "bottom quartile"


def build_sector_context(
    ticker: str,
    fundamentals: FundamentalsSnapshot | None,
    valuation: ValuationAssessment | None,
    *,
    universe: str = "sp500",
    stats: dict[str, _SectorBucket] | None = None,
) -> SectorContext:
    sector = _normalize_sector(fundamentals.sector if fundamentals else None)
    industry = fundamentals.industry if fundamentals else None
    priors = _load_sector_pe_priors()
    prior_pe = priors.get(sector or "", None) if sector else None

    pe_vs_prior = None
    pe_forward = fundamentals.pe_forward if fundamentals else None
    if prior_pe and pe_forward and prior_pe > 0:
        pe_vs_prior = round((pe_forward - prior_pe) / prior_pe * 100, 2)

    if not sector:
        return SectorContext(
            industry=industry,
            universe=universe,
            sector_pe_prior=prior_pe,
            message="Sector not available for peer comparison.",
        )

    buckets = stats if stats is not None else get_sector_universe_stats(universe)
    bucket = buckets.get(sector)
    peer_count = len(bucket.pe_forwards) if bucket else 0

    pe_sector_pct = None
    mos_sector_pct = None
    if bucket and pe_forward is not None and pe_forward > 0:
        pe_sector_pct = _percentile_rank(pe_forward, bucket.pe_forwards)
    if bucket and valuation and valuation.mos_pct is not None:
        mos_sector_pct = _percentile_rank(valuation.mos_pct, bucket.mos_pcts)

    bullets: list[str] = []
    if prior_pe and pe_forward:
        direction = "above" if pe_vs_prior and pe_vs_prior > 0 else "below"
        bullets.append(
            f"Forward P/E {pe_forward:.1f} is ~{abs(pe_vs_prior or 0):.0f}% {direction} "
            f"static sector prior ({prior_pe:.1f} for {sector})."
        )
    if pe_sector_pct is not None and peer_count >= _MIN_PEERS:
        bullets.append(
            f"Forward P/E in {_quartile_label(pe_sector_pct)} vs ~{peer_count} "
            f"{sector} names in {universe.upper()} preset cache."
        )
    if mos_sector_pct is not None and peer_count >= _MIN_PEERS:
        bullets.append(
            f"Premium vs model fair mid at ~{mos_sector_pct:.0f}th percentile within sector peers."
        )

    headline = None
    if pe_sector_pct is not None and peer_count >= _MIN_PEERS:
        headline = f"{sector}: {_quartile_label(pe_sector_pct)} P/E vs preset peers"
    elif pe_vs_prior is not None:
        headline = f"{sector}: vs sector prior P/E"

    data_available = bool(bullets) or headline is not None
    msg = None
    if peer_count < _MIN_PEERS:
        msg = f"Fewer than {_MIN_PEERS} cached peers in {sector}; warm market screener cache for ranks."

    return SectorContext(
        sector=sector,
        industry=industry,
        universe=universe,
        sector_pe_prior=prior_pe,
        pe_vs_sector_prior_pct=pe_vs_prior,
        pe_forward_sector_percentile=pe_sector_pct,
        mos_sector_percentile=mos_sector_pct,
        sector_headline=headline,
        sector_bullets=bullets[:3],
        peer_count=peer_count,
        data_available=data_available,
        message=msg,
    )


def enrich_digest_row_sector_fields(
    row: DigestTickerRow,
    *,
    universe: str = "sp500",
    stats: dict[str, _SectorBucket] | None = None,
) -> DigestTickerRow:
    """Attach sector peer percentile when universe stats cache is warm."""
    sector = _normalize_sector(row.sector)
    if not sector or row.pe_forward is None:
        return row
    buckets = stats if stats is not None else get_sector_universe_stats(universe)
    bucket = buckets.get(sector)
    if not bucket:
        return row
    pe_pct = _percentile_rank(row.pe_forward, bucket.pe_forwards)
    if pe_pct is None:
        return row
    return row.model_copy(update={"pe_sector_percentile": pe_pct})
