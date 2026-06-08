"""Background job status tracking."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.scheduler.types import JOB_META, BackgroundJobName

logger = logging.getLogger(__name__)

_INSIDER_BUILDER_STALE_ERROR = (
    "_build_insider_result() got an unexpected keyword argument 'provider_degraded'"
)


def _job_meta_key(name: BackgroundJobName) -> str:
    return f"{name.value}"


def job_label(name: str | BackgroundJobName) -> str:
    key = name.value if isinstance(name, BackgroundJobName) else name
    return JOB_META.get(key, {}).get("label", key.replace("_", " ").title())


def get_job_status(name: BackgroundJobName) -> dict[str, Any]:
    cached = get_cached("bg_job", _job_meta_key(name))
    if isinstance(cached, dict):
        return {**cached, "label": cached.get("label") or job_label(name)}
    return {"name": name.value, "status": "idle", "label": job_label(name)}


def clear_stale_job_errors() -> None:
    """Drop in-memory job errors from pre-fix deploys (cache is process-local)."""
    for job in BackgroundJobName:
        status = get_job_status(job)
        if status.get("status") != "error":
            continue
        err = status.get("last_error") or ""
        if err != _INSIDER_BUILDER_STALE_ERROR:
            continue
        _write_job_status(
            job,
            {
                **status,
                "status": "idle",
                "last_error": None,
                "phase": None,
            },
        )
        logger.info("Cleared stale background job error for %s", job.value)


def _write_job_status(name: BackgroundJobName, payload: dict[str, Any]) -> None:
    payload = {
        **payload,
        "name": name.value,
        "label": payload.get("label") or job_label(name),
    }
    set_cached_ttl("bg_job", _job_meta_key(name), payload, 86400 * 7)


def update_job_progress(
    name: str | BackgroundJobName,
    *,
    phase: str | None = None,
    progress_completed: int | None = None,
    progress_total: int | None = None,
) -> None:
    """Update running job progress without changing terminal status."""
    job_name = BackgroundJobName(name) if isinstance(name, str) else name
    current = get_job_status(job_name)
    if current.get("status") != "running":
        return
    payload: dict[str, Any] = {**current}
    if phase is not None:
        payload["phase"] = phase
    if progress_completed is not None:
        payload["progress_completed"] = progress_completed
    if progress_total is not None:
        payload["progress_total"] = progress_total
    _write_job_status(job_name, payload)
    from trade_sentinel_api.services.job_events import publish_jobs_snapshot

    publish_jobs_snapshot()


def set_job_running(name: BackgroundJobName, *, phase: str | None = None) -> None:
    meta = JOB_META.get(name.value, {})
    _write_job_status(
        name,
        {
            "status": "running",
            "last_run_at": datetime.now(UTC).isoformat(),
            "last_error": None,
            "phase": phase or meta.get("description"),
            "progress_completed": None,
            "progress_total": None,
        },
    )
    from trade_sentinel_api.services.job_events import publish_job_started

    publish_job_started(name.value)


def set_job_result(name: BackgroundJobName, *, ok: bool, duration_ms: int, error: str | None) -> None:
    settings = get_settings()
    next_run = datetime.now(UTC) + timedelta(minutes=settings.background_refresh_interval_minutes)
    _write_job_status(
        name,
        {
            "status": "ok" if ok else "error",
            "last_run_at": datetime.now(UTC).isoformat(),
            "last_duration_ms": duration_ms,
            "last_error": error,
            "next_run_at": next_run.isoformat(),
            "phase": None,
            "progress_completed": None,
            "progress_total": None,
        },
    )
    from trade_sentinel_api.services.job_events import publish_job_finished

    publish_job_finished(
        name.value,
        status="ok" if ok else "error",
        last_error=error,
    )


def get_active_job_name() -> str | None:
    for job in BackgroundJobName:
        if get_job_status(job).get("status") == "running":
            return job.value
    return None


def list_job_statuses() -> list[dict[str, Any]]:
    return [get_job_status(job) for job in BackgroundJobName]


def market_screener_scanned_count() -> int:
    from trade_sentinel_api.services.digest import market_screener_cache_key

    settings = get_settings()
    universe = settings.market_screener_universe.strip().lower() or "sp500"
    cache_key = market_screener_cache_key(universe)
    cached = get_cached("market_screener", cache_key)
    if isinstance(cached, dict) and cached.get("rows"):
        return len(cached["rows"])
    return 0
