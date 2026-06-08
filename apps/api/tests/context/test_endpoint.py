"""Context endpoint smoke tests — mocked for CI, optional live check via API_URL."""

import os
import time
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.context_mocks import (
    MOCK_MARKET,
    MOCK_SUMMARY,
    patch_context_pipeline,
)
from trade_sentinel_api.main import app
from trade_sentinel_api.models.schemas import TickerContext
from trade_sentinel_api.services import cache as cache_mod

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_memory_cache():
    cache_mod._memory.clear()
    yield
    cache_mod._memory.clear()


@patch_context_pipeline()
def test_context_returns_summary_and_warnings():
    r = client.get("/api/v1/context/TEST?summarize=true")
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "TEST"
    assert data["price"] == 150.25
    assert data["rsi"] == 72.5
    assert len(data["summary"]["bullets"]) == 3
    assert any(w["code"] == "RSI_OVERBOUGHT" for w in data["warnings"])
    assert data["fundamentals"] is not None
    assert data["fundamentals"]["sector"] == "Technology"
    assert "forward_outlook" in data


@patch_context_pipeline()
def test_context_latency_under_10s():
    start = time.perf_counter()
    r = client.get("/api/v1/context/LAT?summarize=true")
    elapsed = time.perf_counter() - start
    assert r.status_code == 200
    assert elapsed < 10.0


@patch(
    "trade_sentinel_api.routers.context.build_ticker_context",
    new_callable=AsyncMock,
)
def test_context_stream_sse_complete(_build):
    _build.return_value = TickerContext(
        ticker="SSE",
        as_of=datetime.now(UTC),
        price=100.0,
        news=[],
        warnings=[],
        summary=MOCK_SUMMARY,
    )
    with client.stream("GET", "/api/v1/context/SSE/stream") as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert '"status": "fetching"' in body
    assert '"status": "complete"' in body
    assert '"ticker": "SSE"' in body or '"ticker":"SSE"' in body


@patch(
    "trade_sentinel_api.services.context.fetch_sec_filings",
    new_callable=AsyncMock,
)
@patch(
    "trade_sentinel_api.services.context.resolve_ticker_valuation",
    new_callable=AsyncMock,
)
@patch(
    "trade_sentinel_api.services.context.fetch_earnings_snapshot",
    new_callable=AsyncMock,
)
@patch(
    "trade_sentinel_api.services.context.aggregate_market_context",
    new_callable=AsyncMock,
)
def test_context_skips_cache_when_market_data_missing(
    _market, _earnings, _valuation, _sec
):
    from tests.fixtures.context_mocks import (
        MOCK_EARNINGS,
        MOCK_FUNDAMENTALS,
        MOCK_SEC_FILINGS,
        MOCK_VALUATION,
    )

    _sec.return_value = MOCK_SEC_FILINGS
    _earnings.return_value = MOCK_EARNINGS
    _valuation.return_value = (MOCK_FUNDAMENTALS, MOCK_VALUATION)

    ticker = f"Z{uuid.uuid4().hex[:6].upper()}"
    _market.return_value = {
        "price": None,
        "change_pct": None,
        "volume": None,
        "volume_avg_30d": None,
        "volume_ratio": None,
        "rsi": None,
        "macd": None,
        "price_history": [],
        "news": [],
        "_hist": None,
    }
    r1 = client.get(f"/api/v1/context/{ticker}?summarize=false")
    assert r1.status_code == 200
    assert r1.json()["price"] is None

    _market.return_value = {**MOCK_MARKET, "_hist": None, "news": []}
    r2 = client.get(f"/api/v1/context/{ticker}?summarize=false")
    assert r2.status_code == 200
    assert r2.json()["price"] == 150.25


@patch_context_pipeline(include_smart_money=True)
def test_context_includes_institutional_13f_with_insider_flag():
    r = client.get("/api/v1/context/TEST?include_insider=true&include_options=true")
    assert r.status_code == 200
    data = r.json()
    assert data["institutional_13f"] is not None
    assert data["institutional_13f"]["data_available"] is True
    assert len(data["institutional_13f"]["changes"]) == 1
    assert data["smart_money_assessment"] is not None


@pytest.mark.live
def test_context_live_smoke():
    """Run against a running API: API_URL=http://localhost:8000 pytest -m live."""
    import httpx

    base = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
    ticker = os.environ.get("SMOKE_TICKER", "AAPL")
    start = time.perf_counter()
    with httpx.Client(timeout=30.0) as http:
        health = http.get(f"{base}/health")
        assert health.status_code == 200

        r = http.get(
            f"{base}/api/v1/context/{ticker}",
            params={"summarize": "true", "include_insider": "true"},
        )
        elapsed = time.perf_counter() - start
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ticker"] == ticker.upper()
        assert len(data.get("summary", {}).get("bullets", [])) >= 3
        assert elapsed < 30.0, f"context took {elapsed:.1f}s (limit 30s)"
