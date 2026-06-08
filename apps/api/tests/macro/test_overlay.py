"""Merged from: test_macro_context.py, test_macro_news.py, test_macro_signals.py, test_macro_release_stats.py, test_context_macro.py"""

# --- from test_macro_context.py ---

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from trade_sentinel_api.models.schemas import MacroSignalsSnapshot
from trade_sentinel_api.services.macro.context import (
    attach_briefing_narrative,
    macro_overlay_for_ticker,
    sector_matches_ticker,
)


def test_sector_matches_technology():
    assert sector_matches_ticker("Technology", ["Tech", "Real Estate"]) is True
    assert sector_matches_ticker("Technology", ["Energy"]) is False


def test_sector_matches_broad_market():
    assert sector_matches_ticker("Healthcare", ["Broad Market"]) is True


def test_macro_overlay_filters_by_sector():
    bundle = {
        "trading_date": "2026-06-03",
        "events": [
            {
                "name": "CPI Release",
                "impact": "high",
                "sectors": ["Tech", "Consumer"],
            },
            {
                "name": "EIA Weekly Petroleum Status",
                "impact": "moderate",
                "sectors": ["Energy"],
            },
        ],
        "impact_summary": {"high": 1, "moderate": 1, "noise": 0},
        "macro_signals": MacroSignalsSnapshot(
            as_of=datetime.now(UTC),
            signals=[],
            risk_tone="normal",
        ).model_dump(mode="json"),
        "macro_news": [],
        "data_gaps": [],
    }
    overlay = macro_overlay_for_ticker("AAPL", "Technology", bundle)
    names = [e.name for e in overlay.relevant_events]
    assert "CPI Release" in names
    assert "EIA Weekly Petroleum Status" not in names
    assert overlay.has_content is True


def test_attach_briefing_narrative_from_cache():
    bundle = {"trading_date": "2026-06-03"}
    with patch(
        "trade_sentinel_api.services.macro.context.get_cached",
        return_value={
            "market_weather": "Risk-on",
            "signal_highlights": ["VIX low"],
            "headline_events": ["CPI"],
        },
    ):
        attach_briefing_narrative(bundle)
    assert bundle["market_weather"] == "Risk-on"
    assert bundle["signal_highlights"] == ["VIX low"]


def test_attach_briefing_narrative_fallback_without_cache():
    from trade_sentinel_api.models.schemas import MacroSignal, MacroSignalsSnapshot

    bundle = {
        "trading_date": "2026-06-03",
        "events": [{"name": "CPI Release", "impact": "high"}],
        "impact_summary": {"high": 1, "moderate": 0, "noise": 0},
        "macro_signals": MacroSignalsSnapshot(
            as_of=__import__("datetime").datetime.now(__import__("datetime").UTC),
            signals=[MacroSignal(symbol="^VIX", label="VIX", level=22.0, change_1d_pct=5.2)],
            risk_tone="elevated_vix",
        ).model_dump(mode="json"),
    }
    with patch("trade_sentinel_api.services.macro.context.get_cached", return_value=None):
        attach_briefing_narrative(bundle)
    assert bundle["market_weather"]
    assert "high-impact" in bundle["market_weather"].lower()
    assert bundle["signal_highlights"]
    assert bundle["headline_events"] == ["CPI Release"]


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.macro.context.set_cached")
@patch("trade_sentinel_api.services.macro.context.get_cached", return_value=None)
@patch(
    "trade_sentinel_api.services.macro.context.build_daily_macro_bundle",
    new_callable=AsyncMock,
)
async def test_get_daily_macro_bundle_caches(mock_build, _get, _set):
    from trade_sentinel_api.services.macro.context import get_daily_macro_bundle

    mock_build.return_value = {"trading_date": "2026-06-03", "events": []}
    bundle = await get_daily_macro_bundle()
    assert bundle["trading_date"] == "2026-06-03"
    _set.assert_called_once()

# --- from test_macro_news.py ---

from unittest.mock import AsyncMock, patch

import pytest

from trade_sentinel_api.models.schemas import NewsItem
from trade_sentinel_api.services.macro.news import (
    _dedupe_and_sort,
    _normalize_title,
    _parse_rss_xml,
    fetch_macro_news,
)


def test_normalize_title():
    assert _normalize_title("  Hello   World  ") == "hello world"


def test_dedupe_and_sort():
    items = [
        NewsItem(title="Fed holds rates", published_at="2026-01-02T10:00:00+00:00"),
        NewsItem(title="fed holds rates", published_at="2026-01-03T10:00:00+00:00"),
        NewsItem(title="CPI rises", published_at="2026-01-01T10:00:00+00:00"),
    ]
    out = _dedupe_and_sort(items, 10)
    assert len(out) == 2
    assert out[0].title == "Fed holds rates"


def test_parse_rss_xml_minimal():
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Test headline</title>
        <link>https://example.com/a</link>
        <pubDate>Mon, 02 Jun 2026 12:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""
    items = _parse_rss_xml(xml, "Test")
    assert len(items) == 1
    assert items[0].title == "Test headline"
    assert items[0].url == "https://example.com/a"


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.macro.news._fetch_newsapi", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.macro.news._fetch_rss_feed", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.macro.news.fetch_yfinance_news", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.macro.news.fetch_macro_headlines", new_callable=AsyncMock)
async def test_source_gaps_only_when_all_news_empty(
    mock_finnhub, mock_yfinance, mock_rss, mock_newsapi
):
    mock_finnhub.return_value = [NewsItem(title="Fed headline")]
    mock_yfinance.return_value = []
    mock_rss.return_value = ([], "rss_bls_fetch_failed")
    mock_newsapi.return_value = ([], "newsapi_key_missing")

    merged, _counts, gaps = await fetch_macro_news(limit=12)

    assert len(merged) >= 1
    assert "rss_bls_fetch_failed" not in gaps
    assert "yfinance_macro_news_empty" not in gaps

# --- from test_macro_signals.py ---

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from trade_sentinel_api.models.schemas import MacroSignal
from trade_sentinel_api.services.macro.signals import (
    _apply_fred_fallbacks,
    _derive_risk_and_curve,
    _fetch_signal_sync,
    _valid_fred_observations,
    fetch_macro_signals,
)


def test_fetch_signal_sync_rejects_nan_close():
    nan_hist = pd.DataFrame({"Close": [100.0, float("nan")]})
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = nan_hist
    with patch("trade_sentinel_api.services.macro.signals.yf.Ticker", return_value=mock_ticker):
        sig = _fetch_signal_sync("SPY", "S&P 500 (SPY)")
    assert sig.level is None
    assert sig.symbol == "SPY"


def test_valid_fred_observations_skips_dot_values():
    obs = [
        {"date": "2024-01-01", "value": "."},
        {"date": "2024-02-01", "value": "2.5"},
    ]
    valid = _valid_fred_observations(obs)
    assert len(valid) == 1
    assert valid[0][1] == 2.5


def test_derive_risk_elevated_vix():
    signals = [
        MacroSignal(symbol="^VIX", label="VIX", level=25.0),
        MacroSignal(symbol="^TNX", label="10Y", level=4.2),
        MacroSignal(symbol="^IRX", label="3M", level=4.0),
    ]
    curve, tone = _derive_risk_and_curve(signals)
    assert tone == "elevated_vix"
    assert curve == pytest.approx(20.0, abs=0.1)


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.macro.signals._fetch_fred_observations", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.macro.signals.asyncio.to_thread")
async def test_fetch_macro_signals_shape(mock_to_thread, mock_fred):
    mock_fred.return_value = ([], ["fred_api_key_missing"])
    mock_to_thread.side_effect = lambda fn, *args: MacroSignal(
        symbol=args[0], label=args[1], level=100.0, change_1d_pct=1.0
    )

    snap = await fetch_macro_signals()
    assert snap.as_of.tzinfo is not None
    assert len(snap.signals) == 12
    assert "fred_api_key_missing" in snap.data_gaps


def test_apply_fred_fallbacks_t10y2y_proxy():
    signals = [
        MacroSignal(symbol="^TNX", label="10Y", level=4.5),
        MacroSignal(symbol="^FVX", label="5Y", level=4.0),
        MacroSignal(symbol="^IRX", label="3M", level=3.8),
    ]
    official, gaps = _apply_fred_fallbacks(
        signals,
        [],
        ["fred_T10Y2Y_fetch_failed"],
    )
    assert any(o.series_id == "T10Y2Y_PROXY" for o in official)
    assert "fred_T10Y2Y_fetch_failed" not in gaps


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.macro.signals._fetch_fred_series", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.macro.signals.asyncio.to_thread")
async def test_fred_t10y2y_uses_valid_observation_after_dots(mock_to_thread, mock_fred_series):
    mock_to_thread.side_effect = lambda fn, *args: MacroSignal(
        symbol=args[0], label=args[1], level=100.0, change_1d_pct=1.0
    )

    async def fred_side_effect(client, api_key, series_id, limit):
        if series_id == "T10Y2Y":
            return (
                [{"date": "2024-06-01", "value": "."}, {"date": "2024-06-02", "value": "-0.25"}],
                None,
                200,
            )
        return ([{"date": "2024-06-01", "value": "3.5"}], None, 200)

    mock_fred_series.side_effect = fred_side_effect

    from trade_sentinel_api.config import get_settings

    with patch.object(get_settings(), "fred_api_key", "test-key"):
        snap = await fetch_macro_signals()

    t10y2y = [o for o in snap.official if o.series_id == "T10Y2Y"]
    assert len(t10y2y) == 1
    assert t10y2y[0].value == -0.25

# --- from test_macro_release_stats.py ---

from trade_sentinel_api.services.macro.release_stats import (
    build_release_stats,
    enrich_event_release_stats,
)


def test_release_status_released():
    e = enrich_event_release_stats(
        {"name": "CPI", "actual": 3.2, "estimate": 3.0, "impact": "high"}
    )
    assert e["release_status"] == "released"


def test_release_status_scheduled():
    e = enrich_event_release_stats({"name": "ISM Services PMI", "impact": "moderate"})
    assert e["release_status"] == "scheduled"


def test_enrich_beat():
    e = enrich_event_release_stats(
        {"name": "CPI", "actual": 3.2, "estimate": 3.0, "impact": "high"}
    )
    assert e["beat_miss"] == "beat"
    assert e["surprise_pct"] is not None
    assert e["surprise_pct"] > 0


def test_enrich_miss():
    e = enrich_event_release_stats(
        {"name": "Jobs", "actual": 150.0, "estimate": 200.0, "impact": "high"}
    )
    assert e["beat_miss"] == "miss"


def test_enrich_unavailable_without_estimate():
    e = enrich_event_release_stats({"name": "GDP", "actual": 2.1, "impact": "high"})
    assert e["beat_miss"] == "unavailable"
    assert e["surprise_pct"] is None


def test_build_release_stats_counts():
    events = [
        {"name": "A", "beat_miss": "beat", "surprise_pct": 5.0},
        {"name": "B", "beat_miss": "miss", "surprise_pct": -3.0},
        {"name": "C", "beat_miss": "unavailable"},
    ]
    stats = build_release_stats(events)
    assert stats.beats == 1
    assert stats.misses == 1
    assert stats.unavailable == 1
    assert len(stats.largest_surprises) == 2

# --- from test_context_macro.py ---

from unittest.mock import AsyncMock, patch

import pytest

from trade_sentinel_api.models.schemas import (
    ContextSummary,
    EarningsSnapshot,
    FundamentalsSnapshot,
    MacroContextOverlay,
    ValuationAssessment,
)
from trade_sentinel_api.services.context import _build_facts


def test_context_summary_accepts_eight_bullets():
    bullets = [f"bullet {i}" for i in range(8)]
    summary = ContextSummary(bullets=bullets, model="test")
    assert len(summary.bullets) == 8


def test_build_facts_includes_macro_context():
    overlay = MacroContextOverlay(
        trading_date="2026-06-03",
        ticker="AAPL",
        ticker_sector="Technology",
        has_content=True,
        market_weather="Steady macro",
        macro_signals=MacroSignalsSnapshot(as_of=datetime.now(UTC), signals=[]),
    )
    facts = _build_facts(
        "AAPL",
        {"price": 100.0},
        [],
        None,
        FundamentalsSnapshot(sector="Technology"),
        None,
        None,
        None,
        [],
        None,
        None,
        macro_overlay=overlay,
    )
    assert "macro_context" in facts
    assert facts["macro_context"]["ticker_sector"] == "Technology"


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.context.summarize_context", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.resolve_ticker_valuation", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.get_daily_macro_bundle", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.fetch_sec_filings", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.fetch_earnings_snapshot", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.aggregate_market_context", new_callable=AsyncMock)
@patch("trade_sentinel_api.services.context.get_cached", return_value=None)
@patch("trade_sentinel_api.services.context.set_cached")
async def test_build_ticker_context_uses_v4_when_macro_present(
    _set,
    _get,
    mock_market,
    mock_earnings,
    mock_sec,
    mock_macro_bundle,
    mock_resolve_valuation,
    mock_summarize,
):
    from trade_sentinel_api.models.schemas import ContextSummary, SecFilingsFeed
    from trade_sentinel_api.services.context import build_ticker_context

    mock_market.return_value = {
        "price": 50.0,
        "change_pct": 1.0,
        "volume": 1,
        "volume_avg_30d": 1.0,
        "volume_ratio": 1.0,
        "rsi": 55.0,
        "macd": None,
        "price_history": [],
        "news": [],
    }
    mock_earnings.return_value = EarningsSnapshot(data_available=False)
    mock_sec.return_value = SecFilingsFeed(ticker="X", filings=[], data_available=False)
    mock_macro_bundle.return_value = {
        "trading_date": "2026-06-03",
        "events": [
            {"name": "CPI", "impact": "high", "sectors": ["Tech"]},
        ],
        "impact_summary": {"high": 1, "moderate": 0, "noise": 0},
        "macro_signals": MacroSignalsSnapshot(
            as_of=datetime.now(UTC),
            signals=[],
            risk_tone="normal",
        ).model_dump(mode="json"),
        "macro_news": [],
        "data_gaps": [],
    }
    mock_resolve_valuation.return_value = (
        FundamentalsSnapshot(sector="Technology", data_available=True),
        ValuationAssessment(data_available=True, fair_value_mid=45.0, mos_label="fair"),
    )
    mock_summarize.return_value = ContextSummary(
        bullets=["a", "b", "c", "d", "e", "f"],
        model="test",
    )

    ctx = await build_ticker_context("AAPL", summarize=True)

    assert ctx.macro_overlay is not None
    assert ctx.macro_overlay.has_content
    mock_summarize.assert_called_once()
    assert mock_summarize.call_args.kwargs.get("prompt_version") == "v5"
