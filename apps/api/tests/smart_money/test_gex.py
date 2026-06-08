"""Tests for computed GEX and microstructure adjustments."""

from __future__ import annotations

from datetime import UTC, datetime

from trade_sentinel_api.models.schemas import DixProxySnapshot, GammaExposureSnapshot
from trade_sentinel_api.services.microstructure_adjustments import microstructure_adjustment


def test_microstructure_negative_gex_reduces_multiplier():
    gex = GammaExposureSnapshot(
        symbol="SPY",
        as_of=datetime.now(UTC),
        net_gex_usd=-1_000_000,
        regime="negative",
        data_available=True,
    )
    adj = microstructure_adjustment(gex, None)
    assert adj.conviction_multiplier < 1.0


def test_microstructure_elevated_dix_adds_note():
    dix = DixProxySnapshot(
        ticker="SPY",
        as_of=datetime.now(UTC),
        short_volume_ratio=48.0,
        elevated_dark_accumulation=True,
        data_available=True,
    )
    adj = microstructure_adjustment(None, dix)
    assert adj.notes
