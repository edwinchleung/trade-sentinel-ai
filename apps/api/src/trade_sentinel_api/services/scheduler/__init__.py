"""Public background scheduler API."""

import asyncio

from trade_sentinel_api.services.scheduler.state import (
    _interval_task,
    _pending_watchlist,
    _running,
)
from trade_sentinel_api.services.scheduler.types import (
    JOB_META,
    BackgroundJobName,
    get_batch_context,
)

__all__ = [
    "JOB_META",
    "BackgroundJobName",
    "_interval_task",
    "_pending_watchlist",
    "_running",
    "asyncio",
    "_run_job",
    "clear_stale_job_errors",
    "get_active_job_name",
    "get_batch_context",
    "get_job_status",
    "get_scan_executor",
    "is_background_warming",
    "job_label",
    "list_job_statuses",
    "market_screener_scanned_count",
    "run_all_jobs",
    "run_job",
    "run_market_screener_job",
    "run_watchlist_jobs",
    "schedule_digest_refresh",
    "schedule_market_screener_refresh",
    "schedule_watchlist_refresh",
    "shutdown_scan_executor",
    "start_background_scheduler",
    "stop_background_scheduler",
    "update_job_progress",
]


def __getattr__(name: str):
    if name in {"get_scan_executor", "shutdown_scan_executor"}:
        from trade_sentinel_api.services.scheduler.executor import (
            get_scan_executor,
            shutdown_scan_executor,
        )

        return get_scan_executor if name == "get_scan_executor" else shutdown_scan_executor
    if name in {
        "is_background_warming",
        "start_background_scheduler",
        "stop_background_scheduler",
    }:
        from trade_sentinel_api.services.scheduler import lifecycle

        return getattr(lifecycle, name)
    if name in {
        "run_job",
        "_run_job",
        "run_all_jobs",
        "run_watchlist_jobs",
        "run_market_screener_job",
    }:
        from trade_sentinel_api.services.scheduler import runner

        if name == "_run_job":
            return runner.run_job
        return getattr(runner, name)
    if name in {
        "schedule_digest_refresh",
        "schedule_market_screener_refresh",
        "schedule_watchlist_refresh",
    }:
        from trade_sentinel_api.services.scheduler import scheduling

        return getattr(scheduling, name)
    if name in {
        "clear_stale_job_errors",
        "get_active_job_name",
        "get_job_status",
        "job_label",
        "list_job_statuses",
        "market_screener_scanned_count",
        "update_job_progress",
    }:
        from trade_sentinel_api.services.scheduler import status

        return getattr(status, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
