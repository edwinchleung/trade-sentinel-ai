"""Tests for options tick sweep detection."""

from __future__ import annotations

from trade_sentinel_api.services.providers.polygon_options_ticks import _detect_sweeps


def test_detect_sweeps_groups_nearby_trades():
    trades = [
        {
            "details": {"strike_price": 100, "expiration_date": "2026-07-01", "contract_type": "call"},
            "size": 50,
            "price": 2.5,
            "sip_timestamp": 1_000_000_000,
        },
        {
            "details": {"strike_price": 100, "expiration_date": "2026-07-01", "contract_type": "call"},
            "size": 60,
            "price": 2.6,
            "sip_timestamp": 1_000_200_000,
        },
    ]
    sweeps = _detect_sweeps(trades, underlying="AAPL")
    assert len(sweeps) == 1
    assert sweeps[0].is_sweep is True
    assert sweeps[0].total_size == 110
