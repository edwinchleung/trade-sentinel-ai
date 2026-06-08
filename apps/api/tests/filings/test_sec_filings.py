"""SEC filings feed tests."""

from unittest.mock import patch

import pytest

from trade_sentinel_api.services.sec.filings import (
    _attach_excerpts_async,
    _build_feed_sync,
    fetch_sec_filings,
)

_SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["8-K", "4", "10-Q", "S-8", "10-K"],
            "filingDate": ["2025-01-15", "2025-01-10", "2024-11-01", "2024-10-01", "2024-09-30"],
            "accessionNumber": ["0001", "0002", "0003", "0004", "0005"],
            "primaryDocument": ["d8k.htm", "form4.xml", "10q.htm", "s8.htm", "10k.htm"],
            "primaryDocDescription": ["Current report", "Form 4", "Quarterly", "S-8", "Annual"],
        }
    }
}


_SUBMISSIONS_MULTI_8K = {
    "filings": {
        "recent": {
            "form": ["8-K", "8-K", "8-K", "10-Q", "4"],
            "filingDate": [
                "2026-05-01",
                "2026-04-01",
                "2026-03-01",
                "2025-11-01",
                "2025-10-01",
            ],
            "accessionNumber": ["a1", "a2", "a3", "a4", "a5"],
            "primaryDocument": ["k1.htm", "k2.htm", "k3.htm", "10q.htm", "f4.xml"],
            "primaryDocDescription": ["8K1", "8K2", "8K3", "Q", "F4"],
        }
    }
}


_SUBMISSIONS_FIVE_8K_BEFORE_10Q = {
    "filings": {
        "recent": {
            "form": ["8-K", "8-K", "8-K", "8-K", "8-K", "10-Q"],
            "filingDate": [
                "2026-05-01",
                "2026-04-01",
                "2026-03-01",
                "2026-02-01",
                "2026-01-01",
                "2025-11-01",
            ],
            "accessionNumber": ["k1", "k2", "k3", "k4", "k5", "q1"],
            "primaryDocument": ["k1.htm", "k2.htm", "k3.htm", "k4.htm", "k5.htm", "10q.htm"],
            "primaryDocDescription": ["8K"] * 5 + ["Quarterly"],
        }
    }
}


_SUBMISSIONS_TSM_FOREIGN = {
    "filings": {
        "recent": {
            "form": ["6-K", "6-K", "6-K", "6-K", "6-K", "20-F"],
            "filingDate": [
                "2026-05-01",
                "2026-04-01",
                "2026-03-01",
                "2026-02-01",
                "2026-01-01",
                "2025-04-15",
            ],
            "accessionNumber": ["s1", "s2", "s3", "s4", "s5", "f1"],
            "primaryDocument": ["6k1.htm", "6k2.htm", "6k3.htm", "6k4.htm", "6k5.htm", "20f.htm"],
            "primaryDocDescription": ["6K"] * 5 + ["Annual"],
        }
    }
}


@patch("trade_sentinel_api.services.sec.filings.get_cik_for_ticker", return_value=None)
def test_sec_filings_no_cik(mock_cik):
    feed, cik, targets = _build_feed_sync("INVALID")
    assert feed.data_available is False
    assert cik is None
    assert targets == []


@patch(
    "trade_sentinel_api.services.sec.filings.fetch_company_filings",
    side_effect=RuntimeError("use submissions fallback"),
)
@patch("trade_sentinel_api.services.sec.filings.fetch_submissions_json", return_value=_SUBMISSIONS)
@patch("trade_sentinel_api.services.sec.filings.get_cik_for_ticker", return_value="0000320193")
def test_sec_filings_filters_forms(_mock_cik, _mock_submissions, _mock_edgar):
    feed, cik, targets = _build_feed_sync("AAPL")
    assert feed.data_available is True
    forms = [f.form for f in feed.filings]
    assert "4" not in forms
    assert "8-K" in forms
    assert len(feed.filings) <= 5
    assert len(targets) == 2
    assert targets[0].form.startswith("10")
    assert any(_normalize(t) == "8-K" for t in targets)


@patch(
    "trade_sentinel_api.services.sec.filings.fetch_company_filings",
    side_effect=RuntimeError("use submissions fallback"),
)
@patch(
    "trade_sentinel_api.services.sec.filings.fetch_submissions_json",
    return_value=_SUBMISSIONS_MULTI_8K,
)
@patch("trade_sentinel_api.services.sec.filings.get_cik_for_ticker", return_value="0000320193")
def test_sec_filings_multiple_8k_excerpt_targets(_mock_cik, _mock_submissions, _mock_edgar):
    feed, _cik, targets = _build_feed_sync("NVDA")
    assert targets[0].form == "10-Q"
    eight_k_targets = [t for t in targets if _normalize(t) == "8-K"]
    assert len(eight_k_targets) == 3
    assert len(targets) >= 4


@patch(
    "trade_sentinel_api.services.sec.filings.fetch_company_filings",
    side_effect=RuntimeError("use submissions fallback"),
)
@patch(
    "trade_sentinel_api.services.sec.filings.fetch_submissions_json",
    return_value=_SUBMISSIONS_FIVE_8K_BEFORE_10Q,
)
@patch("trade_sentinel_api.services.sec.filings.get_cik_for_ticker", return_value="0001045810")
def test_sec_filings_injects_quarterly_when_first_five_are_8k(_mock_cik, _mock_submissions, _mock_edgar):
    feed, _cik, targets = _build_feed_sync("NVDA")
    forms = [f.form for f in feed.filings]
    assert "10-Q" in forms
    assert targets[0].form == "10-Q"
    assert len([t for t in targets if _normalize(t) == "8-K"]) <= 4


@patch(
    "trade_sentinel_api.services.sec.filings.fetch_company_filings",
    side_effect=RuntimeError("use submissions fallback"),
)
@patch(
    "trade_sentinel_api.services.sec.filings.fetch_submissions_json",
    return_value=_SUBMISSIONS_TSM_FOREIGN,
)
@patch("trade_sentinel_api.services.sec.filings.get_cik_for_ticker", return_value="0001046179")
def test_sec_filings_tsm_foreign_issuer(_mock_cik, _mock_submissions, _mock_edgar):
    feed, _cik, targets = _build_feed_sync("TSM")
    assert feed.data_available is True
    forms = [f.form for f in feed.filings]
    assert "6-K" in forms
    assert "20-F" in forms
    assert targets[0].form == "20-F"
    six_k_targets = [t for t in targets if _normalize(t) == "6-K"]
    assert len(six_k_targets) <= 4
    assert len(targets) <= 5


def _normalize(h):
    from trade_sentinel_api.services.sec.filings import _normalize_form

    return _normalize_form(h.form)


@pytest.mark.asyncio
@patch(
    "trade_sentinel_api.services.sec.filings.build_filing_enrichment",
    return_value={"excerpt": "Item 2.02 Earnings beat expectations with revenue of $10B.", "event_items": ["2.02"]},
)
@patch(
    "trade_sentinel_api.services.sec.filings.fetch_company_filings",
    side_effect=RuntimeError("use submissions fallback"),
)
@patch("trade_sentinel_api.services.sec.filings.fetch_submissions_json", return_value=_SUBMISSIONS)
@patch("trade_sentinel_api.services.sec.filings.get_cik_for_ticker", return_value="0000320193")
async def test_fetch_sec_filings_attaches_excerpts(_mock_cik, _mock_submissions, _mock_edgar, mock_enrichment):
    feed = await fetch_sec_filings("AAPL")
    with_excerpt = [f for f in feed.filings if f.excerpt_available]
    assert len(with_excerpt) >= 1
    assert mock_enrichment.call_count == 2
    assert with_excerpt[0].event_items == ["2.02"]


@pytest.mark.asyncio
async def test_attach_excerpts_async():
    from trade_sentinel_api.models.schemas import SecFilingHighlight, SecFilingsFeed

    eight_k = SecFilingHighlight(
        form="8-K",
        filing_date="2025-01-15",
        title="Current",
        url="http://sec/8k",
        accession="0001",
    )
    feed = SecFilingsFeed(ticker="X", filings=[eight_k], data_available=True)

    with patch(
        "trade_sentinel_api.services.sec.filings.build_filing_enrichment",
        return_value={
            "excerpt": "Material event disclosed in filing body text here " * 3,
            "event_items": ["2.02"],
        },
    ):
        result = await _attach_excerpts_async("0001", feed, [eight_k])

    assert result.filings[0].excerpt_available is True
    assert result.filings[0].excerpt is not None
    assert result.filings[0].event_items == ["2.02"]
