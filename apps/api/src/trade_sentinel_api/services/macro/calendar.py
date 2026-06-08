import json
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from trade_sentinel_api.config import get_settings

_SCHEDULE_PATH = Path(__file__).resolve().parents[4] / "data" / "macro_schedule.json"
_SECTOR_MAP_PATH = Path(__file__).resolve().parents[4] / "data" / "event_sector_map.json"

_IMPACT_MAP = {"high": "high", "medium": "moderate", "low": "noise"}


@lru_cache(maxsize=1)
def _load_sector_map() -> list[dict]:
    if not _SECTOR_MAP_PATH.is_file():
        return []
    with _SECTOR_MAP_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("rules", [])


def map_event_sectors(name: str, existing: list[str] | None = None) -> list[str]:
    """Map event name to sectors via keyword rules."""
    if existing and existing != ["Broad Market"]:
        return existing
    lower = name.lower()
    for rule in _load_sector_map():
        for kw in rule.get("keywords", []):
            if kw in lower:
                return list(rule.get("sectors", ["Broad Market"]))
    return existing or ["Broad Market"]


def _load_schedule() -> dict:
    if not _SCHEDULE_PATH.is_file():
        return {"recurring": [], "dated": []}
    with _SCHEDULE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _event_key(event: dict) -> str:
    return str(event.get("name", "")).lower()


def macro_trading_date(target: date | None = None) -> date:
    """US macro trading calendar day in configured timezone (default America/New_York)."""
    settings = get_settings()
    tz = ZoneInfo(settings.macro_trading_timezone)
    if target is not None:
        return target
    return datetime.now(UTC).astimezone(tz).date()


def _is_first_friday(today: date) -> bool:
    return today.weekday() == 4 and 1 <= today.day <= 7


def _matches_recurring(entry: dict, today: date) -> bool:
    if entry.get("first_friday"):
        if not _is_first_friday(today):
            return False
    else:
        weekday = entry.get("weekday")
        if weekday is not None and today.weekday() != int(weekday):
            return False
    weeks = entry.get("week_of_month")
    if weeks is not None:
        week_num = (today.day - 1) // 7 + 1
        if week_num not in weeks:
            return False
    return True


def _parse_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _events_from_schedule(target: date) -> list[dict]:
    schedule = _load_schedule()
    seen: set[str] = set()
    events: list[dict] = []

    for entry in schedule.get("dated", []):
        entry_date = entry.get("date")
        if not entry_date:
            continue
        try:
            if date.fromisoformat(str(entry_date)) != target:
                continue
        except ValueError:
            continue
        key = _event_key(entry)
        if key in seen:
            continue
        seen.add(key)
        sectors = map_event_sectors(entry["name"], entry.get("sectors", []))
        events.append(
            {
                "name": entry["name"],
                "impact": entry.get("impact", "moderate"),
                "sectors": sectors,
                "date": str(entry_date),
                "source": "schedule",
            }
        )

    for entry in schedule.get("recurring", []):
        if not _matches_recurring(entry, target):
            continue
        key = _event_key(entry)
        if key in seen:
            continue
        seen.add(key)
        sectors = map_event_sectors(entry["name"], entry.get("sectors", []))
        events.append(
            {
                "name": entry["name"],
                "impact": entry.get("impact", "moderate"),
                "sectors": sectors,
                "date": target.isoformat(),
                "source": "schedule",
            }
        )

    return events


async def _fetch_finnhub_calendar(from_date: date, to_date: date) -> list[dict]:
    settings = get_settings()
    if not settings.finnhub_api_key:
        return []
    url = "https://finnhub.io/api/v1/calendar/economic"
    params = {
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "token": settings.finnhub_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return []

    economic = data.get("economicCalendar") or data.get("data") or []
    if not isinstance(economic, list):
        return []

    events: list[dict] = []
    for row in economic:
        if not isinstance(row, dict):
            continue
        country = str(row.get("country", "")).upper()
        if country and country not in ("US", "USA"):
            continue
        impact_raw = str(row.get("impact", "")).lower()
        impact = _IMPACT_MAP.get(impact_raw, "moderate" if impact_raw else "moderate")
        name = row.get("event") or row.get("title") or "Economic release"
        event_date = row.get("date") or row.get("time") or from_date.isoformat()
        time_et = None
        if isinstance(event_date, (int, float)):
            event_date = datetime.fromtimestamp(event_date, tz=UTC).date().isoformat()
        elif isinstance(event_date, str):
            if " " in event_date:
                parts = event_date.split(" ", 1)
                event_date = parts[0]
                if len(parts) > 1:
                    time_et = parts[1][:8]
            elif "T" in event_date:
                parts = event_date.split("T", 1)
                event_date = parts[0]
                if len(parts) > 1:
                    time_et = parts[1][:8]
        sectors = map_event_sectors(str(name))
        events.append(
            {
                "name": str(name),
                "impact": impact,
                "sectors": sectors,
                "date": str(event_date)[:10],
                "time_et": time_et,
                "actual": _parse_float(row.get("actual")),
                "estimate": _parse_float(row.get("estimate")),
                "prior": _parse_float(row.get("prev")),
                "source": "finnhub",
            }
        )
    return events


async def get_macro_events_for_day(target: date | None = None) -> list[dict]:
    """Return macro events for the given US trading calendar day (default: today ET)."""
    day = macro_trading_date(target)
    seen: set[str] = set()
    merged: list[dict] = []

    finnhub = await _fetch_finnhub_calendar(day, day + timedelta(days=1))
    for event in finnhub:
        if str(event.get("date", ""))[:10] != day.isoformat():
            continue
        key = _event_key(event)
        if key in seen:
            continue
        seen.add(key)
        merged.append(event)

    for event in _events_from_schedule(day):
        key = _event_key(event)
        if key in seen:
            continue
        seen.add(key)
        merged.append(event)

    return merged
