"""WebSocket broadcast hub for background job status and progressive scan updates."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.cache import set_cached_ttl

logger = logging.getLogger(__name__)


def _channels_for_event(event: dict[str, Any]) -> set[str]:
    """Map event type to subscription channels."""
    etype = event.get("type", "")
    channels: set[str] = {"jobs"}

    if etype in ("jobs_snapshot", "job_started", "job_finished"):
        return {"jobs"}

    if etype == "scan_progress":
        resource = event.get("resource", "")
        if resource == "market_screener":
            universe = event.get("universe")
            if universe:
                channels.add(f"screener:{universe}")
        elif resource == "digest":
            wl = event.get("watchlist_name", "default")
            channels.add(f"digest:{wl}")
        return channels

    if etype == "screener_rows":
        universe = event.get("universe")
        if universe:
            channels.add(f"screener:{universe}")
        return channels

    if etype == "digest_rows":
        wl = event.get("watchlist_name", "default")
        channels.add(f"digest:{wl}")
        return channels

    return channels


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channels: set[str] | None = None) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = channels or {"jobs"}

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)

    async def set_channels(self, websocket: WebSocket, channels: set[str]) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections[websocket] = channels

    async def send_json(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(payload, default=str))

    async def broadcast(self, event: dict[str, Any]) -> None:
        if not get_settings().websocket_enabled:
            return
        event_channels = _channels_for_event(event)
        text = json.dumps(event, default=str)
        async with self._lock:
            targets = [
                (ws, chans)
                for ws, chans in list(self._connections.items())
                if event_channels & chans
            ]
        for ws, _ in targets:
            try:
                await ws.send_text(text)
            except Exception:
                self.disconnect(ws)

    def connection_count(self) -> int:
        return len(self._connections)


_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    return _manager


def publish(event: dict[str, Any]) -> None:
    """Schedule broadcast on the running event loop (no-op if disabled or no loop)."""
    if not get_settings().websocket_enabled:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_manager.broadcast(event))


def build_jobs_snapshot_payload() -> dict[str, Any]:
    from trade_sentinel_api.services.scheduler import (
        get_active_job_name,
        get_batch_context,
        is_background_warming,
        list_job_statuses,
        market_screener_scanned_count,
    )

    settings = get_settings()
    batch = get_batch_context()
    return {
        "type": "jobs_snapshot",
        "as_of": datetime.now(UTC).isoformat(),
        "jobs": list_job_statuses(),
        "market_screener_scanned_count": market_screener_scanned_count(),
        "background_jobs_enabled": settings.background_jobs_enabled,
        "warming": is_background_warming(),
        "active_job": get_active_job_name(),
        "batch_position": batch.get("position") or None,
        "batch_total": batch.get("total") or None,
    }


async def send_jobs_snapshot(websocket: WebSocket) -> None:
    await get_connection_manager().send_json(websocket, build_jobs_snapshot_payload())


def publish_jobs_snapshot() -> None:
    publish(build_jobs_snapshot_payload())


def publish_job_started(name: str) -> None:
    publish({"type": "job_started", "name": name})
    publish(build_jobs_snapshot_payload())


def publish_job_finished(name: str, *, status: str, last_error: str | None = None) -> None:
    publish(
        {
            "type": "job_finished",
            "name": name,
            "status": status,
            "last_error": last_error,
        }
    )
    publish(build_jobs_snapshot_payload())


def _progress_phase(resource: str, completed: int, total: int, universe: str | None) -> str:
    if resource == "smart_money_feed":
        return f"Parsing Form 4 filings ({completed}/{total})"
    if resource == "market_screener":
        label = universe or "universe"
        return f"Scanning {label} ({completed}/{total} tickers)"
    if resource == "digest":
        return f"Building digest ({completed}/{total} tickers)"
    if resource == "options_scan":
        label = universe or "universe"
        return f"Scanning options — {label} ({completed}/{total})"
    if resource == "volume_scan":
        label = universe or "universe"
        return f"Scanning volume — {label} ({completed}/{total})"
    return f"Scanning ({completed}/{total})"


def publish_scan_progress(
    *,
    resource: str,
    cache_key: str,
    completed: int,
    total: int,
    universe: str | None = None,
    watchlist_name: str | None = None,
    job_name: str | None = None,
) -> None:
    percent = round(100.0 * completed / total, 1) if total > 0 else 0.0
    phase = _progress_phase(resource, completed, total, universe)
    payload: dict[str, Any] = {
        "type": "scan_progress",
        "resource": resource,
        "cache_key": cache_key,
        "completed": completed,
        "total": total,
        "percent": percent,
        "phase": phase,
    }
    if universe:
        payload["universe"] = universe
    if watchlist_name:
        payload["watchlist_name"] = watchlist_name
    if job_name:
        payload["job_name"] = job_name
    publish(payload)
    if job_name:
        from trade_sentinel_api.services.scheduler import update_job_progress

        update_job_progress(
            job_name,
            phase=phase,
            progress_completed=completed,
            progress_total=total,
        )


def publish_job_progress(
    job_name: str,
    *,
    completed: int,
    total: int,
) -> None:
    """Update job cache + WebSocket for non-chunked jobs (e.g. insider feed enrichment)."""
    publish_scan_progress(
        resource="smart_money_feed",
        cache_key=f"feed:{job_name}",
        completed=completed,
        total=total,
        job_name=job_name,
    )


def publish_screener_rows(
    *,
    universe: str,
    rows: list[dict[str, Any]],
    completed: int,
    total: int,
) -> None:
    publish(
        {
            "type": "screener_rows",
            "universe": universe,
            "rows": rows,
            "completed": completed,
            "total": total,
            "stale": True,
        }
    )


def publish_digest_rows(
    *,
    watchlist_name: str,
    rows: list[dict[str, Any]],
    completed: int,
    total: int,
) -> None:
    publish(
        {
            "type": "digest_rows",
            "watchlist_name": watchlist_name,
            "rows": rows,
            "completed": completed,
            "total": total,
        }
    )


def _universe_from_market_cache_key(cache_key: str) -> str | None:
    parts = cache_key.split(":")
    if len(parts) >= 2:
        return parts[1]
    return None


def _watchlist_from_digest_cache_key(cache_key: str) -> str | None:
    parts = cache_key.split(":")
    if len(parts) >= 2:
        return parts[1]
    return None


def after_chunk_cached(
    *,
    cache_prefix: str,
    cache_key: str,
    all_rows: list,
    chunk_rows: list,
    completed: int,
    total: int,
    cache_ttl_seconds: int,
    cached_at: datetime,
) -> None:
    """Write partial cache and emit WebSocket progress + row batch events."""
    all_dicts = [r.model_dump(mode="json") for r in all_rows]
    chunk_dicts = [r.model_dump(mode="json") for r in chunk_rows]

    if cache_prefix == "market_screener":
        set_cached_ttl(
            cache_prefix,
            cache_key,
            {
                "rows": all_dicts,
                "cached_at": cached_at.isoformat(),
                "partial": completed < total,
            },
            cache_ttl_seconds,
        )
        universe = _universe_from_market_cache_key(cache_key) or "sp500"
        publish_scan_progress(
            resource="market_screener",
            cache_key=cache_key,
            completed=completed,
            total=total,
            universe=universe,
            job_name="market_screener",
        )
        publish_screener_rows(
            universe=universe,
            rows=chunk_dicts,
            completed=completed,
            total=total,
        )
    elif cache_prefix == "digest":
        wl = _watchlist_from_digest_cache_key(cache_key) or "default"
        parts = cache_key.split(":")
        trading_date = parts[0] if parts else ""
        set_cached_ttl(
            "digest",
            cache_key,
            {
                "as_of": cached_at.isoformat(),
                "trading_date": trading_date,
                "watchlist_name": wl,
                "tickers": all_dicts,
                "partial": completed < total,
            },
            cache_ttl_seconds,
        )
        publish_scan_progress(
            resource="digest",
            cache_key=cache_key,
            completed=completed,
            total=total,
            watchlist_name=wl,
            job_name="digest",
        )
        publish_digest_rows(
            watchlist_name=wl,
            rows=chunk_dicts,
            completed=completed,
            total=total,
        )
