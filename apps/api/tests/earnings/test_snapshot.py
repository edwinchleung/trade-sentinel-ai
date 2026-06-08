"""Merged from: test_earnings.py"""

# --- from test_earnings.py ---

from datetime import date
from unittest.mock import MagicMock, patch

from trade_sentinel_api.models.schemas import EarningsSnapshot
from trade_sentinel_api.services.earnings import (
    _fetch_yfinance_earnings_extra_sync,
    _parse_yfinance_next_earnings,
)
from trade_sentinel_api.services.yfinance_bundle import TickerDataBundle


@patch("trade_sentinel_api.services.yfinance_bundle.earnings_from_bundle")
@patch("trade_sentinel_api.services.yfinance_bundle.load_ticker_bundle_sync")
def test_yfinance_earnings_with_info(mock_load_bundle, mock_earnings_from_bundle):
    mock_load_bundle.return_value = TickerDataBundle(symbol="AAPL")
    mock_earnings_from_bundle.return_value = EarningsSnapshot(
        last_eps_actual=2.5,
        last_eps_estimate=3.0,
        data_available=True,
    )

    result = _fetch_yfinance_earnings_extra_sync("AAPL")

    assert isinstance(result, EarningsSnapshot)
    assert result.last_eps_actual == 2.5
    assert result.last_eps_estimate == 3.0
    assert result.data_available is True


@patch("trade_sentinel_api.services.yfinance_bundle.earnings_from_bundle")
@patch("trade_sentinel_api.services.yfinance_bundle.load_ticker_bundle_sync")
def test_yfinance_earnings_dict_calendar(mock_load_bundle, mock_earnings_from_bundle):
    mock_load_bundle.return_value = TickerDataBundle(symbol="TSM")
    mock_earnings_from_bundle.return_value = EarningsSnapshot(
        next_report_date="2026-07-16",
        days_until=30,
        last_eps_actual=2.0,
        data_available=True,
    )

    result = _fetch_yfinance_earnings_extra_sync("TSM")

    assert result.next_report_date == "2026-07-16"
    assert result.days_until is not None
    assert result.days_until >= 0


def test_parse_yfinance_next_earnings_dict_calendar_only():
    cal = {"Earnings Date": [date(2026, 7, 16)]}
    next_date, days = _parse_yfinance_next_earnings(MagicMock(), {}, cal)
    assert next_date == "2026-07-16"
    assert days is not None
