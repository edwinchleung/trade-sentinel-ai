"""Enrich calendar events with surprise statistics and day-level aggregates."""

from trade_sentinel_api.models.schemas import MacroReleaseStats

_BEAT_MISS_INLINE_THRESHOLD_PCT = 0.5


def enrich_event_release_stats(event: dict) -> dict:
    """Add surprise_pct, beat_miss, and release_status to an event dict (in place)."""
    actual = event.get("actual")
    estimate = event.get("estimate")
    event["release_status"] = "released" if actual is not None else "scheduled"
    if actual is None or estimate is None:
        event["surprise_pct"] = None
        event["beat_miss"] = "unavailable"
        return event
    if estimate == 0:
        event["surprise_pct"] = None
        event["beat_miss"] = "unavailable"
        return event

    surprise = round((actual - estimate) / abs(estimate) * 100, 2)
    event["surprise_pct"] = surprise
    if abs(surprise) <= _BEAT_MISS_INLINE_THRESHOLD_PCT:
        event["beat_miss"] = "inline"
    elif actual > estimate:
        event["beat_miss"] = "beat"
    else:
        event["beat_miss"] = "miss"
    return event


def enrich_events_release_stats(events: list[dict]) -> list[dict]:
    return [enrich_event_release_stats(dict(e)) for e in events]


def build_release_stats(events: list[dict]) -> MacroReleaseStats:
    beats = misses = inline = unavailable = 0
    surprises: list[dict] = []

    for e in events:
        bm = e.get("beat_miss", "unavailable")
        if bm == "beat":
            beats += 1
        elif bm == "miss":
            misses += 1
        elif bm == "inline":
            inline += 1
        else:
            unavailable += 1

        sp = e.get("surprise_pct")
        if sp is not None and bm in ("beat", "miss", "inline"):
            surprises.append(
                {
                    "name": e.get("name", ""),
                    "surprise_pct": sp,
                    "beat_miss": bm,
                    "actual": e.get("actual"),
                    "estimate": e.get("estimate"),
                }
            )

    surprises.sort(key=lambda x: abs(x.get("surprise_pct") or 0), reverse=True)
    return MacroReleaseStats(
        beats=beats,
        misses=misses,
        inline=inline,
        unavailable=unavailable,
        largest_surprises=surprises[:5],
    )
