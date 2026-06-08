"""Background job execution."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.cache import set_cached_ttl
from trade_sentinel_api.services.scheduler.status import set_job_result, set_job_running
from trade_sentinel_api.services.scheduler.types import (
    EDGAR_HEAVY_JOBS,
    YFINANCE_SCAN_JOBS,
    BackgroundJobName,
    set_batch_context,
)

logger = logging.getLogger(__name__)

_running = False


def is_batch_running() -> bool:
    return _running


async def run_job(name: BackgroundJobName) -> None:
    from trade_sentinel_api.services.cot_report import fetch_cot_report
    from trade_sentinel_api.services.digest import (
        build_digest_today,
        build_lite_rows_batch,
        market_screener_cache_key,
    )
    from trade_sentinel_api.services.sec.form13dg import build_activist_feed
    from trade_sentinel_api.services.sec.form13f import scan_institutional_conviction
    from trade_sentinel_api.services.smart_money.feed import build_smart_money_feed
    from trade_sentinel_api.services.smart_money.scan import (
        build_watchlist_insider_pulse,
        scan_insider_universe,
        scan_options_universe,
    )
    from trade_sentinel_api.services.universe import load_universe_tickers
    from trade_sentinel_api.services.volume import scan_volume_universe

    started = datetime.now(UTC)
    set_job_running(name)
    error: str | None = None
    try:
        if name == BackgroundJobName.DIGEST:
            await build_digest_today("default", refresh=True, from_background=True)
        elif name == BackgroundJobName.MARKET_SCREENER:
            settings = get_settings()
            universe = settings.market_screener_universe.strip().lower() or "sp500"
            tickers = load_universe_tickers(universe)
            cache_key = market_screener_cache_key(universe)
            ttl = settings.market_screener_cache_minutes * 60
            await build_lite_rows_batch(
                tickers,
                refresh=True,
                cache_prefix="market_screener",
                cache_key=cache_key,
                cache_ttl_seconds=ttl,
                max_workers=settings.background_scan_workers,
                include_insider=False,
            )
        elif name == BackgroundJobName.SMART_MONEY_FEED:
            await build_smart_money_feed(days=1, refresh=True)
        elif name == BackgroundJobName.WATCHLIST_PULSE:
            await build_watchlist_insider_pulse("default")
        elif name == BackgroundJobName.OPTIONS_WATCHLIST:
            await scan_options_universe("watchlist", "default", refresh=True)
        elif name == BackgroundJobName.OPTIONS_SP100:
            await scan_options_universe("sp100", "default", refresh=True)
        elif name == BackgroundJobName.OPTIONS_SP500:
            settings = get_settings()
            proactive = settings.smart_money_proactive_universe.strip().lower() or "sp500"
            await scan_options_universe(proactive, "default", refresh=True)
        elif name == BackgroundJobName.VOLUME_WATCHLIST:
            await scan_volume_universe("watchlist", "default", refresh=True)
        elif name == BackgroundJobName.VOLUME_SP100:
            await scan_volume_universe("sp100", refresh=True)
        elif name == BackgroundJobName.VOLUME_SP500:
            await scan_volume_universe("sp500", refresh=True)
        elif name == BackgroundJobName.INSIDER_SP500:
            await scan_insider_universe("sp500", refresh=True)
        elif name == BackgroundJobName.INSTITUTIONAL_CONVICTION:
            await scan_institutional_conviction("sp500", refresh=True)
        elif name == BackgroundJobName.ACTIVIST_FEED:
            await build_activist_feed(days=30)
        elif name == BackgroundJobName.COT_MACRO:
            await fetch_cot_report()
        elif name == BackgroundJobName.EDGAR_REGISTRY_WARM:
            settings = get_settings()
            if settings.edgar_registry_warm_enabled:
                await _warm_edgar_registry_forms()
        elif name == BackgroundJobName.SEC_13F_BULK_INGEST:
            from trade_sentinel_api.services.sec.form13f_bulk import ingest_latest_13f_quarter

            await asyncio.to_thread(ingest_latest_13f_quarter)
        elif name == BackgroundJobName.SEC_NPORT_BULK_INGEST:
            from trade_sentinel_api.services.sec.nport_bulk import ingest_latest_nport_quarter

            await asyncio.to_thread(ingest_latest_nport_quarter)
        elif name == BackgroundJobName.CONGRESSIONAL_TRADES:
            from trade_sentinel_api.services.congressional_trades import build_congressional_feed

            await build_congressional_feed(refresh=True)
        elif name == BackgroundJobName.FINRA_SHORT_VOLUME:
            from trade_sentinel_api.services.finra_short_volume import compute_dix_proxy

            await asyncio.to_thread(compute_dix_proxy, "SPY")
        elif name == BackgroundJobName.GEX_SNAPSHOT:
            from trade_sentinel_api.services.microstructure import fetch_microstructure

            await fetch_microstructure("SPY")
    except Exception as exc:
        error = str(exc)
        logger.exception("Background job %s failed: %s", name.value, exc)
    duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    set_job_result(name, ok=error is None, duration_ms=duration_ms, error=error)


_run_job = run_job


async def _warm_edgar_registry_forms() -> None:
    from trade_sentinel_api.services.sec.adapter import fetch_current
    from trade_sentinel_api.services.sec.registry import (
        get_filing_spec,
        resolve_edgar_enabled_forms,
    )

    settings = get_settings()
    forms = resolve_edgar_enabled_forms(settings.edgar_enabled_forms)
    ttl = settings.edgar_registry_cache_minutes * 60
    for form in forms:
        spec = get_filing_spec(form)
        if spec is None:
            continue
        cache_key = f"{spec.key}:25"
        try:
            filings = await asyncio.to_thread(fetch_current, spec.key, max_entries=25)
            set_cached_ttl(
                "edgar_current_filings",
                cache_key,
                {
                    "as_of": datetime.now(UTC).isoformat(),
                    "form": spec.key,
                    "count": len(filings),
                    "partial": False,
                },
                ttl,
            )
        except Exception as exc:
            logger.debug("Edgar registry warm failed for %s: %s", form, exc)


async def run_all_jobs(*, reason: str = "manual") -> None:
    global _running
    if _running:
        logger.info("Background jobs already running — skip (%s)", reason)
        return
    _running = True
    logger.info("Background jobs starting (%s)", reason)
    settings = get_settings()
    gap = settings.sec_job_gap_seconds
    jobs = [
        job
        for job in BackgroundJobName
        if (job != BackgroundJobName.EDGAR_REGISTRY_WARM or settings.edgar_registry_warm_enabled)
        and (job != BackgroundJobName.SEC_NPORT_BULK_INGEST or settings.sec_bulk_nport_background_enabled)
    ]
    set_batch_context(position=0, total=len(jobs), reason=reason)
    try:
        for idx, job in enumerate(jobs, start=1):
            set_batch_context(position=idx)
            if job in YFINANCE_SCAN_JOBS and gap > 0:
                cooldown = settings.yfinance_job_cooldown_seconds
                if cooldown > 0:
                    await asyncio.sleep(cooldown)
            await run_job(job)
            if job in EDGAR_HEAVY_JOBS and gap > 0:
                await asyncio.sleep(gap)
    finally:
        _running = False
        set_batch_context(position=0, total=0, reason="")
        logger.info("Background jobs finished (%s)", reason)


async def run_watchlist_jobs(*, reason: str = "watchlist") -> None:
    global _running
    if _running:
        return
    _running = True
    logger.info("Watchlist background jobs starting (%s)", reason)
    try:
        for job in (
            BackgroundJobName.DIGEST,
            BackgroundJobName.WATCHLIST_PULSE,
            BackgroundJobName.OPTIONS_WATCHLIST,
        ):
            await run_job(job)
    finally:
        _running = False


async def run_market_screener_job(*, reason: str = "enqueue") -> None:
    global _running
    if _running:
        return
    _running = True
    try:
        await run_job(BackgroundJobName.MARKET_SCREENER)
    finally:
        _running = False
