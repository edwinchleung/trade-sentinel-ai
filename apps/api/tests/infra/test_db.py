"""Merged from: test_db_cache.py, test_db_journal.py, test_watchlist_cache.py"""

# --- from test_db_cache.py ---

import pytest

from trade_sentinel_api.db import (
    _decode_cache_payload,
    _json_safe,
    cache_get,
    cache_set,
    use_postgres,
)


def test_json_safe_strips_nan_and_inf():
    payload = {
        "macro_signals": {
            "signals": [{"symbol": "SPY", "label": "S&P 500 (SPY)", "level": float("nan")}],
        }
    }
    cleaned = _json_safe(payload)
    assert cleaned["macro_signals"]["signals"][0]["level"] is None


def test_decode_cache_payload_empty_string():
    assert _decode_cache_payload("") == ""


def test_decode_cache_payload_plain_string():
    assert _decode_cache_payload("excerpt text") == "excerpt text"


def test_decode_cache_payload_json_object():
    assert _decode_cache_payload('{"a": 1}') == {"a": 1}


@pytest.mark.skipif(not use_postgres(), reason="DATABASE_URL not set to PostgreSQL")
def test_cache_roundtrip_postgres():
    import time

    key = "test:cache:roundtrip"
    payload = {"price": 123.45, "ticker": "TEST"}
    expires = time.time() + 60
    cache_set(key, payload, expires)
    loaded = cache_get(key)
    assert loaded is not None
    assert loaded["price"] == 123.45


@pytest.mark.skipif(not use_postgres(), reason="DATABASE_URL not set to PostgreSQL")
def test_cache_roundtrip_postgres_empty_string_negative_cache():
    import time

    key = "test:cache:empty_excerpt"
    expires = time.time() + 60
    cache_set(key, "", expires)
    assert cache_get(key) == ""

# --- from test_db_journal.py ---

import pytest

from trade_sentinel_api.db import use_postgres
from trade_sentinel_api.models.schemas import TradeJournalCreate
from trade_sentinel_api.services.journal import create_journal_entry, list_journal_entries


@pytest.mark.skipif(not use_postgres(), reason="DATABASE_URL not set to PostgreSQL")
def test_journal_roundtrip_postgres():
    entry = create_journal_entry(
        TradeJournalCreate(
            ticker="TEST",
            direction="long",
            quantity=1,
            entry_price=100,
            account_size=10000,
            instrument_type="stock",
            ai_warnings=["test warning"],
        )
    )
    assert entry.id is not None
    rows = list_journal_entries()
    assert any(r.ticker == "TEST" for r in rows)


def test_journal_sqlite_fallback():
    """SQLite path works when DATABASE_URL is empty (default in CI)."""
    if use_postgres():
        pytest.skip("Postgres configured; sqlite fallback not active")
    entry = create_journal_entry(
        TradeJournalCreate(
            ticker="SQLTEST",
            direction="long",
            quantity=2,
            entry_price=50,
            account_size=5000,
            instrument_type="stock",
            ai_warnings=[],
        )
    )
    assert entry.ticker == "SQLTEST"
    assert any(e.ticker == "SQLTEST" for e in list_journal_entries())

# --- from test_watchlist_cache.py ---

from trade_sentinel_api.services.watchlists import watchlist_ticker_fingerprint


def test_fingerprint_changes_when_tickers_change():
    a = watchlist_ticker_fingerprint(["nvda", "aapl"])
    b = watchlist_ticker_fingerprint(["nvda", "aapl", "tsla"])
    assert a != b


def test_fingerprint_stable_for_order():
    assert watchlist_ticker_fingerprint(["b", "a"]) == watchlist_ticker_fingerprint(
        ["a", "b"]
    )
