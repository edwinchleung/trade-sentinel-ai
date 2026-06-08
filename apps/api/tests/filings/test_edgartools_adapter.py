"""EdgarTools adapter unit tests (mocked objects)."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from trade_sentinel_api.services.sec.adapter import (
    eightk_to_highlight,
    fetch_schedule13_by_date_range,
    form4_to_parsed_dict,
    normalize_generic,
    parse_filing,
    schedule13_edgar_form,
    schedule13_to_activist_fields,
    thirteenf_to_holdings,
)


def test_parse_filing_returns_none_on_error():
    filing = MagicMock()
    filing.obj.side_effect = RuntimeError("boom")
    obj, err = parse_filing(filing)
    assert obj is None
    assert err is not None


def test_form4_to_parsed_dict_from_activities():
    filing = MagicMock()
    filing.filing_date = "2026-05-01"
    tx = MagicMock()
    tx.code = "P"
    tx.code_description = "Purchase"
    tx.shares = 1000
    tx.price_per_share = 42.5
    tx.is_derivative = False
    obj = MagicMock()
    obj.insider_name = "Jane Doe"
    obj.position = "CEO"
    obj.issuer = None
    obj.get_transaction_activities.return_value = [tx]
    parsed = form4_to_parsed_dict(filing, obj)
    assert parsed["insider_name"] == "Jane Doe"
    assert parsed["transactions"][0]["transaction_code"] == "P"


def test_thirteenf_to_holdings_scales_value():
    obj = MagicMock()
    obj.report_period = "2024-12-31"
    obj.infotable = pd.DataFrame([{"Issuer": "X", "Cusip": "123", "Value": 100, "SharesPrnAmount": 10}])
    holdings, q = thirteenf_to_holdings(obj)
    assert q == "2024-12-31"
    assert holdings[0]["value"] == 100_000


def test_schedule13_to_activist_fields():
    filing = MagicMock()
    person = MagicMock()
    person.name = "Big Fund"
    obj = MagicMock()
    obj.reporting_persons = [person]
    obj.total_percent = "7.5%"
    name, pct = schedule13_to_activist_fields(filing, obj, form_type="13D")
    assert name == "Big Fund"
    assert pct == 7.5


def test_schedule13_edgar_form_maps_registry_keys():
    assert schedule13_edgar_form("SC 13D") == "SCHEDULE 13D"
    assert schedule13_edgar_form("SC 13G") == "SCHEDULE 13G"


def test_fetch_schedule13_by_date_range_collects_in_window():
    filing = MagicMock()
    filing.form = "SC 13D"
    filing.filing_date = "2026-05-15"

    filings = MagicMock()
    filings.head.return_value = [filing]

    with patch("trade_sentinel_api.services.sec.adapter._ensure_edgar"):
        with patch("edgar.get_filings", return_value=filings) as mock_get:
            result = fetch_schedule13_by_date_range(
                date(2026, 5, 1),
                date(2026, 5, 31),
                registry_form="SC 13D",
                max_entries=10,
            )

    mock_get.assert_called()
    assert mock_get.call_args.kwargs["form"] == "SCHEDULE 13D"
    assert len(result) == 1
    assert result[0].filing_date == "2026-05-15"


def test_eightk_to_highlight_includes_items():
    filing = MagicMock()
    filing.form = "8-K"
    filing.filing_date = "2025-01-15"
    filing.filing_url = "https://sec.gov/8k"
    filing.accession_no = None
    filing.accession_number = None
    obj = MagicMock()
    obj.items = ["2.02", "9.01"]
    highlight = eightk_to_highlight(filing, obj, form="8-K")
    assert highlight.form == "8-K"
    assert highlight.event_items == ["2.02", "9.01"]


def test_normalize_generic_text_fallback():
    filing = MagicMock()
    filing.form = "CORRESP"
    filing.filing_date = "2025-01-01"
    filing.filing_url = "https://sec.gov/c"
    filing.company = "Example Co"
    filing.text.return_value = "Letter content " * 20
    with patch(
        "trade_sentinel_api.services.sec.adapter.parse_filing",
        return_value=(None, "unsupported"),
    ):
        payload = normalize_generic(filing, spec=MagicMock(supports_obj=False))
    assert payload["form"] == "CORRESP"
    assert payload.get("text_excerpt")
