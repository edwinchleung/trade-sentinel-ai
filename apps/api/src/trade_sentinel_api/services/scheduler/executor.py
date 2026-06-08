"""Thread pool for background scan workloads."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from trade_sentinel_api.config import get_settings

_executor: ThreadPoolExecutor | None = None


def get_scan_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        workers = get_settings().background_scan_workers
        _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="bgscan")
    return _executor


def shutdown_scan_executor() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None
