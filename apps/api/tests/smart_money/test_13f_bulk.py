"""Tests for SEC bulk 13F index and ingest helpers."""

from __future__ import annotations

from trade_sentinel_api.services.sec.form13f import _changes_from_bulk_rows, _classify_change
from trade_sentinel_api.services.sec.form13f_bulk import parse_infotable_rows, quarter_key_from_label


def test_quarter_key_from_label():
    assert quarter_key_from_label("2024q4") == "2024Q4"


def test_parse_infotable_rows_maps_ticker():
    infotable = [
        {
            "accessionNumber": "0001-24-000001",
            "cusip": "037833100",
            "nameOfIssuer": "APPLE INC",
            "sshPrnamt": "1000",
            "value": "150000",
            "reportCalendarOrQuarter": "2024-12-31",
        }
    ]
    submissions = [
        {
            "accessionNumber": "0001-24-000001",
            "cik": "1364742",
            "companyName": "BlackRock Inc.",
            "filingDate": "2025-02-14",
        }
    ]
    sub_map = {s["accessionNumber"]: s for s in submissions}
    rows = parse_infotable_rows(infotable, submission_map=sub_map, cusip_map={"AAPL": "037833100"})
    assert len(rows) == 1
    assert rows[0][4] == "AAPL"
    assert rows[0][5] == 1000


def test_changes_from_bulk_rows_detects_increase():
    rows = [
        {
            "quarter_end": "2024-12-31",
            "filer_cik": "0001364742",
            "filer_name": "BlackRock",
            "cusip": "037833100",
            "ticker": "AAPL",
            "shares": 2000,
            "value_usd": 300000,
        },
        {
            "quarter_end": "2024-09-30",
            "filer_cik": "0001364742",
            "filer_name": "BlackRock",
            "cusip": "037833100",
            "ticker": "AAPL",
            "shares": 1000,
            "value_usd": 150000,
        },
    ]
    changes, shares, q = _changes_from_bulk_rows("AAPL", rows)
    assert q == "2024-12-31"
    assert len(changes) == 1
    assert changes[0].change_type == "increased"
    assert len(shares) == 1


def test_classify_change_new():
    assert _classify_change(None, 100) == "new"
