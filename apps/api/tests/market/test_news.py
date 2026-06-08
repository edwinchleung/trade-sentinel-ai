from unittest.mock import AsyncMock, patch

import pytest

from trade_sentinel_api.services.market_data import fetch_news


@pytest.mark.asyncio
@patch(
    "trade_sentinel_api.services.market_data.fetch_yfinance_news",
    new_callable=AsyncMock,
)
@patch(
    "trade_sentinel_api.services.market_data.fetch_finnhub_news",
    new_callable=AsyncMock,
)
async def test_fetch_news_uses_yfinance_when_finnhub_empty(
    mock_finnhub, mock_yfinance
):
    from trade_sentinel_api.models.schemas import NewsItem

    mock_finnhub.return_value = []
    mock_yfinance.return_value = [
        NewsItem(title="Headline", url="http://x", source="yfinance")
    ]

    items = await fetch_news("AAPL")
    assert len(items) == 1
    assert items[0].title == "Headline"
    mock_yfinance.assert_awaited_once()


@pytest.mark.asyncio
@patch(
    "trade_sentinel_api.services.market_data.fetch_yfinance_news",
    new_callable=AsyncMock,
)
@patch(
    "trade_sentinel_api.services.market_data.fetch_finnhub_news",
    new_callable=AsyncMock,
)
async def test_fetch_news_prefers_finnhub(mock_finnhub, mock_yfinance):
    from trade_sentinel_api.models.schemas import NewsItem

    mock_finnhub.return_value = [NewsItem(title="FH", source="finnhub")]

    items = await fetch_news("AAPL")
    assert items[0].title == "FH"
    mock_yfinance.assert_not_awaited()

# --- from test_yfinance_bundle.py ---

from unittest.mock import MagicMock, patch

import pandas as pd

from trade_sentinel_api.models.schemas import FundamentalsSnapshot
from trade_sentinel_api.services.yfinance_bundle import (
    earnings_from_bundle,
    fundamentals_from_bundle,
    load_ticker_bundle_sync,
    market_from_bundle,
    prefetch_hist_chunk,
)


def _sample_hist() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    return pd.DataFrame(
        {
            "Close": [100.0 + i * 0.1 for i in range(60)],
            "Volume": [1_000_000] * 60,
        },
        index=idx,
    )


@patch("trade_sentinel_api.services.yfinance_bundle.yf.Ticker")
def test_load_ticker_bundle_sync_single_session(mock_ticker_cls):
    stock = MagicMock()
    stock.history.return_value = _sample_hist()
    stock.info = {"currentPrice": 105.0, "regularMarketPrice": 105.0, "marketState": "REGULAR"}
    stock.quarterly_income_stmt = pd.DataFrame()
    stock.quarterly_balance_sheet = pd.DataFrame()
    stock.quarterly_cashflow = pd.DataFrame()
    stock.financials = pd.DataFrame()
    stock.calendar = {}
    mock_ticker_cls.return_value = stock

    bundle = load_ticker_bundle_sync("AAA")
    assert bundle.ok
    mock_ticker_cls.assert_called_once_with("AAA")
    stock.history.assert_called_once()
    assert stock.info is not None


@patch("trade_sentinel_api.services.yfinance_bundle.yf.Ticker")
def test_market_fundamentals_earnings_from_one_bundle(mock_ticker_cls):
    stock = MagicMock()
    hist = _sample_hist()
    stock.history.return_value = hist
    stock.info = {
        "currentPrice": 105.0,
        "regularMarketPrice": 105.0,
        "marketState": "REGULAR",
        "sector": "Technology",
        "trailingEps": 1.5,
    }
    stock.quarterly_income_stmt = pd.DataFrame()
    stock.quarterly_balance_sheet = pd.DataFrame()
    stock.quarterly_cashflow = pd.DataFrame()
    stock.financials = pd.DataFrame()
    stock.calendar = {}
    mock_ticker_cls.return_value = stock

    bundle = load_ticker_bundle_sync("AAA")
    market = market_from_bundle(bundle)
    assert market["price"] is not None

    with patch(
        "trade_sentinel_api.services.yfinance_bundle._fundamentals_from_yf_data",
        return_value=FundamentalsSnapshot(data_available=True, sector="Technology", pe_forward=20),
    ):
        fund = fundamentals_from_bundle(bundle, market["price"])
    assert fund.sector == "Technology"

    earn = earnings_from_bundle(bundle)
    assert earn.data_available


@patch("trade_sentinel_api.services.yfinance_bundle.yf.download")
def test_prefetch_hist_chunk_skips_history_call(mock_download):
    hist = _sample_hist()
    mock_download.return_value = hist

    result = prefetch_hist_chunk(["AAA"])
    assert "AAA" in result
    mock_download.assert_called_once()

    with patch("trade_sentinel_api.services.yfinance_bundle.yf.Ticker") as mock_ticker_cls:
        stock = MagicMock()
        stock.info = {"currentPrice": 100.0, "marketState": "REGULAR"}
        stock.quarterly_income_stmt = pd.DataFrame()
        stock.quarterly_balance_sheet = pd.DataFrame()
        stock.quarterly_cashflow = pd.DataFrame()
        stock.financials = pd.DataFrame()
        stock.calendar = {}
        mock_ticker_cls.return_value = stock

        bundle = load_ticker_bundle_sync("AAA", hist_prefetch=hist)
        stock.history.assert_not_called()
        assert bundle.ok
