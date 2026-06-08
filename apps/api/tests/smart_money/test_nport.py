"""Tests for N-PORT fund CIK mapping and bulk ingest."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest

from trade_sentinel_api.services.sec.bulk_storage import upsert_nport_holdings_rows
from trade_sentinel_api.services.sec.nport_bulk import (
    fund_cik_for_ticker,
    ingest_nport_zip,
    parse_nport_holdings_rows,
    query_nport_holdings,
    target_fund_ciks,
)


@pytest.fixture
def bulk_root(tmp_path, monkeypatch):
    root = tmp_path / "sec_bulk"
    root.mkdir()
    monkeypatch.setattr(
        "trade_sentinel_api.services.sec.bulk_storage.bulk_data_root",
        lambda: root,
    )
    return root


def test_fund_cik_for_spy():
    assert fund_cik_for_ticker("SPY") == "0000884394"


def test_fund_cik_unknown():
    assert fund_cik_for_ticker("ZZZZ") is None


def test_target_fund_ciks_defaults_to_tracked_etfs():
    ciks = target_fund_ciks()
    assert "0000884394" in ciks
    assert len(ciks) == 5


def test_parse_nport_holdings_joins_tsv_tables():
    acc = "0000884394-24-000001"
    rows, archive = parse_nport_holdings_rows(
        submissions=[{"ACCESSION_NUMBER": acc, "REPORT_DATE": "2024-12-31"}],
        registrants=[{"ACCESSION_NUMBER": acc, "CIK": "884394", "REGISTRANT_NAME": "SPDR Trust"}],
        fund_info=[{"ACCESSION_NUMBER": acc, "SERIES_NAME": "SPDR S&P 500 ETF Trust"}],
        holdings=[
            {
                "ACCESSION_NUMBER": acc,
                "HOLDING_ID": "1",
                "ISSUER_NAME": "Apple Inc",
                "ISSUER_CUSIP": "037833100",
                "CURRENCY_VALUE": "1000000",
                "PERCENTAGE": "7.5",
                "ASSET_CAT": "EC",
            }
        ],
        identifiers=[{"HOLDING_ID": "1", "IDENTIFIER_TICKER": "AAPL"}],
    )
    assert len(rows) == 1
    assert rows[0][1] == "0000884394"
    assert rows[0][2] == "SPDR S&P 500 ETF Trust"
    assert rows[0][3] == "Apple Inc"
    assert rows[0][5] == "AAPL"
    assert archive[0]["fund_cik"] == "0000884394"


def test_parse_nport_large_fair_value_exceeds_pg_integer():
    """SPY-scale holdings can exceed Postgres INTEGER max (~2.1B USD)."""
    acc = "0000884394-24-000001"
    rows, _ = parse_nport_holdings_rows(
        submissions=[{"ACCESSION_NUMBER": acc, "REPORT_DATE": "2024-12-31"}],
        registrants=[{"ACCESSION_NUMBER": acc, "CIK": "884394"}],
        fund_info=[{"ACCESSION_NUMBER": acc, "SERIES_NAME": "SPDR S&P 500 ETF Trust"}],
        holdings=[
            {
                "ACCESSION_NUMBER": acc,
                "HOLDING_ID": "1",
                "ISSUER_NAME": "Mega Cap Inc",
                "ISSUER_CUSIP": "037833100",
                "CURRENCY_VALUE": "3500000000",
                "PERCENTAGE": "7.5",
                "ASSET_CAT": "EC",
            }
        ],
    )
    assert len(rows) == 1
    assert rows[0][7] == 3_500_000_000


def test_parse_nport_filters_non_target_ciks():
    spy_acc = "0000884394-24-000001"
    other_acc = "0000999999-24-000001"
    rows, archive = parse_nport_holdings_rows(
        submissions=[
            {"ACCESSION_NUMBER": spy_acc, "REPORT_DATE": "2024-12-31"},
            {"ACCESSION_NUMBER": other_acc, "REPORT_DATE": "2024-12-31"},
        ],
        registrants=[
            {"ACCESSION_NUMBER": spy_acc, "CIK": "884394"},
            {"ACCESSION_NUMBER": other_acc, "CIK": "999999"},
        ],
        fund_info=[
            {"ACCESSION_NUMBER": spy_acc, "SERIES_NAME": "SPDR S&P 500 ETF Trust"},
            {"ACCESSION_NUMBER": other_acc, "SERIES_NAME": "Other Fund"},
        ],
        holdings=[
            {
                "ACCESSION_NUMBER": spy_acc,
                "HOLDING_ID": "1",
                "ISSUER_NAME": "Apple Inc",
                "ISSUER_CUSIP": "037833100",
                "CURRENCY_VALUE": "1000000",
                "PERCENTAGE": "7.5",
                "ASSET_CAT": "EC",
            },
            {
                "ACCESSION_NUMBER": other_acc,
                "HOLDING_ID": "2",
                "ISSUER_NAME": "Microsoft Corp",
                "ISSUER_CUSIP": "594918104",
                "CURRENCY_VALUE": "500000",
                "PERCENTAGE": "4.0",
                "ASSET_CAT": "EC",
            },
        ],
        target_ciks={"0000884394"},
    )
    assert len(rows) == 1
    assert rows[0][1] == "0000884394"
    assert archive[0]["holding_name"] == "Apple Inc"


def _write_tsv(name: str, rows: list[dict[str, str]]) -> tuple[str, bytes]:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)
    return name, buf.getvalue().encode("utf-8")


def _make_nport_zip(tmp_path: Path, *, include_other_fund: bool = False) -> Path:
    spy_acc = "0000884394-24-000001"
    other_acc = "0000999999-24-000001"
    submissions = [{"ACCESSION_NUMBER": spy_acc, "REPORT_DATE": "2024-12-31"}]
    registrants = [{"ACCESSION_NUMBER": spy_acc, "CIK": "884394", "REGISTRANT_NAME": "SPDR Trust"}]
    fund_info = [{"ACCESSION_NUMBER": spy_acc, "SERIES_NAME": "SPDR S&P 500 ETF Trust"}]
    holdings = [
        {
            "ACCESSION_NUMBER": spy_acc,
            "HOLDING_ID": "1",
            "ISSUER_NAME": "Apple Inc",
            "ISSUER_CUSIP": "037833100",
            "CURRENCY_VALUE": "1000000",
            "PERCENTAGE": "7.5",
            "ASSET_CAT": "EC",
        }
    ]
    identifiers = [{"HOLDING_ID": "1", "IDENTIFIER_TICKER": "AAPL"}]

    if include_other_fund:
        submissions.append({"ACCESSION_NUMBER": other_acc, "REPORT_DATE": "2024-12-31"})
        registrants.append({"ACCESSION_NUMBER": other_acc, "CIK": "999999", "REGISTRANT_NAME": "Other Fund"})
        fund_info.append({"ACCESSION_NUMBER": other_acc, "SERIES_NAME": "Other Fund Series"})
        holdings.append(
            {
                "ACCESSION_NUMBER": other_acc,
                "HOLDING_ID": "2",
                "ISSUER_NAME": "Microsoft Corp",
                "ISSUER_CUSIP": "594918104",
                "CURRENCY_VALUE": "500000",
                "PERCENTAGE": "4.0",
                "ASSET_CAT": "EC",
            }
        )
        identifiers.append({"HOLDING_ID": "2", "IDENTIFIER_TICKER": "MSFT"})

    files = [
        _write_tsv("SUBMISSION.tsv", submissions),
        _write_tsv("REGISTRANT.tsv", registrants),
        _write_tsv("FUND_REPORTED_INFO.tsv", fund_info),
        _write_tsv("FUND_REPORTED_HOLDING.tsv", holdings),
        _write_tsv("IDENTIFIERS.tsv", identifiers),
    ]
    zip_path = tmp_path / "2024q4_nport.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, data in files:
            zf.writestr(name, data)
    return zip_path


@pytest.mark.parametrize("use_zip", [False, True])
def test_nport_ingest_and_query(tmp_path, use_zip, bulk_root):
    from trade_sentinel_api.db import sec_index_connection

    if use_zip:
        zip_path = _make_nport_zip(tmp_path)
        result = ingest_nport_zip(zip_path, quarter_key="2024Q4")
    else:
        acc = "0000884394-24-000001"
        rows, _ = parse_nport_holdings_rows(
            submissions=[{"ACCESSION_NUMBER": acc, "REPORT_DATE": "2024-12-31"}],
            registrants=[{"ACCESSION_NUMBER": acc, "CIK": "884394"}],
            fund_info=[{"ACCESSION_NUMBER": acc, "SERIES_NAME": "SPDR S&P 500 ETF Trust"}],
            holdings=[
                {
                    "ACCESSION_NUMBER": acc,
                    "HOLDING_ID": "1",
                    "ISSUER_NAME": "Apple Inc",
                    "ISSUER_CUSIP": "037833100",
                    "CURRENCY_VALUE": "500000",
                    "PERCENTAGE": "5.0",
                    "ASSET_CAT": "EC",
                }
            ],
        )
        with sec_index_connection() as conn:
            conn.execute("DELETE FROM sec_nport_holdings WHERE fund_cik = ?", ("0000884394",))
            conn.commit()
        count = upsert_nport_holdings_rows(rows)
        result = {"ok": True, "rows": count}

    assert result["ok"] is True
    assert result["rows"] >= 1

    holdings = query_nport_holdings("0000884394")
    assert len(holdings) >= 1
    assert holdings[0]["fund_cik"] == "0000884394"
    assert holdings[0]["holding_name"] == "Apple Inc"


def test_nport_zip_ingest_filters_non_target_funds(tmp_path, bulk_root):
    from trade_sentinel_api.db import sec_index_connection

    zip_path = _make_nport_zip(tmp_path, include_other_fund=True)
    with sec_index_connection() as conn:
        conn.execute("DELETE FROM sec_nport_holdings WHERE fund_cik IN (?, ?)", ("0000884394", "0000999999"))
        conn.commit()

    result = ingest_nport_zip(zip_path, quarter_key="2024Q4")
    assert result["ok"] is True
    assert result["rows"] == 1

    spy_holdings = query_nport_holdings("0000884394")
    other_holdings = query_nport_holdings("0000999999")
    assert len(spy_holdings) == 1
    assert spy_holdings[0]["holding_name"] == "Apple Inc"
    assert other_holdings == []

    archive_path = bulk_root / "nport" / "2024Q4" / "holdings.csv"
    assert archive_path.exists()
    archive_text = archive_path.read_text(encoding="utf-8")
    assert "Apple Inc" in archive_text
    assert "Microsoft Corp" not in archive_text
