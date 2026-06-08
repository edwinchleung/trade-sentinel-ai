"""Macro briefing async tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from trade_sentinel_api.models.schemas import MacroSignalsSnapshot, MacroSummary
from trade_sentinel_api.services.macro import get_macro_briefing


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.macro.summarize_macro", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.macro.fetch_watchlist_sectors", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.macro.get_watchlist")
@patch("trade_sentinel_api.services.macro.get_cached", return_value=None)
@patch("trade_sentinel_api.services.macro.set_cached")
@patch(
    "trade_sentinel_api.services.macro.get_daily_macro_bundle",
    new_callable=AsyncMock,
)
async def test_macro_briefing_uses_daily_events(
    mock_bundle,
    _set_cache,
    _get_cache,
    mock_watchlist,
    mock_sectors,
    mock_summarize,
):
    mock_bundle.return_value = {
        "trading_date": "2026-06-03",
        "events": [
            {
                "name": "CPI Release",
                "impact": "high",
                "sectors": ["Tech"],
                "source": "schedule",
                "actual": 3.2,
                "estimate": 3.0,
                "surprise_pct": 6.67,
                "beat_miss": "beat",
            },
        ],
        "impact_summary": {"high": 1, "moderate": 0, "noise": 0},
        "release_stats": {
            "beats": 1,
            "misses": 0,
            "inline": 0,
            "unavailable": 0,
            "largest_surprises": [],
        },
        "macro_signals": MacroSignalsSnapshot(
            as_of=datetime.now(UTC),
            signals=[],
            risk_tone="normal",
        ).model_dump(mode="json"),
        "macro_news": [],
        "news_by_source": {},
        "data_gaps": [],
    }
    mock_watchlist.return_value = type("W", (), {"tickers": ["AAPL"]})()
    mock_sectors.return_value = {"AAPL": "Technology"}
    mock_summarize.return_value = (
        MacroSummary(bullets=["a", "b", "c"], model="test"),
        {
            "market_weather": "Data-heavy day",
            "headline_events": ["CPI Release"],
            "sector_watch": ["Watch Tech"],
            "watchlist_exposure": ["AAPL exposed to CPI"],
            "event_playbooks": [{"name": "CPI Release", "playbook": "Inflation gauge"}],
            "signal_highlights": ["VIX stable"],
        },
    )

    briefing = await get_macro_briefing()

    assert briefing.events[0].name == "CPI Release"
    assert briefing.events[0].beat_miss == "beat"
    assert briefing.market_weather == "Data-heavy day"
    assert briefing.impact_summary["high"] == 1
    assert briefing.signal_highlights == ["VIX stable"]
    assert briefing.release_stats is not None
    mock_summarize.assert_called_once()
    facts = mock_summarize.call_args[0][0]
    assert "events" in facts
    assert "macro_signals" in facts
    assert "macro_news" in facts
    assert "release_stats" in facts
    assert "calendar_headline_candidates" in facts


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.macro.summarize_macro", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.macro.get_cached", return_value=None)
@patch("trade_sentinel_api.services.macro.set_cached")
@patch(
    "trade_sentinel_api.services.macro.get_daily_macro_bundle",
    new_callable=AsyncMock,
)
async def test_macro_briefing_quiet_day_with_signals(
    mock_bundle,
    _set_cache,
    _get_cache,
    mock_summarize,
):
    from trade_sentinel_api.models.schemas import MacroSignal, NewsItem

    mock_bundle.return_value = {
        "trading_date": "2026-06-03",
        "events": [],
        "impact_summary": {"high": 0, "moderate": 0, "noise": 0},
        "release_stats": None,
        "macro_signals": MacroSignalsSnapshot(
            as_of=datetime.now(UTC),
            signals=[MacroSignal(symbol="^VIX", label="VIX", level=18.0)],
            risk_tone="normal",
        ).model_dump(mode="json"),
        "macro_news": [NewsItem(title="Markets steady", source="finnhub").model_dump()],
        "news_by_source": {"finnhub": 1},
        "data_gaps": [],
    }
    mock_summarize.return_value = (
        MacroSummary(bullets=["a", "b", "c"], model="test"),
        {
            "market_weather": "Quiet calendar",
            "headline_events": [],
            "sector_watch": [],
            "watchlist_exposure": [],
            "event_playbooks": [],
            "signal_highlights": ["Low vol"],
        },
    )

    with patch("trade_sentinel_api.services.macro.fetch_watchlist_sectors", new_callable=AsyncMock) as mock_sec:
        with patch("trade_sentinel_api.services.macro.get_watchlist") as mock_wl:
            mock_wl.return_value = type("W", (), {"tickers": []})()
            mock_sec.return_value = {}
            briefing = await get_macro_briefing()

    assert briefing.events == []
    assert briefing.market_weather == "Quiet calendar"
    mock_summarize.assert_called_once()
