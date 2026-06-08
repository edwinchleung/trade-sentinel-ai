"""Shared daily macro data bundle for briefing and ticker context."""

import asyncio

from trade_sentinel_api.models.schemas import (
    MacroContextOverlay,
    MacroEvent,
    MacroReleaseStats,
    MacroSignalsSnapshot,
    NewsItem,
)
from trade_sentinel_api.services.cache import get_cached, set_cached
from trade_sentinel_api.services.data_gaps import collapse_cpi_gaps, macro_facts_data_gaps
from trade_sentinel_api.services.macro.calendar import get_macro_events_for_day, macro_trading_date
from trade_sentinel_api.services.macro.news import fetch_macro_news
from trade_sentinel_api.services.macro.release_stats import (
    build_release_stats,
    enrich_events_release_stats,
)
from trade_sentinel_api.services.macro.signals import fetch_macro_signals

_SECTOR_ALIASES: dict[str, set[str]] = {
    "technology": {"technology", "tech"},
    "financial services": {"financial services", "financials", "banking"},
    "healthcare": {"healthcare", "health care"},
    "consumer cyclical": {"consumer", "consumer discretionary", "discretionary"},
    "consumer defensive": {"consumer", "consumer staples", "staples"},
    "communication services": {"communication services", "services", "tech"},
    "industrials": {"industrials", "materials"},
    "energy": {"energy"},
    "utilities": {"utilities"},
    "real estate": {"real estate"},
    "basic materials": {"materials", "industrials"},
}


def impact_counts(events: list[dict]) -> dict[str, int]:
    counts = {"high": 0, "moderate": 0, "noise": 0}
    for e in events:
        level = e.get("impact", "moderate")
        if level in counts:
            counts[level] += 1
    return counts


def _normalize_sector_tokens(sector: str | None) -> set[str]:
    if not sector:
        return set()
    lower = sector.strip().lower()
    tokens = {lower}
    if lower in _SECTOR_ALIASES:
        tokens |= _SECTOR_ALIASES[lower]
    for key, aliases in _SECTOR_ALIASES.items():
        if lower == key or lower in aliases:
            tokens |= aliases
            tokens.add(key)
    return tokens


def sector_matches_ticker(ticker_sector: str | None, event_sectors: list[str]) -> bool:
    if not event_sectors:
        return False
    if "Broad Market" in event_sectors:
        return True
    ticker_tokens = _normalize_sector_tokens(ticker_sector)
    if not ticker_tokens:
        return False
    for es in event_sectors:
        event_tokens = _normalize_sector_tokens(es)
        if ticker_tokens & event_tokens:
            return True
    return False


def _event_dict_to_model(e: dict) -> MacroEvent:
    return MacroEvent(
        name=e.get("name", ""),
        impact=e.get("impact", "moderate"),
        sectors=e.get("sectors", []),
        time_et=e.get("time_et"),
        actual=e.get("actual"),
        estimate=e.get("estimate"),
        prior=e.get("prior"),
        source=e.get("source"),
        date=e.get("date"),
        surprise_pct=e.get("surprise_pct"),
        beat_miss=e.get("beat_miss"),
        release_status=e.get("release_status"),
    )


def _top_signals_by_move(signals_snapshot: MacroSignalsSnapshot, limit: int = 6) -> list:
    ranked = sorted(
        [s for s in signals_snapshot.signals if s.change_1d_pct is not None],
        key=lambda s: abs(s.change_1d_pct or 0),
        reverse=True,
    )
    return ranked[:limit]


async def build_daily_macro_bundle() -> dict:
    """Fetch and enrich macro data for the current US trading day."""
    trading_day = macro_trading_date()
    events_raw, signals_snapshot, (macro_news, news_by_source, news_gaps) = await asyncio.gather(
        get_macro_events_for_day(trading_day),
        fetch_macro_signals(),
        fetch_macro_news(),
    )
    events_raw = enrich_events_release_stats(events_raw)
    release_stats = build_release_stats(events_raw) if events_raw else None
    summary = impact_counts(events_raw)
    data_gaps: list[str] = collapse_cpi_gaps(
        list(signals_snapshot.data_gaps) + list(news_gaps)
    )

    bundle = {
        "trading_date": trading_day.isoformat(),
        "events": events_raw,
        "impact_summary": summary,
        "release_stats": release_stats.model_dump() if release_stats else None,
        "macro_signals": signals_snapshot.model_dump(mode="json"),
        "macro_news": [h.model_dump() for h in macro_news],
        "news_by_source": news_by_source,
        "data_gaps": data_gaps,
        "market_weather": None,
        "signal_highlights": [],
        "headline_events": [],
    }
    attach_briefing_narrative(bundle)
    return bundle


def _fallback_market_weather(bundle: dict) -> str | None:
    impact = bundle.get("impact_summary") or {}
    high = impact.get("high", 0)
    moderate = impact.get("moderate", 0)
    signals_raw = bundle.get("macro_signals") or {}
    risk_tone = signals_raw.get("risk_tone", "normal")

    parts: list[str] = []
    if high:
        parts.append(f"{high} high-impact event{'s' if high != 1 else ''}")
    if moderate:
        parts.append(f"{moderate} moderate-impact event{'s' if moderate != 1 else ''}")
    if risk_tone == "elevated_vix":
        parts.append("elevated VIX")
    elif risk_tone == "inverted_curve":
        parts.append("inverted yield curve")

    if not parts:
        events = bundle.get("events") or []
        if not events:
            return "Quiet macro calendar today."
        return "Macro calendar active; run Briefing for full narrative."

    return "; ".join(parts).capitalize() + "."


def _fallback_signal_highlights(bundle: dict) -> list[str]:
    signals_raw = bundle.get("macro_signals") or {}
    try:
        snapshot = MacroSignalsSnapshot(**signals_raw)
    except Exception:
        return []
    highlights: list[str] = []
    for sig in _top_signals_by_move(snapshot, 3):
        ch = sig.change_1d_pct
        if ch is None:
            continue
        sign = "+" if ch > 0 else ""
        highlights.append(f"{sig.label} {sign}{ch:.2f}% (1d)")
    if snapshot.risk_tone == "elevated_vix":
        highlights.append("VIX elevated — risk-off tone")
    return highlights[:5]


def attach_briefing_narrative(bundle: dict) -> None:
    """Reuse cached Macro Briefing LLM output when available (no extra LLM call)."""
    trading_date = bundle.get("trading_date")
    if not trading_date:
        return
    cached = get_cached("macro", f"daily:{trading_date}")
    if cached:
        bundle["market_weather"] = cached.get("market_weather")
        bundle["signal_highlights"] = cached.get("signal_highlights") or []
        bundle["headline_events"] = cached.get("headline_events") or []
        return

    bundle["market_weather"] = _fallback_market_weather(bundle)
    bundle["signal_highlights"] = _fallback_signal_highlights(bundle)
    events = bundle.get("events") or []
    bundle["headline_events"] = [
        e.get("name", "") for e in events if e.get("impact") == "high"
    ][:3]


async def get_daily_macro_bundle() -> dict:
    trading_day = macro_trading_date()
    cache_key = f"bundle:{trading_day.isoformat()}"
    cached = get_cached("macro", cache_key)
    if cached:
        return cached
    bundle = await build_daily_macro_bundle()
    set_cached("macro", cache_key, bundle)
    return bundle


def macro_overlay_for_ticker(
    ticker: str,
    sector: str | None,
    bundle: dict,
) -> MacroContextOverlay:
    """Build sector-filtered macro overlay for a single ticker."""
    events = bundle.get("events") or []
    relevant = [
        e
        for e in events
        if sector_matches_ticker(sector, e.get("sectors", []))
        and e.get("impact") in ("high", "moderate", "noise")
    ]
    relevant.sort(
        key=lambda e: (
            0 if e.get("impact") == "high" else (1 if e.get("impact") == "moderate" else 2),
            e.get("name", ""),
        )
    )
    relevant = relevant[:8]

    signals_raw = bundle.get("macro_signals")
    signals_snapshot = (
        MacroSignalsSnapshot(**signals_raw) if signals_raw else None
    )
    top_signals = []
    if signals_snapshot:
        top_signals = _top_signals_by_move(signals_snapshot, 6)
        signals_snapshot = MacroSignalsSnapshot(
            as_of=signals_snapshot.as_of,
            signals=top_signals,
            yield_curve_10y_3m_bps=signals_snapshot.yield_curve_10y_3m_bps,
            risk_tone=signals_snapshot.risk_tone,
            official=signals_snapshot.official,
            data_gaps=signals_snapshot.data_gaps,
        )

    news_raw = bundle.get("macro_news") or []
    macro_news = [NewsItem(**n) for n in news_raw[:5]]

    release_stats = None
    if bundle.get("release_stats"):
        release_stats = MacroReleaseStats(**bundle["release_stats"])

    has_content = bool(
        relevant
        or macro_news
        or (signals_snapshot and any(s.level is not None for s in signals_snapshot.signals))
        or bundle.get("market_weather")
        or bundle.get("signal_highlights")
    )

    return MacroContextOverlay(
        trading_date=bundle.get("trading_date", macro_trading_date().isoformat()),
        ticker=ticker.upper(),
        ticker_sector=sector,
        has_content=has_content,
        market_weather=bundle.get("market_weather"),
        signal_highlights=list(bundle.get("signal_highlights") or [])[:5],
        headline_events=list(bundle.get("headline_events") or [])[:3],
        relevant_events=[_event_dict_to_model(e) for e in relevant],
        impact_summary=bundle.get("impact_summary") or {},
        macro_signals=signals_snapshot,
        macro_news=macro_news,
        release_stats=release_stats,
        data_gaps=list(bundle.get("data_gaps") or []),
    )


def macro_context_facts(overlay: MacroContextOverlay) -> dict:
    """Compact dict for LLM context facts (no infra data_gaps)."""
    facts = overlay.model_dump(mode="json")
    facts.pop("data_gaps", None)
    actionable = macro_facts_data_gaps(overlay.data_gaps)
    if actionable:
        facts["data_gaps"] = actionable
    return facts
