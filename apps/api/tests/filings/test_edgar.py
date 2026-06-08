from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest

import trade_sentinel_api.services.sec.edgar as edgar
from trade_sentinel_api.services.sec.edgar import (
    _empty_timeline,
    _fetch_form4_sync,
    _load_cik_disk_cache,
    _resolve_cik_map,
    clear_edgar_cache,
    get_cik_for_ticker,
    get_company_tickers,
    warm_company_tickers_cache,
)


@pytest.fixture(autouse=True)
def reset_edgar_cache():
    clear_edgar_cache()
    edgar._CIK_MAP_UNAVAILABLE = False
    edgar._CIK_USING_FALLBACK = False
    yield
    clear_edgar_cache()


def test_empty_timeline_has_no_stub_transactions():
    timeline = _empty_timeline("XYZ", "Data Unavailable — test.")
    assert timeline.ticker == "XYZ"
    assert timeline.transactions == []
    assert timeline.data_available is False
    assert timeline.message == "Data Unavailable — test."


@patch("trade_sentinel_api.services.sec.edgar._company_tickers", return_value={})
def test_unknown_ticker_returns_unavailable(_tickers):
    timeline = _fetch_form4_sync("NOTREAL", 5)
    assert timeline.data_available is False
    assert timeline.transactions == []
    assert "CIK" in (timeline.message or "")


@patch("trade_sentinel_api.services.sec.edgar.sec_get")
def test_company_tickers_fetches_mapping(mock_sec_get):
    mock_resp_ok = MagicMock()
    mock_resp_ok.status_code = 200
    mock_resp_ok.json.return_value = {"0": {"ticker": "AAPL", "cik_str": 320193}}
    mock_sec_get.return_value = mock_resp_ok

    with (
        patch("trade_sentinel_api.services.sec.edgar._load_cik_disk_cache", return_value=(None, False)),
        patch("trade_sentinel_api.services.sec.edgar._load_cik_seed", return_value=None),
    ):
        mapping = get_company_tickers()

    assert mapping["AAPL"] == "0000320193"
    mock_sec_get.assert_called_once()


def test_negative_cache_avoids_repeat_fetch():
    edgar._CIK_CACHE = None
    edgar._CIK_FAILED_UNTIL = datetime.now(UTC) + timedelta(seconds=120)
    stale_map = {"AAPL": "0000320193"}

    with (
        patch(
            "trade_sentinel_api.services.sec.edgar._load_cik_disk_cache",
            return_value=(stale_map, True),
        ),
        patch("trade_sentinel_api.services.sec.edgar.sec_get") as mock_sec_get,
    ):
        mapping = get_company_tickers()
        assert mapping["AAPL"] == "0000320193"
        mock_sec_get.assert_not_called()

        mapping2 = get_company_tickers()
        assert mapping2["AAPL"] == "0000320193"
        mock_sec_get.assert_not_called()


@patch("trade_sentinel_api.services.sec.edgar.sec_get")
def test_company_tickers_uses_seed_on_429(mock_sec_get):
    mock_resp_fail = MagicMock()
    mock_resp_fail.status_code = 429
    mock_resp_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
        "rate limited", request=MagicMock(), response=mock_resp_fail
    )
    mock_sec_get.return_value = mock_resp_fail

    with (
        patch("trade_sentinel_api.services.sec.edgar._load_cik_disk_cache", return_value=(None, False)),
        patch(
            "trade_sentinel_api.services.sec.edgar._load_cik_seed",
            return_value={"AAPL": "0000320193", "MSFT": "0000789019"},
        ),
    ):
        mapping = get_company_tickers()

    assert mapping["AAPL"] == "0000320193"
    assert edgar._CIK_USING_FALLBACK is True


@patch("trade_sentinel_api.services.sec.edgar.fetch_company_filings", return_value=[])
@patch("trade_sentinel_api.services.sec.edgar._company_tickers", return_value={"AAPL": "0000320193"})
def test_submissions_cache_used_for_form4(_tickers, mock_filings):
    timeline = _fetch_form4_sync("AAPL", 5)
    mock_filings.assert_called_once()
    assert timeline.ticker == "AAPL"


@patch("trade_sentinel_api.services.sec.edgar.get_company_tickers", return_value={"AAPL": "0000320193"})
def test_warm_company_tickers_cache(_mock):
    assert warm_company_tickers_cache() is True


@patch("trade_sentinel_api.services.sec.edgar.get_company_tickers", side_effect=httpx.HTTPError("fail"))
def test_warm_company_tickers_cache_failure(_mock):
    assert warm_company_tickers_cache() is False


def test_resolve_cik_map_merges_seed_when_disk_cache_incomplete():
    seed = {
        "TSLA": "0001318605",
        "META": "0001326801",
        "AAPL": "0000320193",
    }
    with patch("trade_sentinel_api.services.sec.edgar._load_cik_seed", return_value=seed):
        resolved = _resolve_cik_map({"AAPL": "0000320193"})
    assert resolved["TSLA"] == "0001318605"
    assert resolved["META"] == "0001326801"
    assert resolved["AAPL"] == "0000320193"


def test_load_cik_disk_cache_rejects_partial_map(tmp_path):
    cache_path = tmp_path / "company_tickers_cache.json"
    cache_path.write_text(
        '{"fetched_at": "2026-06-05T12:00:00+00:00", "mapping": {"AAPL": "0000320193"}}',
        encoding="utf-8",
    )
    with patch("trade_sentinel_api.services.sec.edgar._CIK_DISK_CACHE_PATH", cache_path):
        mapping, _ = _load_cik_disk_cache(allow_stale=False)
    assert mapping is None


@patch("trade_sentinel_api.services.sec.edgar.sec_get")
def test_partial_sec_response_uses_seed_for_missing_tickers(mock_sec_get):
    mock_resp_ok = MagicMock()
    mock_resp_ok.status_code = 200
    mock_resp_ok.json.return_value = {"0": {"ticker": "AAPL", "cik_str": 320193}}
    mock_sec_get.return_value = mock_resp_ok

    seed = {
        "TSLA": "0001318605",
        "META": "0001326801",
        "AAPL": "0000320193",
    }
    with (
        patch("trade_sentinel_api.services.sec.edgar._load_cik_disk_cache", return_value=(None, False)),
        patch("trade_sentinel_api.services.sec.edgar._load_cik_seed", return_value=seed),
        patch("trade_sentinel_api.services.sec.edgar._save_cik_disk_cache") as mock_save,
    ):
        mapping = get_company_tickers()

    assert mapping["TSLA"] == "0001318605"
    assert mapping["META"] == "0001326801"
    assert get_cik_for_ticker("TSLA") == "0001318605"
    mock_save.assert_not_called()


def test_cik_map_unavailable_uses_debug_per_ticker():
    edgar._CIK_CACHE = None
    edgar._CIK_MAP_UNAVAILABLE = True
    edgar._CIK_FAILED_UNTIL = datetime.now(UTC) + timedelta(seconds=60)
    with (
        patch("trade_sentinel_api.services.sec.edgar._load_cik_seed", return_value={}),
        patch("trade_sentinel_api.services.sec.edgar._load_cik_disk_cache", return_value=(None, False)),
        patch("trade_sentinel_api.services.sec.edgar._company_tickers", return_value={}),
    ):
        timeline = _fetch_form4_sync("AAPL", 5)
    assert timeline.data_available is False
    assert timeline.transactions == []
