from datetime import UTC, datetime

from trade_sentinel_api.models.schemas import (
    MacroBriefing,
    MacroEvent,
    MacroReleaseStats,
    MacroSignalsSnapshot,
    NewsItem,
)
from trade_sentinel_api.services.data_gaps import sanitize_briefing_data_gaps
from trade_sentinel_api.services.macro.calendar import macro_trading_date
from trade_sentinel_api.services.macro.context import impact_counts


def _macro():
    from trade_sentinel_api.services import macro as macro_svc

    return macro_svc


def _apply_playbooks(events: list[dict], playbooks: list[dict]) -> list[MacroEvent]:
    playbook_map = {p.get("name", "").lower(): p.get("playbook") for p in playbooks}
    result: list[MacroEvent] = []
    for e in events:
        name = e.get("name", "")
        result.append(
            MacroEvent(
                name=name,
                impact=e.get("impact", "moderate"),
                sectors=e.get("sectors", []),
                time_et=e.get("time_et"),
                actual=e.get("actual"),
                estimate=e.get("estimate"),
                prior=e.get("prior"),
                source=e.get("source"),
                date=e.get("date"),
                playbook=playbook_map.get(name.lower()),
                surprise_pct=e.get("surprise_pct"),
                beat_miss=e.get("beat_miss"),
                release_status=e.get("release_status"),
            )
        )
    return result


def _has_briefing_content(
    events: list[dict],
    signals_snapshot,
    macro_news: list,
) -> bool:
    if events:
        return True
    if macro_news:
        return True
    if signals_snapshot and any(s.level is not None for s in signals_snapshot.signals):
        return True
    return False


async def get_macro_briefing(*, refresh: bool = False) -> MacroBriefing:
    trading_day = macro_trading_date()
    cache_key = f"daily:{trading_day.isoformat()}"

    if refresh:
        _macro().clear_cached("macro", cache_key)
    else:
        cached = _macro().get_cached("macro", cache_key)
        if cached and not _macro().is_stale_llm_summary(cached.get("summary")):
            return MacroBriefing(**cached)
        if cached and _macro().is_stale_llm_summary(cached.get("summary")):
            _macro().clear_cached("macro", cache_key)

    bundle = await _macro().get_daily_macro_bundle()
    events_raw = bundle.get("events") or []
    signals_snapshot = MacroSignalsSnapshot(**bundle["macro_signals"])
    macro_news = [NewsItem(**n) for n in bundle.get("macro_news") or []]
    news_by_source = bundle.get("news_by_source") or {}
    release_stats = (
        MacroReleaseStats(**bundle["release_stats"])
        if bundle.get("release_stats")
        else None
    )
    impact_summary = bundle.get("impact_summary") or impact_counts(events_raw)
    data_gaps: list[str] = list(bundle.get("data_gaps") or [])

    if not _has_briefing_content(events_raw, signals_snapshot, macro_news):
        briefing = MacroBriefing(
            as_of=datetime.now(UTC),
            events=[],
            impact_summary=impact_summary,
            empty_message="No US macro releases, market signals, or headlines available for today.",
            macro_signals=signals_snapshot,
            macro_news=macro_news,
            release_stats=release_stats,
            trading_date=trading_day.isoformat(),
            data_gaps=data_gaps,
        )
        _macro().set_cached("macro", cache_key, briefing.model_dump(mode="json"))
        return briefing

    watchlist = _macro().get_watchlist("default")
    ticker_sectors = await _macro().fetch_watchlist_sectors(watchlist.tickers)

    high_moderate = [e for e in events_raw if e.get("impact") in ("high", "moderate")]

    facts = {
        "date": trading_day.isoformat(),
        "trading_date": trading_day.isoformat(),
        "impact_summary": impact_summary,
        "events": events_raw,
        "release_stats": release_stats.model_dump() if release_stats else None,
        "calendar_headline_candidates": [e["name"] for e in high_moderate[:10]],
        "macro_signals": signals_snapshot.model_dump(mode="json"),
        "macro_news": [h.model_dump() for h in macro_news],
        "news_by_source": news_by_source,
        "watchlist": {
            "tickers": watchlist.tickers,
            "sectors": ticker_sectors,
        },
        "instruction": (
            "Produce a macro briefing weaving macro_signals, calendar events, release_stats, "
            "and macro_news (headlines for context only). Map watchlist tickers to sectors "
            "affected by today's releases."
        ),
    }

    summary, structured = await _macro().summarize_macro(facts)
    macro_events = _apply_playbooks(events_raw, structured.get("event_playbooks", []))

    impact_levels = [{"event": e.name, "level": e.impact} for e in macro_events]
    sector_impacts = list(structured.get("sector_watch", []))
    if summary:
        sector_impacts = sector_impacts or list(summary.bullets)

    llm_gaps = summary.data_gaps if summary else []
    cpi_yoy = any(o.series_id == "CPI_YOY" for o in signals_snapshot.official)
    all_gaps = sanitize_briefing_data_gaps(
        list(dict.fromkeys(data_gaps + llm_gaps)),
        yield_curve_available=signals_snapshot.yield_curve_10y_3m_bps is not None,
        cpi_yoy_available=cpi_yoy,
    )

    briefing = MacroBriefing(
        as_of=datetime.now(UTC),
        market_weather=structured.get("market_weather"),
        events=macro_events,
        headline_events=structured.get("headline_events", []),
        sector_watch=structured.get("sector_watch", []),
        watchlist_exposure=structured.get("watchlist_exposure", []),
        impact_summary=impact_summary,
        sector_impacts=sector_impacts,
        impact_levels=impact_levels,
        summary=summary,
        data_gaps=all_gaps,
        macro_signals=signals_snapshot,
        macro_news=macro_news,
        signal_highlights=structured.get("signal_highlights", []),
        release_stats=release_stats,
        trading_date=trading_day.isoformat(),
    )
    _macro().set_cached("macro", cache_key, briefing.model_dump(mode="json"))
    return briefing
