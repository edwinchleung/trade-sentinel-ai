"""Deferred scheduling helpers for watchlist, digest, and screener refreshes."""

from __future__ import annotations

import asyncio

from trade_sentinel_api.config import get_settings
import trade_sentinel_api.services.scheduler.state as _state
from trade_sentinel_api.services.scheduler.runner import (
    is_batch_running,
    run_job,
    run_market_screener_job,
    run_watchlist_jobs,
)
from trade_sentinel_api.services.scheduler.types import BackgroundJobName

_debounce_task: asyncio.Task | None = None


async def _debounced_watchlist_refresh() -> None:
    settings = get_settings()
    await asyncio.sleep(settings.background_watchlist_debounce_seconds)
    names = sorted(_state._pending_watchlist)
    _state._pending_watchlist.clear()
    if names:
        await run_watchlist_jobs(reason=f"watchlist:{','.join(names)}")


def schedule_watchlist_refresh(watchlist_name: str) -> None:
    _state._pending_watchlist.add(watchlist_name)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    global _debounce_task
    if _debounce_task and not _debounce_task.done():
        _debounce_task.cancel()

    async def _run():
        try:
            await _debounced_watchlist_refresh()
        except asyncio.CancelledError:
            pass

    _debounce_task = loop.create_task(_run())


def schedule_market_screener_refresh() -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(run_market_screener_job(reason="cache_miss"))


def schedule_digest_refresh() -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _one():
        if is_batch_running():
            return
        await run_job(BackgroundJobName.DIGEST)

    loop.create_task(_one())


def get_debounce_task() -> asyncio.Task | None:
    return _debounce_task
