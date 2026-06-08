import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from trade_sentinel_api.main import app
from trade_sentinel_api.models.schemas import (
    DigestTickerRow,
    FundamentalsSnapshot,
    ValuationAssessment,
)
from trade_sentinel_api.services.scheduler import schedule_watchlist_refresh
from trade_sentinel_api.services.digest import (
    apply_screener_filters,
    build_lite_row_sync,
    resolve_screener_filters,
)
from trade_sentinel_api.services.earnings import EarningsSnapshot

client = TestClient(app)


def _row(ticker: str, mos_pct: float | None, mos_label: str | None) -> DigestTickerRow:
    return DigestTickerRow(ticker=ticker, mos_pct=mos_pct, mos_label=mos_label)


@patch("trade_sentinel_api.services.digest.earnings_from_bundle")
@patch("trade_sentinel_api.services.digest.resolve_ticker_valuation_sync")
@patch("trade_sentinel_api.services.digest.fundamentals_from_bundle")
@patch("trade_sentinel_api.services.digest.market_from_bundle")
@patch("trade_sentinel_api.services.digest.load_ticker_bundle_sync")
def test_build_lite_row_sync(mock_load, mock_mkt, mock_fund, mock_val_sync, mock_earn):
    from trade_sentinel_api.services.yfinance_bundle import TickerDataBundle

    mock_load.return_value = TickerDataBundle(symbol="AAA")
    mock_mkt.return_value = {"price": 100.0, "change_pct": 1.2}
    mock_fund.return_value = FundamentalsSnapshot(data_available=True, pe_forward=20)
    mock_val_sync.return_value = (
        FundamentalsSnapshot(data_available=True, pe_forward=20),
        ValuationAssessment(
            data_available=True, fair_value_mid=110, mos_pct=-9.0, mos_label="undervalued"
        ),
    )
    mock_earn.return_value = EarningsSnapshot(data_available=True, days_until=5)

    row = build_lite_row_sync("AAA", {}, include_insider=False)
    assert row.ticker == "AAA"
    assert row.mos_label == "undervalued"
    assert row.earnings_days == 5


def test_jobs_status_endpoint():
    r = client.get("/api/v1/jobs/status")
    assert r.status_code == 200
    body = r.json()
    assert "jobs" in body
    assert body["background_jobs_enabled"] is False


def test_health_includes_ready_and_warming():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert "warming" in body


@pytest.mark.asyncio
async def test_start_background_scheduler_returns_before_jobs_finish(monkeypatch):
    from trade_sentinel_api.config import get_settings
    from trade_sentinel_api.services import scheduler as sched

    monkeypatch.setenv("BACKGROUND_JOBS_ENABLED", "true")
    monkeypatch.setenv("BACKGROUND_STARTUP_WARM", "true")
    get_settings.cache_clear()

    job_started = asyncio.Event()

    async def slow_run_all_jobs(**_kwargs):
        job_started.set()
        await asyncio.sleep(30)

    sched._interval_task = None
    with patch(
        "trade_sentinel_api.services.scheduler.lifecycle.run_all_jobs",
        side_effect=slow_run_all_jobs,
    ):
        with patch(
            "trade_sentinel_api.services.scheduler.lifecycle.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=True,
        ):
            t0 = time.monotonic()
            await sched.start_background_scheduler()
            elapsed = time.monotonic() - t0
            assert elapsed < 2.0
            await asyncio.sleep(0.05)
            assert job_started.is_set()
    if sched._interval_task:
        sched._interval_task.cancel()
        try:
            await sched._interval_task
        except asyncio.CancelledError:
            pass
        sched._interval_task = None
    get_settings.cache_clear()


def test_health_responds_quickly_with_background_jobs_enabled(monkeypatch):
    from trade_sentinel_api.config import get_settings

    monkeypatch.setenv("BACKGROUND_JOBS_ENABLED", "true")
    monkeypatch.setenv("BACKGROUND_STARTUP_WARM", "true")
    get_settings.cache_clear()

    async def slow_run_all_jobs(**_kwargs):
        await asyncio.sleep(30)

    with patch(
        "trade_sentinel_api.services.scheduler.lifecycle.run_all_jobs",
        side_effect=slow_run_all_jobs,
    ):
        with patch(
            "trade_sentinel_api.services.scheduler.lifecycle.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with TestClient(app) as quick_client:
                t0 = time.monotonic()
                r = quick_client.get("/health")
                elapsed = time.monotonic() - t0
                assert elapsed < 3.0
                assert r.status_code == 200
                body = r.json()
                assert body["ready"] is True
                assert body["background_jobs_enabled"] is True
    get_settings.cache_clear()


@patch("trade_sentinel_api.routers.jobs.run_all_jobs", new_callable=AsyncMock)
def test_jobs_refresh_endpoint(mock_run):
    r = client.post("/api/v1/jobs/refresh?scope=all")
    assert r.status_code == 200
    mock_run.assert_awaited_once()


def test_schedule_watchlist_refresh_queues_name():
    from trade_sentinel_api.services import scheduler as sched

    sched._pending_watchlist.clear()
    schedule_watchlist_refresh("default")
    assert "default" in sched._pending_watchlist


def test_sp500_universe_loader():
    from trade_sentinel_api.services.universe import load_sp500_tickers

    tickers = load_sp500_tickers()
    assert len(tickers) > 400
    assert "AAPL" in tickers


def test_background_job_names_include_sp500_scans():
    from trade_sentinel_api.services.scheduler import BackgroundJobName

    names = {j.value for j in BackgroundJobName}
    assert "options_sp500" in names
    assert "volume_sp500" in names
    assert "insider_sp500" in names
    assert "activist_feed" in names


def test_undervalued_filter_regression():
    filters = resolve_screener_filters(preset="undervalued")
    rows = [_row("CHEAP", -12.0, "undervalued"), _row("RICH", 12.0, "overvalued")]
    matched = apply_screener_filters(rows, filters, preset="undervalued")
    assert [r.ticker for r in matched] == ["CHEAP"]


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.digest.set_cached_ttl")
@patch("trade_sentinel_api.services.digest.get_cached", return_value=None)
@patch("trade_sentinel_api.services.digest.get_daily_macro_bundle", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.yfinance_bundle.prefetch_hist_chunk", return_value={})
@patch("trade_sentinel_api.services.digest.build_lite_row_sync")
async def test_build_lite_rows_batch_chunks(
    mock_row, mock_prefetch, mock_macro, _get_cached, _set_cached
):
    from concurrent.futures import ThreadPoolExecutor

    from trade_sentinel_api.services.digest import build_lite_rows_batch

    mock_macro.return_value = {}
    mock_row.side_effect = lambda sym, *_a, **_k: DigestTickerRow(ticker=sym, price=1.0)

    tickers = [f"T{i}" for i in range(30)]
    with patch(
        "trade_sentinel_api.services.digest.get_scan_executor",
        return_value=ThreadPoolExecutor(max_workers=2),
    ):
        with patch("trade_sentinel_api.services.digest.get_settings") as mock_settings:
            s = mock_settings.return_value
            s.yfinance_batch_chunk_size = 25
            s.yfinance_chunk_delay_seconds = 0
            s.macro_trading_timezone = "America/New_York"
            rows, _ = await build_lite_rows_batch(
                tickers,
                refresh=True,
                cache_prefix="market_screener",
                cache_key="test",
                cache_ttl_seconds=60,
                max_workers=4,
            )

    assert len(rows) == 30
    assert mock_prefetch.call_count == 2


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.job_events.after_chunk_cached")
@patch("trade_sentinel_api.services.digest.set_cached_ttl")
@patch("trade_sentinel_api.services.digest.get_cached", return_value=None)
@patch("trade_sentinel_api.services.digest.get_daily_macro_bundle", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.yfinance_bundle.prefetch_hist_chunk", return_value={})
@patch("trade_sentinel_api.services.digest.build_lite_row_sync")
async def test_build_lite_rows_batch_partial_cache(
    mock_row, mock_prefetch, mock_macro, _get_cached, _set_cached, mock_after_chunk
):
    from concurrent.futures import ThreadPoolExecutor

    from trade_sentinel_api.services.digest import build_lite_rows_batch

    mock_macro.return_value = {}
    mock_row.side_effect = lambda sym, *_a, **_k: DigestTickerRow(ticker=sym, price=1.0)

    tickers = ["A", "B"]
    with patch(
        "trade_sentinel_api.services.digest.get_scan_executor",
        return_value=ThreadPoolExecutor(max_workers=2),
    ):
        with patch("trade_sentinel_api.services.digest.get_settings") as mock_settings:
            s = mock_settings.return_value
            s.yfinance_batch_chunk_size = 1
            s.yfinance_chunk_delay_seconds = 0
            await build_lite_rows_batch(
                tickers,
                refresh=True,
                cache_prefix="market_screener",
                cache_key="2026-01-01:sp500:lite",
                cache_ttl_seconds=60,
                max_workers=2,
            )

    assert mock_after_chunk.call_count == 2


def test_chunk_symbols_helper():
    from trade_sentinel_api.services.yfinance_bundle import _chunk_symbols

    chunks = _chunk_symbols([f"T{i}" for i in range(30)], 25)
    assert len(chunks) == 2
    assert len(chunks[0]) == 25
    assert len(chunks[1]) == 5
