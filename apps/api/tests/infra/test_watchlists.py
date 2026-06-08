"""Merged from: test_watchlists.py, test_watchlists_api.py"""

# --- from test_watchlists.py ---

import pytest

from trade_sentinel_api.db import use_postgres, watchlist_get, watchlist_set


def test_watchlist_sqlite_roundtrip():
    if use_postgres():
        pytest.skip("Postgres configured; sqlite watchlist path not active")
    watchlist_set("default", ["aapl", "nvda", "aapl"])
    tickers = watchlist_get("default")
    assert tickers == ["AAPL", "NVDA"]


@pytest.mark.skipif(not use_postgres(), reason="DATABASE_URL not set to PostgreSQL")
def test_watchlist_postgres_roundtrip():
    watchlist_set("default", ["tsla", "meta"])
    tickers = watchlist_get("default")
    assert "TSLA" in tickers
    assert "META" in tickers

# --- from test_watchlists_api.py ---

from fastapi.testclient import TestClient

from trade_sentinel_api.main import app

client = TestClient(app)


def test_get_default_watchlist_returns_200():
    resp = client.get("/api/v1/watchlists/default")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "default"
    assert isinstance(data["tickers"], list)


def test_patch_add_and_remove_tickers():
    client.put("/api/v1/watchlists/patch_test", json={"tickers": ["AAA"]})
    resp = client.patch(
        "/api/v1/watchlists/patch_test/tickers",
        json={"add": ["BBB", "CCC"], "remove": []},
    )
    assert resp.status_code == 200
    assert resp.json()["tickers"] == ["AAA", "BBB", "CCC"]

    resp2 = client.patch(
        "/api/v1/watchlists/patch_test/tickers",
        json={"add": [], "remove": ["AAA"]},
    )
    assert resp2.status_code == 200
    assert resp2.json()["tickers"] == ["BBB", "CCC"]

    client.put("/api/v1/watchlists/patch_test", json={"tickers": []})


def test_digest_refresh_query_param():
    resp = client.get("/api/v1/digest/today?refresh=true")
    assert resp.status_code == 200
    assert "trading_date" in resp.json()
