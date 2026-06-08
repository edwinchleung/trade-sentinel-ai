"""Finnhub calendar merge and partial earnings semantics."""

from trade_sentinel_api.models.schemas import EarningsSnapshot
from trade_sentinel_api.services.earnings import _merge_earnings_snapshot


def test_merge_fills_next_date_from_calendar():
    base = EarningsSnapshot(
        last_eps_actual=1.2,
        last_eps_estimate=1.1,
        surprise_pct=9.0,
        data_available=True,
    )
    upcoming = {
        "next_report_date": "2026-08-20",
        "days_until": 78,
        "last_revenue_estimate": 1e10,
    }
    merged = _merge_earnings_snapshot(base, upcoming, None)
    assert merged.next_report_date == "2026-08-20"
    assert merged.days_until == 78
    assert merged.last_revenue_estimate == 1e10
    assert merged.data_available is True


def test_merge_partial_message_when_no_next_date():
    base = EarningsSnapshot(
        last_eps_actual=2.0,
        data_available=True,
    )
    merged = _merge_earnings_snapshot(base, None, None)
    assert merged.next_report_date is None
    assert merged.data_available is True
    assert merged.message == "Next earnings date unavailable from data providers."
