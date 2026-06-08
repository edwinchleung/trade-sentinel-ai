from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import BackgroundJobsStatusResponse, BackgroundJobStatus
from trade_sentinel_api.services.scheduler import (
    BackgroundJobName,
    get_active_job_name,
    get_batch_context,
    is_background_warming,
    list_job_statuses,
    market_screener_scanned_count,
    run_all_jobs,
    run_job,
    run_watchlist_jobs,
    schedule_digest_refresh,
    schedule_market_screener_refresh,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _parse_job(payload: dict) -> BackgroundJobStatus:
    last_run = payload.get("last_run_at")
    next_run = payload.get("next_run_at")
    return BackgroundJobStatus(
        name=str(payload.get("name", "")),
        status=payload.get("status", "idle"),
        label=payload.get("label"),
        phase=payload.get("phase"),
        progress_completed=payload.get("progress_completed"),
        progress_total=payload.get("progress_total"),
        last_run_at=datetime.fromisoformat(last_run) if last_run else None,
        last_duration_ms=payload.get("last_duration_ms"),
        last_error=payload.get("last_error"),
        next_run_at=datetime.fromisoformat(next_run) if next_run else None,
    )


def _jobs_response() -> BackgroundJobsStatusResponse:
    settings = get_settings()
    batch = get_batch_context()
    jobs = [_parse_job(j) for j in list_job_statuses()]
    return BackgroundJobsStatusResponse(
        as_of=datetime.now(UTC),
        jobs=jobs,
        market_screener_scanned_count=market_screener_scanned_count(),
        background_jobs_enabled=settings.background_jobs_enabled,
        warming=is_background_warming(),
        active_job=get_active_job_name(),
        batch_position=batch.get("position") or None,
        batch_total=batch.get("total") or None,
    )


@router.get("/status", response_model=BackgroundJobsStatusResponse)
async def jobs_status() -> BackgroundJobsStatusResponse:
    return _jobs_response()


@router.post("/retry/{job_name}", response_model=BackgroundJobsStatusResponse)
async def retry_job(
    job_name: str,
    background_tasks: BackgroundTasks,
) -> BackgroundJobsStatusResponse:
    try:
        job = BackgroundJobName(job_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_name}") from exc
    background_tasks.add_task(run_job, job)
    return _jobs_response()


@router.post("/refresh", response_model=BackgroundJobsStatusResponse)
async def jobs_refresh(
    background_tasks: BackgroundTasks,
    scope: str = Query(
        "all",
        pattern="^(all|digest|market|smart_money|watchlist|sec_bulk_13f|sec_bulk_nport)$",
    ),
) -> BackgroundJobsStatusResponse:
    if scope == "all":
        background_tasks.add_task(run_all_jobs, reason="manual")
    elif scope == "digest":
        schedule_digest_refresh()
    elif scope == "market":
        schedule_market_screener_refresh()
    elif scope == "smart_money":

        async def _smart_money():
            await run_job(BackgroundJobName.SMART_MONEY_FEED)
            await run_job(BackgroundJobName.OPTIONS_SP500)
            await run_job(BackgroundJobName.VOLUME_SP500)
            await run_job(BackgroundJobName.INSIDER_SP500)
            await run_job(BackgroundJobName.INSTITUTIONAL_CONVICTION)
            await run_job(BackgroundJobName.ACTIVIST_FEED)
            await run_job(BackgroundJobName.CONGRESSIONAL_TRADES)
            await run_job(BackgroundJobName.GEX_SNAPSHOT)

        background_tasks.add_task(_smart_money)
    elif scope == "sec_bulk_13f":
        background_tasks.add_task(run_job, BackgroundJobName.SEC_13F_BULK_INGEST)
    elif scope == "sec_bulk_nport":
        background_tasks.add_task(run_job, BackgroundJobName.SEC_NPORT_BULK_INGEST)
    elif scope == "watchlist":
        background_tasks.add_task(run_watchlist_jobs, reason="manual")
    return _jobs_response()
