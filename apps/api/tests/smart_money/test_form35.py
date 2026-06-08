"""Tests for Form 3/5 adapter helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from trade_sentinel_api.services.sec.adapter import (
    fetch_form3_by_date_range,
    form3_to_baseline_dict,
)


def test_form3_to_baseline_dict():
    filing = SimpleNamespace(filing_date="2024-06-01")
    obj = MagicMock()
    obj.reporting_owner_name = "Jane CFO"
    obj.officer_title = "CFO"
    obj.to_dataframe.side_effect = Exception("no df")
    baseline = form3_to_baseline_dict(filing, obj)
    assert baseline["insider_name"] == "Jane CFO"
    assert baseline["source_form"] == "3"


@patch("edgar.get_filings")
@patch("trade_sentinel_api.services.sec.adapter._ensure_edgar")
def test_fetch_form3_by_date_range(mock_edgar, mock_get):
    from datetime import date

    filing = SimpleNamespace(form="3", filing_date="2024-06-02")
    mock_get.return_value.head.return_value = [filing]
    result = fetch_form3_by_date_range(date(2024, 6, 1), date(2024, 6, 3), max_entries=10)
    assert len(result) == 1
