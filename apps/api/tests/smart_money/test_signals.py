"""Merged from: test_volume_footprint.py, test_options_flow.py"""

# --- from test_volume_footprint.py ---

import pandas as pd
import pytest

from trade_sentinel_api.services.volume.footprint import build_volume_footprint


def _sample_hist(prices: list[float], volumes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": prices,
            "High": [p * 1.01 for p in prices],
            "Low": [p * 0.99 for p in prices],
            "Volume": volumes,
        }
    )


def _bullish_obv_fixture() -> tuple[list[float], list[float]]:
    prices: list[float] = []
    volumes: list[float] = []
    base = 100.0
    for i in range(25):
        if i % 2 == 0:
            prices.append(base - i * 0.08)
            volumes.append(400_000.0)
        else:
            prices.append(prices[-1] + 0.4)
            volumes.append(2_500_000.0)
    return prices, volumes


def _bearish_obv_fixture() -> tuple[list[float], list[float]]:
    prices: list[float] = []
    volumes: list[float] = []
    base = 90.0
    for i in range(25):
        if i % 2 == 0:
            prices.append(base + i * 0.35)
            volumes.append(400_000.0)
        else:
            prices.append(prices[-1] - 0.25)
            volumes.append(2_800_000.0)
    return prices, volumes


def test_quiet_accumulation_flat_price_bullish_obv():
    prices, volumes = _bullish_obv_fixture()
    hist = _sample_hist(prices, volumes)
    fp = build_volume_footprint(hist, price=prices[-1], volume_ratio=1.0)
    assert fp.data_available
    assert fp.obv_divergence == "bullish"
    assert fp.quiet_accumulation is True
    assert fp.stance == "accumulation"


def test_bearish_obv_divergence_rising_price_falling_obv():
    prices, volumes = _bearish_obv_fixture()
    hist = _sample_hist(prices, volumes)
    fp = build_volume_footprint(hist, price=prices[-1], volume_ratio=1.0)
    assert fp.obv_divergence == "bearish"
    assert fp.stance == "distribution"

# --- from test_options_flow.py ---

from unittest.mock import MagicMock, patch

from trade_sentinel_api.services.options.flow import _analyze_sync


@patch("trade_sentinel_api.services.options.flow.yf.Ticker")
def test_options_flow_unusual_put_skew(mock_ticker_cls):
    mock_stock = MagicMock()
    mock_ticker_cls.return_value = mock_stock
    mock_stock.options = ("2026-07-18",)

    import pandas as pd

    calls = pd.DataFrame({"volume": [1000.0, 500.0]})
    puts = pd.DataFrame({"volume": [3000.0, 2000.0]})
    chain = MagicMock()
    chain.calls = calls
    chain.puts = puts
    mock_stock.option_chain.return_value = chain

    flag, warnings = _analyze_sync("SPY")

    assert flag.put_call_ratio is not None
    assert flag.put_call_ratio > 0.90
    assert flag.unusual is True
    assert flag.call_volume == 1500.0
    assert flag.put_volume == 5000.0
    assert flag.expiry == "2026-07-18"
    assert any(w.code == "OPTIONS_UNUSUAL" for w in warnings)


@patch("trade_sentinel_api.services.options.flow.yf.Ticker")
def test_options_flow_open_interest_from_chain(mock_ticker_cls):
    import pandas as pd

    mock_stock = MagicMock()
    mock_ticker_cls.return_value = mock_stock
    mock_stock.options = ("2026-07-18",)

    calls = pd.DataFrame({"volume": [100.0], "openInterest": [5000.0]})
    puts = pd.DataFrame({"volume": [200.0], "openInterest": [3000.0]})
    chain = MagicMock()
    chain.calls = calls
    chain.puts = puts
    mock_stock.option_chain.return_value = chain

    flag, _ = _analyze_sync("NVDA")

    assert flag.total_open_interest == 8000.0
    assert flag.open_interest_available is True


@patch("trade_sentinel_api.services.options.flow.yf.Ticker")
def test_options_flow_open_interest_missing(mock_ticker_cls):
    import pandas as pd

    mock_stock = MagicMock()
    mock_ticker_cls.return_value = mock_stock
    mock_stock.options = ("2026-07-18",)

    calls = pd.DataFrame({"volume": [100.0]})
    puts = pd.DataFrame({"volume": [200.0]})
    chain = MagicMock()
    chain.calls = calls
    chain.puts = puts
    mock_stock.option_chain.return_value = chain

    flag, _ = _analyze_sync("XYZ")

    assert flag.total_open_interest is None
    assert flag.open_interest_available is False


@patch("trade_sentinel_api.services.options.flow.yf.Ticker")
def test_options_flow_top_strike_oi_omitted_when_unknown(mock_ticker_cls):
    import pandas as pd

    mock_stock = MagicMock()
    mock_ticker_cls.return_value = mock_stock
    mock_stock.options = ("2026-07-18",)

    calls = pd.DataFrame({"volume": [5000.0], "strike": [100.0]})
    puts = pd.DataFrame({"volume": [100.0], "strike": [95.0]})
    chain = MagicMock()
    chain.calls = calls
    chain.puts = puts
    mock_stock.option_chain.return_value = chain

    flag, _ = _analyze_sync("NVDA")

    assert len(flag.top_strikes) >= 1
    assert flag.top_strikes[0].open_interest is None


def test_build_options_result_no_signals_message():
    from datetime import UTC, datetime

    from trade_sentinel_api.services.smart_money.scan import _build_options_result

    result = _build_options_result(
        [],
        "sp500",
        503,
        datetime.now(UTC),
        fetched_count=120,
        signals_only=True,
    )
    assert result.data_available is False
    assert "No unusual options activity" in (result.message or "")
    assert "120" in (result.message or "")


def test_build_options_result_fetch_failed_message():
    from datetime import UTC, datetime

    from trade_sentinel_api.services.smart_money.scan import _build_options_result

    result = _build_options_result(
        [],
        "sp500",
        503,
        datetime.now(UTC),
        fetched_count=0,
        signals_only=True,
    )
    assert "could not be fetched" in (result.message or "").lower()


def test_build_options_result_provider_degraded():
    from datetime import UTC, datetime

    from trade_sentinel_api.services.smart_money.scan import _build_options_result

    result = _build_options_result(
        [],
        "sp500",
        503,
        datetime.now(UTC),
        fetched_count=0,
        signals_only=True,
        provider_degraded=True,
    )
    assert result.provider_degraded is True


def test_build_insider_result_provider_degraded():
    from datetime import UTC, datetime

    from trade_sentinel_api.services.smart_money.scan import _build_insider_result

    result = _build_insider_result(
        [],
        "sp500",
        503,
        datetime.now(UTC),
        fetched_count=0,
        signals_only=False,
        provider_degraded=True,
    )
    assert result.provider_degraded is True
    assert "could not be fetched" in (result.message or "").lower()


def test_options_flow_has_data_accepts_chain_without_volume():
    from trade_sentinel_api.models.schemas import OptionsExpiryBreakdown, OptionsFlowFlag
    from trade_sentinel_api.services.smart_money.scan import _options_flow_has_data

    flow = OptionsFlowFlag(
        expiry_breakdown=[
            OptionsExpiryBreakdown(expiry="2026-06-20", call_volume=0, put_volume=0)
        ],
        open_interest_available=True,
    )
    assert _options_flow_has_data(flow) is True


def test_scan_batch_effective_cache_ttl_on_failure():
    from trade_sentinel_api.services.scan_batch import _effective_cache_ttl

    assert _effective_cache_ttl(
        cache_ttl_seconds=3600,
        scanned_count=100,
        fetched_count=0,
        partial=False,
    ) == 120


def test_build_volume_result_no_signals_message():
    from datetime import UTC, datetime

    from trade_sentinel_api.services.volume.footprint import _build_volume_result

    result = _build_volume_result(
        [],
        "sp500",
        503,
        datetime.now(UTC),
        fetched_count=80,
        signals_only=True,
    )
    assert "No accumulation volume signals" in (result.message or "")


@pytest.mark.asyncio
async def test_scan_one_option_skips_error_message_only():
    from unittest.mock import AsyncMock, patch

    from trade_sentinel_api.models.schemas import OptionsFlowFlag
    from trade_sentinel_api.services.smart_money.scan import _scan_one_option

    with patch(
        "trade_sentinel_api.services.smart_money.scan.enrich_options_flow_with_ticks",
        new_callable=AsyncMock,
        return_value=(OptionsFlowFlag(message="Options data unavailable."), []),
    ):
        row = await _scan_one_option("XYZ")
        assert row is None


@pytest.mark.asyncio
async def test_scan_one_option_accepts_valid_volumes():
    from unittest.mock import AsyncMock, patch

    from trade_sentinel_api.models.schemas import OptionsFlowFlag
    from trade_sentinel_api.services.smart_money.scan import _scan_one_option

    with patch(
        "trade_sentinel_api.services.smart_money.scan.enrich_options_flow_with_ticks",
        new_callable=AsyncMock,
        return_value=(OptionsFlowFlag(call_volume=100.0, put_volume=50.0), []),
    ):
        row = await _scan_one_option("AAPL")
        assert row is not None
        assert row.ticker == "AAPL"
        assert row.call_volume == 100.0


@patch("trade_sentinel_api.services.options.flow.yf.Ticker")
def test_options_flow_no_chain(mock_ticker_cls):
    mock_stock = MagicMock()
    mock_ticker_cls.return_value = mock_stock
    mock_stock.options = ()

    flag, warnings = _analyze_sync("XYZ")

    assert flag.message == "No options chain data available."
    assert warnings == []
