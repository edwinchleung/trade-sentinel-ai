import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.routers import (
    context,
    digest,
    filings,
    institutional,
    jobs,
    journal,
    macro,
    risk,
    smart_money,
    watchlists,
    ws,
)
from trade_sentinel_api.services.sec.bootstrap import bootstrap_edgartools
from trade_sentinel_api.services.llm import llm_is_configured
from trade_sentinel_api.services.scheduler import (
    clear_stale_job_errors,
    is_background_warming,
    start_background_scheduler,
    stop_background_scheduler,
)
from trade_sentinel_api.services.yfinance_logging import configure_yfinance_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    bootstrap_edgartools()
    configure_yfinance_logging(quiet=settings.yfinance_quiet_logs)
    clear_stale_job_errors()
    await start_background_scheduler()
    yield
    await stop_background_scheduler()


app = FastAPI(
    title="TradeSentinel AI API",
    version="0.1.0",
    description="Rationality co-pilot for retail investors",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(context.router, prefix=API_PREFIX)
app.include_router(risk.router, prefix=API_PREFIX)
app.include_router(macro.router, prefix=API_PREFIX)
app.include_router(institutional.router, prefix=API_PREFIX)
app.include_router(journal.router, prefix=API_PREFIX)
app.include_router(watchlists.router, prefix=API_PREFIX)
app.include_router(digest.router, prefix=API_PREFIX)
app.include_router(smart_money.router, prefix=API_PREFIX)
app.include_router(filings.router, prefix=API_PREFIX)
app.include_router(jobs.router, prefix=API_PREFIX)
app.include_router(ws.router, prefix=API_PREFIX)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health() -> dict:
    s = get_settings()
    warming = s.background_jobs_enabled and is_background_warming()
    return {
        "status": "ok",
        "service": "trade-sentinel-api",
        "llm_provider": s.llm_provider_normalized,
        "llm_configured": llm_is_configured(),
        "api_version": "0.1.0",
        "background_jobs_enabled": s.background_jobs_enabled,
        "ready": True,
        "warming": warming,
    }
