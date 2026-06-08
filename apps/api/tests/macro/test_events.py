from datetime import date

import pytest

from trade_sentinel_api.models.schemas import InsiderTransaction
from trade_sentinel_api.services.sec.edgar import summarize_insider_activity
from trade_sentinel_api.services.macro.calendar import (
    _events_from_schedule,
    _is_first_friday,
    get_macro_events_for_day,
    map_event_sectors,
)


def test_events_from_schedule_thursday_jobless_claims():
    events = _events_from_schedule(date(2026, 6, 4))
    names = [e["name"] for e in events]
    assert "Initial Jobless Claims" in names


def test_is_first_friday():
    assert _is_first_friday(date(2026, 6, 5)) is True
    assert _is_first_friday(date(2026, 6, 12)) is False


def test_nfp_only_first_friday():
    events = _events_from_schedule(date(2026, 6, 5))
    names = [e["name"] for e in events]
    assert "Non-Farm Payrolls" in names
    events_second = _events_from_schedule(date(2026, 6, 12))
    assert "Non-Farm Payrolls" not in [e["name"] for e in events_second]


def test_map_event_sectors_ism():
    sectors = map_event_sectors("ISM Services PMI")
    assert "Services" in sectors or "Industrials" in sectors


def test_map_event_sectors_eia():
    sectors = map_event_sectors("EIA Crude Oil Stocks Change")
    assert "Energy" in sectors


@pytest.mark.asyncio
async def test_get_macro_events_for_day_includes_date():
    events = await get_macro_events_for_day(date(2026, 6, 4))
    assert len(events) >= 1
    assert all("name" in e and "impact" in e for e in events)


@pytest.mark.asyncio
async def test_get_macro_events_empty_day_no_fallback():
    """Quiet days should return empty list, not fake CPI/FOMC."""
    events = await get_macro_events_for_day(date(2026, 1, 1))
    for e in events:
        assert e["name"] not in ("CPI Release", "FOMC Rate Decision", "Geopolitical Headlines")


def test_summarize_insider_activity_accumulation():
    recent = date(2026, 5, 15).isoformat()
    txs = [
        InsiderTransaction(
            filing_date=recent,
            insider_name="CEO",
            transaction_type="Purchase",
            transaction_code="P",
            is_open_market=True,
            shares=10000,
            price=50,
        ),
        InsiderTransaction(
            filing_date=recent,
            insider_name="CFO",
            transaction_type="Purchase",
            transaction_code="P",
            is_open_market=True,
            shares=5000,
            price=40,
        ),
    ]
    summary = summarize_insider_activity(txs)
    assert summary.sentiment == "accumulation"
    assert summary.net_shares_90d == 15000
    assert summary.data_available is True
