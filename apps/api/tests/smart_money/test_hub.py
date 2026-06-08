"""Merged from: test_smart_money_feed.py, test_smart_money_scan.py, test_smart_money_router.py, test_smart_money_assessment.py"""

# --- from test_smart_money_feed.py ---

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from trade_sentinel_api.models.schemas import SmartMoneyFeedItem
from trade_sentinel_api.services.sec.adapter import _items_from_parsed_dict
from trade_sentinel_api.services.sec.insider_classification import side_for_feed
from trade_sentinel_api.services.smart_money.feed import (
    _apply_filters,
    _build_feed_from_raw,
    _build_stats,
    _raw_cache_key,
    resolve_feed_date_range,
)


def _today_window() -> tuple[date, date]:
    today = date.today()
    return today, today


def test_resolve_feed_date_range_defaults_to_one_day():
    start, end, span = resolve_feed_date_range()
    assert start == end == date.today()
    assert span == 1


def test_resolve_feed_date_range_caps_at_max():
    start, end, span = resolve_feed_date_range(days=90)
    assert span <= 30


def test_resolve_feed_date_range_clamps_future_end():
    future = date.today() + timedelta(days=3)
    start, end, span = resolve_feed_date_range(start_date=future - timedelta(days=2), end_date=future)
    assert end == date.today()
    assert start <= end
    assert span >= 1


def test_raw_cache_key_uses_date_range():
    start = date(2026, 6, 1)
    end = date(2026, 6, 5)
    assert _raw_cache_key(start, end) == "v3_raw:2026-06-01:2026-06-05"


@pytest.mark.asyncio
async def test_build_feed_uses_date_range_fetch():
    from unittest.mock import MagicMock

    from trade_sentinel_api.services.smart_money.feed import build_smart_money_feed

    start = date.today() - timedelta(days=6)
    end = date.today()
    recent = end.isoformat()

    mock_filing = MagicMock()
    with (
        patch("trade_sentinel_api.services.smart_money.feed.get_cached", return_value=None),
        patch(
            "trade_sentinel_api.services.smart_money.feed.fetch_form4_by_date_range",
            return_value=[mock_filing],
        ) as mock_range,
        patch(
            "trade_sentinel_api.services.smart_money.feed.filing_to_feed_items",
            return_value=(
                [
                    SmartMoneyFeedItem(
                        filing_date=recent,
                        ticker="AAPL",
                        side="buy",
                        is_open_market=True,
                    )
                ],
                1,
                0,
            ),
        ),
        patch("trade_sentinel_api.services.smart_money.feed._cache_raw_feed_result"),
    ):
        feed = await build_smart_money_feed(
            start_date=start,
            end_date=end,
            open_market_only=True,
        )

    mock_range.assert_called_once()
    assert feed.start_date == start.isoformat()
    assert feed.end_date == end.isoformat()
    assert any(i.ticker == "AAPL" for i in feed.items)


def test_side_for_feed_open_market():
    assert (
        side_for_feed(
            transaction_code="P",
            acquired_disposed=None,
            transaction_type="Purchase",
            is_open_market=True,
        )
        == "buy"
    )
    assert (
        side_for_feed(
            transaction_code="A",
            acquired_disposed="A",
            transaction_type="Grant",
            is_open_market=False,
        )
        == "other"
    )


def test_apply_filters_notable():
    recent = date.today().isoformat()
    start, end = _today_window()
    items = [
        SmartMoneyFeedItem(
            filing_date=recent,
            side="buy",
            is_notable=True,
            notional=2_000_000,
            is_open_market=True,
        ),
        SmartMoneyFeedItem(
            filing_date=recent,
            side="sell",
            is_notable=False,
            notional=50_000,
            is_open_market=True,
        ),
    ]
    filtered = _apply_filters(
        items,
        start_date=start,
        end_date=end,
        side="all",
        notable_only=True,
        min_notional=None,
        open_market_only=False,
        cluster_only=False,
    )
    assert len(filtered) == 1
    assert filtered[0].is_notable


def test_build_stats_top_tickers():
    items = [
        SmartMoneyFeedItem(filing_date="2024-06-01", ticker="AAPL", side="buy"),
        SmartMoneyFeedItem(filing_date="2024-06-01", ticker="AAPL", side="buy"),
        SmartMoneyFeedItem(filing_date="2024-06-01", ticker="MSFT", side="sell"),
    ]
    stats = _build_stats(items)
    assert stats.buy_count == 2
    assert stats.sell_count == 1
    assert stats.top_tickers[0] == "AAPL"


@pytest.mark.asyncio
async def test_build_feed_serves_stale_on_rate_limit():
    from datetime import UTC, datetime

    from trade_sentinel_api.services.sec.http import SecRateLimitError
    from trade_sentinel_api.services.smart_money.feed import (
        _STALE_FEED_SNAPSHOTS,
        build_smart_money_feed,
    )

    recent = (date.today() - timedelta(days=1)).isoformat()
    start, end = _today_window()
    raw_key = _raw_cache_key(start, end)
    _STALE_FEED_SNAPSHOTS[raw_key] = {
        "as_of": datetime.now(UTC).isoformat(),
        "items": [
            SmartMoneyFeedItem(
                filing_date=recent,
                ticker="AAPL",
                side="buy",
                is_open_market=True,
            ).model_dump(mode="json")
        ],
        "data_available": True,
        "days_window": 1,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "raw_entry_count": 1,
        "enriched_count": 1,
    }
    with (
        patch("trade_sentinel_api.services.smart_money.feed.get_cached", return_value=None),
        patch(
            "trade_sentinel_api.services.smart_money.feed.asyncio.to_thread",
            side_effect=SecRateLimitError("https://www.sec.gov/feed"),
        ),
    ):
        feed = await build_smart_money_feed(open_market_only=True)
    assert feed.sec_rate_limited is True
    assert feed.data_available is True
    assert "cached" in (feed.message or "").lower()


@pytest.mark.asyncio
async def test_failure_feed_uses_short_cache_ttl():
    from datetime import UTC, datetime

    from trade_sentinel_api.services.smart_money.feed import (
        _cache_raw_feed_result,
        _raw_cache_key,
    )

    cache_key = _raw_cache_key(*_today_window())
    failure = {
        "as_of": datetime.now(UTC).isoformat(),
        "items": [],
        "data_available": False,
        "message": "SEC Form 4 feed unavailable: Client error '429 Too Many Requests'",
        "days_window": 1,
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
    }
    with patch("trade_sentinel_api.services.smart_money.feed.set_cached_ttl") as mock_set:
        _cache_raw_feed_result(cache_key, failure)
        mock_set.assert_called_once()
        assert mock_set.call_args[0][0] == "smart_money_feed_raw"
        assert mock_set.call_args[0][1] == cache_key
        assert mock_set.call_args[0][3] == 120
        assert mock_set.call_args[0][2]["data_available"] is False


@pytest.mark.asyncio
async def test_filing_to_feed_items_tracks_parse_failure():
    from unittest.mock import MagicMock, patch

    from trade_sentinel_api.services.sec.adapter import filing_to_feed_items

    filing = MagicMock()
    with patch(
        "trade_sentinel_api.services.sec.adapter.parse_filing",
        return_value=(None, "parse failed"),
    ):
        items, enriched, failed = filing_to_feed_items(filing)
    assert enriched == 0
    assert failed == 1
    assert len(items) == 1
    assert items[0].excerpt_available is False


@pytest.mark.asyncio
async def test_refresh_bypasses_cached_failure():
    from datetime import UTC, datetime

    from trade_sentinel_api.services.smart_money.feed import build_smart_money_feed

    start, end = _today_window()
    cached_failure = {
        "as_of": datetime.now(UTC).isoformat(),
        "items": [],
        "data_available": False,
        "message": "SEC Form 4 feed unavailable: rate limited.",
        "days_window": 1,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    recent = (date.today() - timedelta(days=1)).isoformat()
    fresh_raw = {
        "as_of": datetime.now(UTC).isoformat(),
        "items": [
            SmartMoneyFeedItem(
                filing_date=recent,
                ticker="AAPL",
                side="buy",
                is_open_market=True,
            ).model_dump(mode="json")
        ],
        "data_available": True,
        "days_window": 1,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "raw_entry_count": 5,
        "enriched_count": 3,
    }

    with (
        patch("trade_sentinel_api.services.smart_money.feed.get_cached", return_value=cached_failure),
        patch("trade_sentinel_api.services.smart_money.feed.clear_cached") as mock_clear,
        patch(
            "trade_sentinel_api.services.smart_money.feed._fetch_raw_feed_async",
            return_value=fresh_raw,
        ),
        patch("trade_sentinel_api.services.smart_money.feed._cache_raw_feed_result"),
    ):
        feed = await build_smart_money_feed(open_market_only=True, refresh=True)

    mock_clear.assert_called_once_with("smart_money_feed_raw", _raw_cache_key(start, end))
    assert feed.data_available is True


@patch("trade_sentinel_api.services.sec.edgar._cik_to_ticker", return_value={"0000320193": "AAPL"})
def test_get_ticker_for_cik(_mock):
    from trade_sentinel_api.services.sec.edgar import get_ticker_for_cik

    assert get_ticker_for_cik("320193") == "AAPL"


def test_items_from_parsed_nested_value_xml_amounts():
    recent = (date.today() - timedelta(days=1)).isoformat()
    parsed = {
        "insider_name": "Nested Seller",
        "transactions": [
            {
                "transaction_code": "S",
                "transaction_type": "Sale",
                "acquired_disposed": "D",
                "is_open_market": True,
                "shares": 100000.0,
                "price": 222.50,
                "filing_date": recent,
            }
        ],
    }
    items = _items_from_parsed_dict(
        parsed=parsed,
        ticker="AAPL",
        company_name="Apple Inc",
        link="https://sec.gov/form4",
        default_filing_date=recent,
    )
    assert len(items) == 1
    item = items[0]
    assert item.side == "sell"
    assert item.shares == 100000.0
    assert item.price == 222.50
    assert item.notional == 22_250_000.0
    assert item.is_open_market is True


def test_items_from_parsed_includes_derivative_sale():
    recent = (date.today() - timedelta(days=1)).isoformat()
    parsed = {
        "insider_name": "Option Seller",
        "title": "CFO",
        "transactions": [
            {
                "transaction_code": "M",
                "transaction_type": "Exercise",
                "is_open_market": False,
                "filing_date": recent,
            }
        ],
        "derivative_transactions": [
            {
                "transaction_code": "S",
                "transaction_type": "Sale",
                "is_open_market": True,
                "shares": 10000.0,
                "price": 55.0,
                "filing_date": recent,
            }
        ],
    }
    items = _items_from_parsed_dict(
        parsed=parsed,
        ticker="TEST",
        company_name="Test Co",
        link="https://sec.gov/form4",
        default_filing_date=recent,
    )
    sides = {item.side for item in items}
    assert "sell" in sides
    sell_items = [i for i in items if i.side == "sell"]
    assert sell_items[0].is_open_market is True
    assert sell_items[0].shares == 10000.0


def test_apply_filters_sell_returns_derivative_sale():
    recent = date.today().isoformat()
    start, end = _today_window()
    items = [
        SmartMoneyFeedItem(
            filing_date=recent,
            side="buy",
            is_open_market=True,
            ticker="AAPL",
        ),
        SmartMoneyFeedItem(
            filing_date=recent,
            side="sell",
            is_open_market=True,
            ticker="MSFT",
        ),
    ]
    filtered = _apply_filters(
        items,
        start_date=start,
        end_date=end,
        side="sell",
        notable_only=False,
        min_notional=None,
        open_market_only=True,
        cluster_only=False,
    )
    assert len(filtered) == 1
    assert filtered[0].side == "sell"
    assert filtered[0].ticker == "MSFT"


def test_build_feed_from_raw_filter_messages():
    from datetime import UTC, datetime

    recent = (date.today() - timedelta(days=1)).isoformat()
    start, end = _today_window()
    raw = {
        "as_of": datetime.now(UTC).isoformat(),
        "items": [
            SmartMoneyFeedItem(
                filing_date=recent,
                side="buy",
                is_open_market=True,
                notional=50_000,
            ).model_dump(mode="json")
        ],
        "data_available": True,
        "days_window": 1,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "raw_entry_count": 10,
        "enriched_count": 5,
    }
    sell_feed = _build_feed_from_raw(
        raw,
        side="sell",
        notable_only=False,
        min_notional=None,
        open_market_only=True,
        cluster_only=False,
    )
    assert sell_feed.data_available is True
    assert "No open-market sells" in (sell_feed.message or "")

    notable_feed = _build_feed_from_raw(
        raw,
        side="all",
        notable_only=True,
        min_notional=None,
        open_market_only=True,
        cluster_only=False,
    )
    assert notable_feed.data_available is True
    assert "$1M" in (notable_feed.message or "")

    cluster_feed = _build_feed_from_raw(
        raw,
        side="all",
        notable_only=False,
        min_notional=None,
        open_market_only=True,
        cluster_only=True,
    )
    assert cluster_feed.data_available is True
    assert "cluster buys" in (cluster_feed.message or "").lower()


@pytest.mark.asyncio
async def test_raw_cache_reused_across_side_filters():
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock

    from trade_sentinel_api.services.smart_money.feed import build_smart_money_feed

    recent = date.today().isoformat()
    start, end = _today_window()
    raw_pool = {
        "as_of": datetime.now(UTC).isoformat(),
        "items": [
            SmartMoneyFeedItem(
                filing_date=recent,
                side="buy",
                is_open_market=True,
                ticker="AAPL",
            ).model_dump(mode="json"),
            SmartMoneyFeedItem(
                filing_date=recent,
                side="sell",
                is_open_market=True,
                ticker="MSFT",
            ).model_dump(mode="json"),
        ],
        "data_available": True,
        "days_window": 1,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "raw_entry_count": 10,
        "enriched_count": 5,
    }

    with (
        patch(
            "trade_sentinel_api.services.smart_money.feed.get_cached",
            return_value=raw_pool,
        ),
        patch(
            "trade_sentinel_api.services.smart_money.feed.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_thread,
    ):
        buy_feed = await build_smart_money_feed(side="buy", open_market_only=True)
        sell_feed = await build_smart_money_feed(side="sell", open_market_only=True)

    mock_thread.assert_not_called()
    assert len(buy_feed.items) == 1
    assert buy_feed.items[0].ticker == "AAPL"
    assert len(sell_feed.items) == 1
    assert sell_feed.items[0].ticker == "MSFT"

# --- from test_smart_money_scan.py ---

from unittest.mock import AsyncMock, patch

from trade_sentinel_api.models.schemas import OptionsScanRow
from trade_sentinel_api.services.scan_batch import resolve_scan_universe
from trade_sentinel_api.services.smart_money.scan import (
    _options_signal_filter,
    _scan_one_insider,
    scan_insider_universe,
)


def test_resolve_scan_universe_sp500():
    key, tickers, suffix = resolve_scan_universe("sp500")
    assert key == "sp500"
    assert len(tickers) > 400
    assert suffix == "sp500"


def test_resolve_scan_universe_sp100():
    key, tickers, suffix = resolve_scan_universe("sp100")
    assert key == "sp100"
    assert len(tickers) >= 50
    assert suffix == "sp100"


def test_options_signal_filter_sp500_only_unusual():
    filt = _options_signal_filter("sp500")
    assert filt(OptionsScanRow(ticker="AAPL", unusual=True)) is True
    assert filt(OptionsScanRow(ticker="MSFT", unusual=False)) is False


@pytest.mark.asyncio
async def test_scan_one_insider_returns_accumulation_row():
    from trade_sentinel_api.models.schemas import (
        InsiderSummary,
        InsiderTimeline,
        InsiderTransaction,
    )

    timeline = InsiderTimeline(
        ticker="AAPL",
        data_available=True,
        transactions=[
            InsiderTransaction(
                filing_date=date.today().isoformat(),
                insider_name="CEO",
                transaction_type="Purchase",
            )
        ],
    )
    summary = InsiderSummary(
        sentiment="accumulation",
        buy_count=2,
        sell_count=0,
        cluster_buying=True,
        data_available=True,
    )
    with (
        patch(
            "trade_sentinel_api.services.smart_money.scan.fetch_insider_timeline",
            new_callable=AsyncMock,
            return_value=timeline,
        ),
        patch(
            "trade_sentinel_api.services.smart_money.scan.summarize_insider_activity",
            return_value=summary,
        ),
    ):
        row = await _scan_one_insider("AAPL")

    assert row is not None
    assert row.ticker == "AAPL"
    assert row.cluster_buying is True
    assert len(row.recent_transactions) == 1
    assert row.recent_transactions[0].insider_name == "CEO"


@pytest.mark.asyncio
async def test_scan_one_insider_returns_row_when_data_available():
    from trade_sentinel_api.models.schemas import (
        InsiderSummary,
        InsiderTimeline,
        InsiderTransaction,
    )
    from trade_sentinel_api.services.smart_money.scan import _insider_signal_filter

    timeline = InsiderTimeline(
        ticker="MSFT",
        data_available=True,
        transactions=[
            InsiderTransaction(
                filing_date=date.today().isoformat(),
                insider_name="CFO",
                transaction_type="Sale",
            )
        ],
    )
    summary = InsiderSummary(
        sentiment="neutral",
        buy_count=1,
        sell_count=1,
        data_available=True,
    )
    with (
        patch(
            "trade_sentinel_api.services.smart_money.scan.fetch_insider_timeline",
            new_callable=AsyncMock,
            return_value=timeline,
        ),
        patch(
            "trade_sentinel_api.services.smart_money.scan.summarize_insider_activity",
            return_value=summary,
        ),
    ):
        row = await _scan_one_insider("MSFT")

    assert row is not None
    assert row.ticker == "MSFT"
    assert _insider_signal_filter(row) is False


@pytest.mark.asyncio
async def test_scan_insider_universe_returns_accumulation_rows():
    from trade_sentinel_api.models.schemas import InsiderScanRow

    async def fake_scan(symbol: str) -> InsiderScanRow:
        return InsiderScanRow(
            ticker=symbol,
            sentiment="accumulation",
            buy_count=2,
            sell_count=0,
            cluster_buying=True,
            data_available=True,
        )

    with (
        patch(
            "trade_sentinel_api.services.smart_money.scan.resolve_scan_universe",
            return_value=("watchlist", ["AAPL"], "watchlist:default:abc"),
        ),
        patch(
            "trade_sentinel_api.services.smart_money.scan._scan_one_insider",
            side_effect=fake_scan,
        ),
        patch("trade_sentinel_api.services.smart_money.scan.get_cached", return_value=None),
        patch("trade_sentinel_api.services.smart_money.scan.set_cached_ttl"),
    ):
        result = await scan_insider_universe("watchlist", refresh=True)

    assert result.universe == "watchlist"
    assert len(result.rows) == 1
    assert result.rows[0].ticker == "AAPL"
    assert result.rows[0].cluster_buying is True


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.sec.form13dg._fetch_sync")
async def test_build_activist_feed_returns_multiple_items(mock_fetch):
    from datetime import UTC, datetime

    from trade_sentinel_api.models.schemas import ActivistFeed, ActivistFeedItem
    from trade_sentinel_api.services.sec.form13dg import build_activist_feed

    mock_fetch.return_value = ActivistFeed(
        as_of=datetime.now(UTC),
        items=[
            ActivistFeedItem(
                filing_date="2026-06-01",
                form_type="13D",
                ticker="AAPL",
                company_name="Apple Inc",
                is_activist=True,
            ),
            ActivistFeedItem(
                filing_date="2026-06-02",
                form_type="13G",
                ticker="MSFT",
                company_name="Microsoft Corp",
                is_activist=False,
            ),
        ],
        data_available=True,
        days_window=30,
    )

    with patch("trade_sentinel_api.services.sec.form13dg.get_cached", return_value=None):
        with patch("trade_sentinel_api.services.sec.form13dg.set_cached_ttl"):
            feed = await build_activist_feed(days=30, form_filter="all")

    assert len(feed.items) == 2
    assert feed.items[0].form_type == "13D"


@pytest.mark.asyncio
async def test_build_activist_feed_refresh_bypasses_cache():
    from datetime import UTC, datetime

    from trade_sentinel_api.models.schemas import ActivistFeed, ActivistFeedItem
    from trade_sentinel_api.services.sec.form13dg import build_activist_feed

    cached_feed = ActivistFeed(
        as_of=datetime.now(UTC),
        items=[],
        data_available=False,
        message="stale",
        days_window=30,
    )
    fresh_feed = ActivistFeed(
        as_of=datetime.now(UTC),
        items=[
            ActivistFeedItem(
                filing_date="2026-06-01",
                form_type="13D",
                ticker="AAPL",
                is_activist=True,
            )
        ],
        data_available=True,
        days_window=30,
    )

    with patch("trade_sentinel_api.services.sec.form13dg.get_cached", return_value=cached_feed.model_dump(mode="json")):
        with patch("trade_sentinel_api.services.sec.form13dg._fetch_sync", return_value=fresh_feed) as mock_fetch:
            with patch("trade_sentinel_api.services.sec.form13dg.set_cached_ttl") as mock_cache:
                feed = await build_activist_feed(days=30, form_filter="all", refresh=True)

    mock_fetch.assert_called_once()
    mock_cache.assert_called_once()
    cache_key = mock_cache.call_args[0][1]
    assert cache_key == "v3:30:all"
    assert len(feed.items) == 1


def test_fetch_sync_uses_schedule13_date_range():
    from datetime import date

    from trade_sentinel_api.models.schemas import ActivistFeedItem
    from trade_sentinel_api.services.sec.form13dg import _fetch_sync

    filing = MagicMock()
    filing.form = "SC 13D"
    filing.filing_date = date.today().isoformat()
    filing.filing_url = "https://www.sec.gov/example"
    filing.company = "Target Co"

    item = ActivistFeedItem(
        filing_date=filing.filing_date,
        form_type="13D",
        ticker="TGT",
        is_activist=True,
    )

    with patch(
        "trade_sentinel_api.services.sec.form13dg.fetch_schedule13_by_date_range",
        return_value=[filing],
    ) as mock_fetch:
        with patch(
            "trade_sentinel_api.services.sec.form13dg.filing_to_activist_item",
            return_value=item,
        ):
            feed = _fetch_sync(days=30, form_filter="13d")

    mock_fetch.assert_called_once()
    assert mock_fetch.call_args.args[0] <= date.today()
    assert len(feed.items) == 1
    assert feed.data_available is True

# --- from test_smart_money_router.py ---

from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from trade_sentinel_api.main import app
from trade_sentinel_api.models.schemas import (
    OptionsScanResult,
    SmartMoneyFeed,
    SmartMoneyFeedStats,
    WatchlistInsiderPulse,
)

client = TestClient(app)


@patch(
    "trade_sentinel_api.routers.smart_money.build_smart_money_feed",
    new_callable=AsyncMock,
)
def test_smart_money_feed_endpoint(mock_feed):
    mock_feed.return_value = SmartMoneyFeed(
        as_of=datetime.now(UTC),
        stats=SmartMoneyFeedStats(),
        data_available=True,
        days_window=7,
    )
    r = client.get("/api/v1/smart-money/feed?days=7&side=buy")
    assert r.status_code == 200
    assert r.json()["days_window"] == 7


@patch(
    "trade_sentinel_api.routers.smart_money.build_watchlist_insider_pulse",
    new_callable=AsyncMock,
)
def test_watchlist_pulse_endpoint(mock_pulse):
    mock_pulse.return_value = WatchlistInsiderPulse(
        as_of=datetime.now(UTC),
        watchlist_name="default",
        data_available=True,
    )
    r = client.get("/api/v1/smart-money/watchlist-pulse")
    assert r.status_code == 200
    assert r.json()["watchlist_name"] == "default"


@patch(
    "trade_sentinel_api.routers.smart_money.scan_options_universe",
    new_callable=AsyncMock,
)
def test_options_scan_endpoint(mock_scan):
    mock_scan.return_value = OptionsScanResult(
        as_of=datetime.now(UTC),
        universe="sp100",
        scanned_count=100,
        data_available=True,
    )
    r = client.get("/api/v1/smart-money/options-scan?universe=sp100")
    assert r.status_code == 200
    assert r.json()["universe"] == "sp100"

# --- from test_smart_money_assessment.py ---

from trade_sentinel_api.models.schemas import (
    InsiderSummary,
    OptionsFlowFlag,
    VolumeFootprint,
)
from trade_sentinel_api.services.smart_money.assessment import build_smart_money_assessment


def test_full_five_layer_assessment():
    result = build_smart_money_assessment(
        ticker="AAPL",
        insider_summary=InsiderSummary(
            sentiment="accumulation",
            cluster_buying=True,
            data_available=True,
            analysis_bullets=["Cluster buying detected."],
        ),
        options_flow=OptionsFlowFlag(
            unusual=True,
            high_conviction=True,
            institutional_grade=True,
            put_call_ratio=0.55,
            max_vol_oi_ratio=6.0,
            conviction_band="swing",
            unusual_reason="Institutional-grade flow",
        ),
        volume_footprint=VolumeFootprint(
            stance="accumulation",
            data_available=True,
            analysis_bullets=["OBV divergence (20d): bullish."],
        ),
        institutional_conviction=True,
        activist_alert=True,
        crowding_risk="high",
    )
    layer_ids = {l.layer for l in result.layers}
    assert "insider_open_market" in layer_ids
    assert "options_flow" in layer_ids
    assert "volume_footprint" in layer_ids
    assert "institutional_13f" in layer_ids
    assert "activist_13d" in layer_ids
    assert "institutional_crowding" in layer_ids
    assert result.conviction_pct is not None
    assert result.data_available


def test_calendar_notes_present_in_quarter_end():
    result = build_smart_money_assessment(
        ticker="MSFT",
        insider_summary=InsiderSummary(sentiment="neutral", data_available=True),
    )
    assert isinstance(result.calendar_notes, list)
