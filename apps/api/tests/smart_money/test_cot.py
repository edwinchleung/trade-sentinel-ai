"""COT report ZIP download and parsing tests."""

import csv
import io
import zipfile
from unittest.mock import MagicMock, patch

import httpx

from trade_sentinel_api.services.cot_report import (
    _download_cot_rows,
    _extract_csv_from_zip,
    _fetch_sync,
)


def _make_cot_zip(rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    text = io.StringIO()
    writer = csv.DictWriter(
        text,
        fieldnames=[
            "Market_and_Exchange_Names",
            "Report_Date_as_YYYY-MM-DD",
            "Comm_Positions_Long_All",
            "Comm_Positions_Short_All",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("deacot2025.txt", text.getvalue())
    return buf.getvalue()


def test_extract_csv_from_zip():
    data = _make_cot_zip(
        [
            {
                "Market_and_Exchange_Names": "E-MINI S&P 500",
                "Report_Date_as_YYYY-MM-DD": "2025-01-07",
                "Comm_Positions_Long_All": "100",
                "Comm_Positions_Short_All": "50",
            }
        ]
    )
    text = _extract_csv_from_zip(data)
    assert "E-MINI S&P 500" in text


def test_fetch_sync_parses_zip_positions():
    from trade_sentinel_api.services.cot_report import _parse_cot_csv

    zip_bytes = _make_cot_zip(
        [
            {
                "Market_and_Exchange_Names": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
                "Report_Date_as_YYYY-MM-DD": "2025-01-07",
                "Comm_Positions_Long_All": "200000",
                "Comm_Positions_Short_All": "50000",
            },
            {
                "Market_and_Exchange_Names": "GOLD - COMMODITY EXCHANGE INC.",
                "Report_Date_as_YYYY-MM-DD": "2025-01-07",
                "Comm_Positions_Long_All": "10000",
                "Comm_Positions_Short_All": "30000",
            },
        ]
    )
    rows = _parse_cot_csv(_extract_csv_from_zip(zip_bytes))

    with patch("trade_sentinel_api.services.cot_report._download_cot_rows", return_value=rows):
        report = _fetch_sync(["ES", "GC"])

    assert report.data_available
    assert len(report.positions) == 2
    assert report.positions[0].symbol == "ES"
    assert report.positions[0].commercial_net == 150000.0


def test_download_cot_rows_falls_back_on_404():
    responses = {
        "https://www.cftc.gov/files/dea/history/deacot2026.zip": httpx.Response(404, request=MagicMock()),
        "https://www.cftc.gov/files/dea/history/deacot2025.zip": httpx.Response(
            200,
            request=MagicMock(),
            content=_make_cot_zip(
                [
                    {
                        "Market_and_Exchange_Names": "E-MINI S&P 500",
                        "Report_Date_as_YYYY-MM-DD": "2025-01-07",
                        "Comm_Positions_Long_All": "1",
                        "Comm_Positions_Short_All": "0",
                    }
                ]
            ),
        ),
    }

    def fake_get(url: str):
        return responses[url]

    mock_client = MagicMock()
    mock_client.get.side_effect = fake_get

    with patch("trade_sentinel_api.services.cot_report.datetime") as mock_dt:
        mock_dt.now.return_value.year = 2026
        rows = _download_cot_rows(mock_client)

    assert len(rows) == 1
    assert mock_client.get.call_count == 2
