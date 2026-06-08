"""Merged from: test_market_screener.py"""

# --- from test_market_screener.py ---

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from trade_sentinel_api.main import app
from trade_sentinel_api.models.schemas import DigestTickerRow, ScreenerResult
from trade_sentinel_api.services.digest import (
    apply_screener_filters,
    resolve_screener_filters,
)

client = TestClient(app)


def _row(ticker: str, mos_pct: float | None, mos_label: str | None) -> DigestTickerRow:
    return DigestTickerRow(ticker=ticker, mos_pct=mos_pct, mos_label=mos_label)


def test_undervalued_preset_filters_by_mos_label():
    filters = resolve_screener_filters(preset="undervalued")
    assert filters.mos_label == "undervalued"

    rows = [
        _row("CHEAP", -12.0, "undervalued"),
        _row("RICH", 12.0, "overvalued"),
        _row("FAIR", 2.0, "fair"),
    ]
    matched = apply_screener_filters(rows, filters, preset="undervalued")
    assert [r.ticker for r in matched] == ["CHEAP"]


def test_undervalued_preset_does_not_use_inverted_mos_min():
    """Regression: old preset used mos_min=5 which selected overvalued names."""
    filters = resolve_screener_filters(preset="undervalued")
    assert filters.mos_min is None

    rows = [_row("RICH", 12.0, "overvalued")]
    matched = apply_screener_filters(rows, filters, preset="undervalued")
    assert matched == []


def test_undervalued_rank_most_discount_first():
    filters = resolve_screener_filters(preset="undervalued")
    rows = [
        _row("A", -5.0, "undervalued"),
        _row("B", -20.0, "undervalued"),
        _row("C", -12.0, "undervalued"),
    ]
    matched = apply_screener_filters(rows, filters, preset="undervalued")
    assert [r.ticker for r in matched] == ["B", "C", "A"]


@pytest.mark.asyncio
@patch(
    "trade_sentinel_api.services.sec.form13f.scan_institutional_conviction",
    new_callable=AsyncMock,
)
@patch(
    "trade_sentinel_api.services.digest.build_digest_today",
    new_callable=AsyncMock,
)
async def test_institutional_conviction_preset_filters_watchlist(mock_digest, mock_conviction):
    from trade_sentinel_api.models.schemas import (
        DigestToday,
        InstitutionalConvictionRow,
        InstitutionalConvictionScan,
    )
    from trade_sentinel_api.services.digest import screen_watchlist

    mock_digest.return_value = DigestToday(
        as_of=datetime.now(UTC),
        trading_date="2026-06-05",
        watchlist_name="default",
        tickers=[
            DigestTickerRow(ticker="AAPL"),
            DigestTickerRow(ticker="MSFT"),
            DigestTickerRow(ticker="XYZ"),
        ],
        digest_max_tickers=20,
    )
    mock_conviction.return_value = InstitutionalConvictionScan(
        as_of=datetime.now(UTC),
        rows=[
            InstitutionalConvictionRow(ticker="AAPL", filer_count=3, conviction_buy=True),
            InstitutionalConvictionRow(ticker="MSFT", filer_count=2, conviction_buy=True),
        ],
        data_available=True,
    )

    result = await screen_watchlist(preset="institutional_conviction")
    assert [r.ticker for r in result.rows] == ["AAPL", "MSFT"]
    mock_conviction.assert_awaited_once_with("watchlist")


@pytest.mark.asyncio
@patch(
    "trade_sentinel_api.services.sec.form13f.scan_institutional_conviction",
    new_callable=AsyncMock,
)
@patch(
    "trade_sentinel_api.services.digest._build_market_lite_rows",
    new_callable=AsyncMock,
)
async def test_market_institutional_conviction_preset(mock_batch, mock_conviction):
    from datetime import UTC, datetime

    from trade_sentinel_api.models.schemas import (
        DigestTickerRow,
        InstitutionalConvictionRow,
        InstitutionalConvictionScan,
    )
    from trade_sentinel_api.services.digest import screen_market_universe

    mock_batch.return_value = (
        [
            DigestTickerRow(ticker="AAPL"),
            DigestTickerRow(ticker="MSFT"),
            DigestTickerRow(ticker="XYZ"),
        ],
        503,
        datetime.now(UTC),
        False,
    )
    mock_conviction.return_value = InstitutionalConvictionScan(
        as_of=datetime.now(UTC),
        universe="sp500",
        rows=[
            InstitutionalConvictionRow(ticker="AAPL", filer_count=3, conviction_buy=True),
        ],
        data_available=True,
    )

    result = await screen_market_universe(universe="sp500", preset="institutional_conviction")
    assert result.universe == "sp500"
    assert [r.ticker for r in result.rows] == ["AAPL"]
    mock_conviction.assert_awaited_once_with("sp500")


def test_high_risk_preset_still_sorts_descending():
    filters = resolve_screener_filters(preset="high_risk")
    rows = [
        DigestTickerRow(ticker="A", mos_pct=5.0, top_warning="PRICE_ABOVE_FAIR_VALUE"),
        DigestTickerRow(ticker="B", mos_pct=15.0, top_warning="PRICE_ABOVE_FAIR_VALUE"),
    ]
    matched = apply_screener_filters(rows, filters, preset="high_risk")
    assert [r.ticker for r in matched] == ["B", "A"]


@patch(
    "trade_sentinel_api.routers.digest.screen_market_universe",
    new_callable=AsyncMock,
)
def test_screener_market_endpoint(mock_screen):
    mock_screen.return_value = ScreenerResult(
        as_of=datetime.now(UTC),
        universe="sp100",
        preset="undervalued",
        scanned_count=100,
        rows=[],
        empty_message="No tickers in this universe match these filters.",
    )
    r = client.get("/api/v1/screener/market?universe=sp100&preset=undervalued")
    assert r.status_code == 200
    body = r.json()
    assert body["universe"] == "sp100"
    assert body["scanned_count"] == 100
    mock_screen.assert_awaited_once()


@pytest.mark.asyncio
@patch(
    "trade_sentinel_api.services.scheduler.scheduling.schedule_market_screener_refresh",
)
@patch("trade_sentinel_api.services.digest.get_cached")
async def test_market_refresh_enqueues_background(mock_get_cached, mock_schedule):
    from trade_sentinel_api.services.digest import screen_market_universe

    mock_get_cached.return_value = {
        "rows": [_row("AAA", -10.0, "undervalued").model_dump(mode="json")],
        "cached_at": datetime.now(UTC).isoformat(),
    }

    with patch("trade_sentinel_api.services.digest.get_settings") as mock_settings:
        s = mock_settings.return_value
        s.background_jobs_enabled = True
        s.macro_trading_timezone = "America/New_York"
        result = await screen_market_universe(
            universe="sp500", preset="undervalued", refresh=True
        )

    mock_schedule.assert_called_once()
    assert result.stale is True
    assert len(result.rows) == 1


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.digest.build_lite_rows_batch", new_callable=AsyncMock)
async def test_screen_market_universe_applies_undervalued_filter(mock_batch):
    from trade_sentinel_api.services.digest import screen_market_universe

    rows = [
        _row("AAA", -15.0, "undervalued"),
        _row("BBB", 10.0, "overvalued"),
    ]
    mock_batch.return_value = (rows, datetime.now(UTC))

    result = await screen_market_universe(
        universe="sp500", preset="undervalued", refresh=True
    )
    assert result.universe == "sp500"
    assert len(result.rows) == 1
    assert result.rows[0].ticker == "AAA"
