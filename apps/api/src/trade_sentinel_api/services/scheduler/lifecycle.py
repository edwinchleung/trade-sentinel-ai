"""Scheduler startup and shutdown."""

from __future__ import annotations

import asyncio
import logging

from trade_sentinel_api.config import get_settings
import trade_sentinel_api.services.scheduler.state as _state
from trade_sentinel_api.services.scheduler.executor import get_scan_executor, shutdown_scan_executor
from trade_sentinel_api.services.scheduler.runner import is_batch_running, run_all_jobs
from trade_sentinel_api.services.scheduler.scheduling import get_debounce_task

logger = logging.getLogger(__name__)


async def _interval_loop() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(settings.background_refresh_interval_minutes * 60)
        await run_all_jobs(reason="interval")


async def _run_startup_warm() -> None:
    try:
        await run_all_jobs(reason="startup")
    except Exception as exc:
        logger.exception("Background startup warm failed: %s", exc)


def is_background_warming() -> bool:
    """True while a full background job batch (startup, interval, or manual all) is running."""
    return is_batch_running()


async def start_background_scheduler() -> None:
    settings = get_settings()
    if not settings.background_jobs_enabled:
        logger.info("Background jobs disabled (BACKGROUND_JOBS_ENABLED=false)")
        return
    from trade_sentinel_api.services.sec.edgar import warm_company_tickers_cache
    from trade_sentinel_api.services.yfinance_logging import configure_yfinance_logging

    configure_yfinance_logging(quiet=settings.yfinance_quiet_logs)
    await asyncio.to_thread(warm_company_tickers_cache)
    get_scan_executor()
    _state._interval_task = asyncio.create_task(_interval_loop())
    if settings.background_startup_warm:
        asyncio.create_task(_run_startup_warm())
    else:
        logger.info("Background startup warm disabled (BACKGROUND_STARTUP_WARM=false)")


async def stop_background_scheduler() -> None:
    debounce_task = get_debounce_task()
    if _state._interval_task:
        _state._interval_task.cancel()
        try:
            await _state._interval_task
        except asyncio.CancelledError:
            pass
        _state._interval_task = None
    if debounce_task and not debounce_task.done():
        debounce_task.cancel()
    shutdown_scan_executor()
