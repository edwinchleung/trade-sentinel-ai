"""Merged from: test_sec_13f.py, test_sec_13dg.py"""

# --- from test_sec_13f.py ---

from unittest.mock import patch

import pytest

from trade_sentinel_api.models.schemas import Institutional13FChange
from trade_sentinel_api.services.sec.adapter import thirteenf_to_holdings
from trade_sentinel_api.services.institutional_crowding import compute_hhi, crowding_risk_from_hhi
from trade_sentinel_api.services.sec.form13f import (
    _classify_change,
    _conviction_from_changes,
    _match_holding,
    build_cusip_ticker_index,
    scan_institutional_conviction,
)


def test_classify_change_new_position():
    assert _classify_change(0, 1000) == "new"


def test_classify_change_exit():
    assert _classify_change(5000, 0) == "exit"


def test_classify_change_increased_25pct():
    assert _classify_change(100, 130) == "increased"


def test_classify_change_decreased_25pct():
    assert _classify_change(100, 70) == "decreased"


def test_classify_change_held_small_delta():
    assert _classify_change(100, 110) == "held"


def test_thirteenf_to_holdings_nested_shares_and_value_scale():
    from unittest.mock import MagicMock

    import pandas as pd

    obj = MagicMock()
    obj.report_period = "2024-12-31"
    obj.infotable = pd.DataFrame(
        [
            {
                "Issuer": "APPLE INC",
                "Cusip": "037833100",
                "Value": 6339546,
                "SharesPrnAmount": 30099451,
            }
        ]
    )
    holdings, quarter_end = thirteenf_to_holdings(obj)
    assert quarter_end == "2024-12-31"
    assert len(holdings) == 1
    assert holdings[0]["name"] == "APPLE INC"
    assert holdings[0]["shares"] == 30099451
    assert holdings[0]["value"] == 6339546000


def test_cusip_match_preferred_over_name():
    holdings = [
        {"cusip": "037833100", "name": "APPLE INC", "shares": 1000},
        {"cusip": "999999999", "name": "ON SEMICONDUCTOR", "shares": 500},
    ]
    cusip_map = {"AAPL": "037833100"}
    match = _match_holding("AAPL", holdings, cusip_map=cusip_map)
    assert match is not None
    assert match["cusip"] == "037833100"


def test_hhi_high_concentration():
    hhi = compute_hhi([900, 100])
    assert hhi is not None
    assert hhi > 0.8
    assert crowding_risk_from_hhi(hhi) == "high"


def test_build_cusip_ticker_index_inverts_map():
    idx = build_cusip_ticker_index({"AAPL": "037833100", "MSFT": "594918104"})
    assert idx["037833100"] == "AAPL"
    assert idx["594918104"] == "MSFT"


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.sec.form13f._refresh_filer_holdings_sync")
@patch("trade_sentinel_api.services.sec.form13f.resolve_scan_universe")
async def test_scan_institutional_conviction_filters_universe(mock_resolve, mock_refresh):
    mock_resolve.return_value = ("sp500", ["AAPL", "MSFT"], "sp500")
    mock_refresh.return_value = ({
        "AAPL": [
            Institutional13FChange(
                filer_name="Fund A",
                filer_cik="0000000001",
                ticker="AAPL",
                change_type="new",
            ),
            Institutional13FChange(
                filer_name="Fund B",
                filer_cik="0000000002",
                ticker="AAPL",
                change_type="increased",
            ),
        ],
        "TSLA": [
            Institutional13FChange(
                filer_name="Fund C",
                filer_cik="0000000003",
                ticker="TSLA",
                change_type="new",
            ),
            Institutional13FChange(
                filer_name="Fund D",
                filer_cik="0000000004",
                ticker="TSLA",
                change_type="increased",
            ),
        ],
    }, {"filers_refreshed": 2, "tickers_mapped": 2})

    result = await scan_institutional_conviction("sp500", refresh=True)
    assert result.universe == "sp500"
    assert [r.ticker for r in result.rows] == ["AAPL"]
    assert result.rows[0].filer_count == 2


def test_conviction_from_changes_requires_new_or_increased():
    changes = [
        Institutional13FChange(
            filer_name="A",
            filer_cik="1",
            ticker="X",
            change_type="new",
        ),
        Institutional13FChange(
            filer_name="B",
            filer_cik="2",
            ticker="X",
            change_type="increased",
        ),
    ]
    assert _conviction_from_changes(changes) is True


def test_load_filer_cache_tolerates_empty_or_corrupt_file(tmp_path, monkeypatch):
    from trade_sentinel_api.services.sec import form13f as sec_13f

    monkeypatch.setattr(sec_13f, "_CACHE_DIR", tmp_path)
    bad = tmp_path / "0001364742.json"
    bad.write_text("", encoding="utf-8")

    assert sec_13f._load_filer_cache("0001364742") == []

    bad.write_text("{not-json", encoding="utf-8")
    assert sec_13f._load_filer_cache("0001364742") == []
    assert not bad.exists()


def test_save_filer_quarter_round_trip(tmp_path, monkeypatch):
    from trade_sentinel_api.services.sec import form13f as sec_13f

    monkeypatch.setattr(sec_13f, "_CACHE_DIR", tmp_path)
    holdings = [{"cusip": "037833100", "name": "APPLE INC", "shares": 100.0, "value": 1e6}]
    sec_13f._save_filer_quarter("0001364742", "2024-12-31", holdings, "2025-02-14")

    cached = sec_13f._load_filer_cache("0001364742")
    assert len(cached) == 1
    assert cached[0]["quarter_end"] == "2024-12-31"
    assert cached[0]["holdings"][0]["cusip"] == "037833100"

# --- from test_sec_13dg.py ---

from unittest.mock import MagicMock, patch

from trade_sentinel_api.services.sec.adapter import _parse_float, filing_to_activist_item


def test_filing_to_activist_item_maps_fields():
    filing = MagicMock()
    filing.form = "SC 13D"
    filing.filing_date = "2026-01-15"
    filing.filing_url = "https://www.sec.gov/example"
    filing.company = "ACME CORP"
    filing.cik = "0000320193"
    person = MagicMock()
    person.name = "Activist Fund LP"
    obj = MagicMock()
    obj.reporting_persons = [person]
    obj.total_percent = 5.2
    obj.issuer_info = None
    with patch(
        "trade_sentinel_api.services.sec.adapter.parse_filing",
        return_value=(obj, None),
    ):
        item = filing_to_activist_item(filing, form_type="13D")
    assert item.ticker is not None or item.company_name == "ACME CORP"
    assert item.form_type == "13D"
    assert item.filer_name == "Activist Fund LP"
    assert item.percent_owned == 5.2


def test_parse_float_strips_percent():
    assert _parse_float("5.2%") == 5.2
    assert _parse_float("12.5") == 12.5
