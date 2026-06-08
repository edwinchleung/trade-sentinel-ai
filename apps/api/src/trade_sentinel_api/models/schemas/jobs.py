from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BackgroundJobStatus(BaseModel):
    name: str
    status: Literal["idle", "running", "ok", "error"] = "idle"
    label: str | None = None
    phase: str | None = None
    progress_completed: int | None = None
    progress_total: int | None = None
    last_run_at: datetime | None = None
    last_duration_ms: int | None = None
    last_error: str | None = None
    next_run_at: datetime | None = None


class BackgroundJobsStatusResponse(BaseModel):
    as_of: datetime
    jobs: list[BackgroundJobStatus] = Field(default_factory=list)
    market_screener_scanned_count: int = 0
    background_jobs_enabled: bool = True
    warming: bool = False
    active_job: str | None = None
    batch_position: int | None = None
    batch_total: int | None = None

