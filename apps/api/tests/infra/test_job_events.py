import json

from trade_sentinel_api.services.job_events import (
    _channels_for_event,
    publish_scan_progress,
)


def test_channels_for_event_mapping():
    assert _channels_for_event({"type": "job_started", "name": "digest"}) == {"jobs"}
    ch = _channels_for_event(
        {
            "type": "scan_progress",
            "resource": "market_screener",
            "universe": "sp500",
        }
    )
    assert ch == {"jobs", "screener:sp500"}
    ch2 = _channels_for_event(
        {"type": "digest_rows", "watchlist_name": "default"}
    )
    assert "digest:default" in ch2


def test_websocket_connect_and_snapshot():
    from fastapi.testclient import TestClient

    from trade_sentinel_api.main import app

    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws") as ws:
        raw = ws.receive_text()
        data = json.loads(raw)
        assert data["type"] == "jobs_snapshot"
        assert "jobs" in data
        ws.send_text(
            json.dumps({"action": "subscribe", "channels": ["jobs", "screener:sp500"]})
        )
        raw2 = ws.receive_text()
        assert json.loads(raw2)["type"] == "jobs_snapshot"


def test_publish_scan_progress_payload():
    """Unit test — async broadcast is covered by channel mapping + manual UI check."""
    ch = _channels_for_event(
        {
            "type": "scan_progress",
            "resource": "market_screener",
            "universe": "sp500",
            "completed": 25,
            "total": 100,
        }
    )
    assert "screener:sp500" in ch
    publish_scan_progress(
        resource="market_screener",
        cache_key="2026-01-01:sp500:lite",
        completed=25,
        total=100,
        universe="sp500",
    )


def test_after_chunk_cached_digest_publishes_rows():
    from datetime import UTC, datetime
    from unittest.mock import patch

    from trade_sentinel_api.models.schemas import DigestTickerRow
    from trade_sentinel_api.services.job_events import after_chunk_cached

    row = DigestTickerRow(ticker="AAPL")
    with patch("trade_sentinel_api.services.job_events.publish_scan_progress") as mock_progress:
        with patch("trade_sentinel_api.services.job_events.publish_digest_rows") as mock_rows:
            with patch("trade_sentinel_api.services.job_events.set_cached_ttl"):
                after_chunk_cached(
                    cache_prefix="digest",
                    cache_key="2026-06-05:default:abc",
                    all_rows=[row],
                    chunk_rows=[row],
                    completed=1,
                    total=2,
                    cache_ttl_seconds=3600,
                    cached_at=datetime.now(UTC),
                )

    mock_progress.assert_called_once()
    assert mock_progress.call_args.kwargs["resource"] == "digest"
    mock_rows.assert_called_once()
    assert mock_rows.call_args.kwargs["watchlist_name"] == "default"
