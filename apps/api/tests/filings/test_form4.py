"""Merged from: test_form4_parser.py, test_edgar_insider.py, test_insider_classification.py, test_insider_filings.py, test_filing_resolver.py, test_filing_text.py"""

# Legacy XML parser tests removed — see tests/filings/test_edgartools_adapter.py

# --- from test_edgar_insider.py ---

from datetime import date, timedelta

from trade_sentinel_api.models.schemas import InsiderTransaction
from trade_sentinel_api.services.sec.edgar import _classify_insider_side, summarize_insider_activity


def test_classify_grant_ad_code_excluded():
    tx = InsiderTransaction(
        filing_date=date.today().isoformat(),
        insider_name="CFO",
        transaction_type="Grant",
        acquired_disposed="A",
        transaction_code="A",
        is_open_market=False,
    )
    assert _classify_insider_side(tx) == "excluded"


def test_classify_open_market_purchase():
    tx = InsiderTransaction(
        filing_date=date.today().isoformat(),
        insider_name="CEO",
        transaction_type="Purchase",
        transaction_code="P",
        is_open_market=True,
    )
    assert _classify_insider_side(tx) == "buy"


def test_summarize_open_market_purchase():
    recent = date.today().isoformat()
    txs = [
        InsiderTransaction(
            filing_date=recent,
            insider_name="CEO",
            transaction_type="Purchase",
            shares=10_000,
            price=50.0,
            transaction_code="P",
            is_open_market=True,
        ),
    ]
    summary = summarize_insider_activity(txs)
    assert summary.data_available is True
    assert summary.buy_count == 1
    assert summary.open_market_buy_count == 1


def test_summarize_metadata_only_still_available():
    recent = (date.today() - timedelta(days=7)).isoformat()
    txs = [
        InsiderTransaction(
            filing_date=recent,
            insider_name="Insider",
            transaction_type="Form 4 filing",
        ),
    ]
    summary = summarize_insider_activity(txs)
    assert summary.data_available is True
    assert summary.buy_count == 0
    assert summary.sell_count == 0

# --- from test_insider_classification.py ---


from trade_sentinel_api.services.sec.insider_classification import (
    classify_transaction_code,
    detect_cluster_buying,
    is_open_market_transaction,
)


def test_classify_open_market_purchase():
    assert classify_transaction_code("P") == "buy"
    assert is_open_market_transaction("P") is True


def test_classify_grant_excluded():
    assert classify_transaction_code("A") == "excluded"
    assert classify_transaction_code("M") == "excluded"
    assert is_open_market_transaction("A") is False


def test_summarize_excludes_grants_from_sentiment():
    today = date.today().isoformat()
    txs = [
        InsiderTransaction(
            filing_date=today,
            insider_name="CEO",
            transaction_type="Grant",
            shares=100000,
            transaction_code="A",
            is_open_market=False,
        ),
        InsiderTransaction(
            filing_date=today,
            insider_name="CFO",
            transaction_type="Purchase",
            shares=5000,
            price=50.0,
            transaction_code="P",
            is_open_market=True,
        ),
    ]
    summary = summarize_insider_activity(txs)
    assert summary.buy_count == 1
    assert summary.excluded_count == 1
    assert summary.open_market_buy_count == 1


def test_cluster_buying_detection():
    today = date.today()
    txs = [
        InsiderTransaction(
            filing_date=today.isoformat(),
            insider_name="CEO",
            transaction_type="Purchase",
            shares=1000,
            transaction_code="P",
            is_open_market=True,
        ),
        InsiderTransaction(
            filing_date=(today - timedelta(days=2)).isoformat(),
            insider_name="CFO",
            transaction_type="Purchase",
            shares=2000,
            transaction_code="P",
            is_open_market=True,
        ),
    ]
    assert detect_cluster_buying(txs) is True

# --- from test_insider_filings.py ---

"""Form 4 excerpt formatting."""

from unittest.mock import patch

import pytest

from trade_sentinel_api.services.sec.insider_filings import build_form4_excerpt


def test_build_form4_excerpt_purchase():
    tx = InsiderTransaction(
        filing_date="2025-01-10",
        insider_name="Jane Doe",
        transaction_type="Purchase",
        shares=50_000,
        price=142.30,
        filing_url="https://example.com/form4",
    )
    text = build_form4_excerpt(tx)
    assert "2025-01-10" in text
    assert "Jane Doe" in text
    assert "Purchase" in text
    assert "50,000" in text
    assert "$142.30" in text
    assert "$7.1M" in text


def test_build_form4_excerpt_minimal():
    tx = InsiderTransaction(
        filing_date="2024-06-01",
        insider_name="CEO",
        transaction_type="Sale",
    )
    text = build_form4_excerpt(tx, {"shares": 1000, "price": 10.0})
    assert "CEO" in text
    assert "Sale" in text


def test_build_form4_excerpt_unavailable_suffix():
    tx = InsiderTransaction(
        filing_date="2024-06-01",
        insider_name="CEO",
        transaction_type="Form 4 filing",
    )
    text = build_form4_excerpt(tx)
    assert "transaction details unavailable from filing" in text


def test_build_facts_includes_insider_filings_when_requested():
    from trade_sentinel_api.models.schemas import InsiderFilingHighlight
    from trade_sentinel_api.services.context import _build_facts

    highlight = InsiderFilingHighlight(
        filing_date="2025-01-01",
        insider_name="CFO",
        transaction_type="Purchase",
        excerpt="2025-01-01 — CFO — Purchase",
        excerpt_available=True,
    )
    facts = _build_facts(
        "NVDA",
        {
            "price": 100.0,
            "change_pct": 1.0,
            "volume": 1,
            "volume_avg_30d": 1,
            "volume_ratio": 1,
            "macd": None,
        },
        [],
        None,
        None,
        None,
        None,
        None,
        [highlight],
        None,
        None,
        include_insider=True,
    )
    assert "insider_filings" in facts
    assert len(facts["insider_filings"]) == 1


@pytest.mark.asyncio
@patch(
    "trade_sentinel_api.services.sec.insider_filings._fetch_form4_parsed",
    return_value={
        "insider_name": "CFO",
        "transaction_type": "Purchase",
        "shares": 25000.0,
        "price": 99.5,
        "filing_date": "2025-02-01",
        "acquired_disposed": "A",
    },
)
async def test_enrich_insider_filings_form4_filing_type(_mock_parse):
    from trade_sentinel_api.models.schemas import InsiderSummary
    from trade_sentinel_api.services.sec.insider_filings import enrich_insider_filings

    txs = [
        InsiderTransaction(
            filing_date="2025-02-01",
            insider_name="CFO",
            transaction_type="Form 4 filing",
            shares=10_000,
            price=100.0,
            filing_url="https://www.sec.gov/form4-1",
        ),
        InsiderTransaction(
            filing_date="2025-01-15",
            insider_name="CEO",
            transaction_type="Form 4 filing",
            filing_url="https://www.sec.gov/form4-2",
        ),
    ]
    summary = InsiderSummary(data_available=False)
    _, highlights = await enrich_insider_filings(summary, txs)
    assert len(highlights) >= 1
    assert highlights[0].excerpt_available
    assert "25,000" in highlights[0].excerpt
    assert "Buy" in highlights[0].excerpt or "Purchase" in highlights[0].excerpt


@patch("trade_sentinel_api.services.sec.insider_filings.get_cached", return_value=None)
@patch(
    "trade_sentinel_api.services.sec.insider_filings.parse_form4_from_filing_url",
    return_value={
        "insider_name": "CFO",
        "transaction_type": "Purchase",
        "shares": 1000.0,
        "price": 50.0,
    },
)
def test_fetch_form4_parsed_uses_adapter(_mock_parse, _mock_cache):
    from trade_sentinel_api.services.sec.insider_filings import _fetch_form4_parsed

    index_url = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240102-index.htm"
    parsed = _fetch_form4_parsed(index_url)
    assert parsed is not None
    _mock_parse.assert_called_once()
    assert _mock_parse.call_args[0][0] == index_url


def test_build_facts_includes_smart_money_fields():
    from datetime import UTC, datetime

    from trade_sentinel_api.models.schemas import (
        ActivistFeedItem,
        Institutional13FChange,
        Institutional13FChanges,
        SmartMoneyAssessment,
        SmartMoneyLayerScore,
        VolumeFootprint,
    )
    from trade_sentinel_api.services.context import _build_facts

    institutional = Institutional13FChanges(
        ticker="AAPL",
        as_of=datetime.now(UTC),
        changes=[
            Institutional13FChange(
                filer_name="Vanguard",
                filer_cik="0000102909",
                ticker="AAPL",
                change_type="increased",
                pct_change=12.0,
            )
        ],
        conviction_buy=True,
        data_available=True,
    )
    activist = ActivistFeedItem(
        filing_date="2025-01-15",
        form_type="13D",
        filer_name="Activist Fund",
        percent_owned=8.5,
        is_activist=True,
    )
    assessment = SmartMoneyAssessment(
        ticker="AAPL",
        conviction_pct=72.0,
        headline="High smart-money conviction",
        layers=[
            SmartMoneyLayerScore(
                layer="institutional_13f",
                label="Institutional 13F",
                score=15,
                max_score=15,
                stance="conviction",
            )
        ],
        data_available=True,
    )
    footprint = VolumeFootprint(stance="accumulation", data_available=True, analysis_bullets=["OBV bullish"])

    facts = _build_facts(
        "AAPL",
        {
            "price": 100.0,
            "change_pct": 1.0,
            "volume": 1,
            "volume_avg_30d": 1,
            "volume_ratio": 1,
            "macd": None,
        },
        [],
        None,
        None,
        None,
        None,
        None,
        [],
        None,
        None,
        institutional_13f=institutional,
        activist_filing=activist,
        smart_money_assessment=assessment,
        volume_footprint=footprint,
    )
    assert facts["institutional_13f"]["conviction_buy"] is True
    assert len(facts["institutional_13f"]["changes"]) == 1
    assert facts["activist_filing"]["filer_name"] == "Activist Fund"
    assert facts["smart_money_assessment"]["conviction_pct"] == 72.0
    assert facts["volume_footprint"]["stance"] == "accumulation"


def test_build_metadata_highlights():
    from trade_sentinel_api.services.sec.insider_filings import build_metadata_highlights

    txs = [
        InsiderTransaction(
            filing_date="2025-01-01",
            insider_name="Insider",
            transaction_type="Form 4 filing",
        )
    ]
    h = build_metadata_highlights(txs)
    assert len(h) == 1
    assert "Form 4 filing" in h[0].excerpt

# --- from test_filing_text.py ---

"""Tests for SEC filing HTML excerpt extraction."""

from unittest.mock import patch

from trade_sentinel_api.services.sec.text import (
    _CAP_8K,
    _CAP_QUARTERLY,
    _MIN_EXCERPT_CHARS,
    extract_excerpt,
    html_to_plain_text,
)


def test_html_to_plain_text_strips_scripts():
    html = "<html><script>bad()</script><body><p>Revenue up 10%</p></body></html>"
    text = html_to_plain_text(html)
    assert "bad()" not in text
    assert "Revenue up 10%" in text


def test_extract_excerpt_8k_item_202():
    body = "Intro " * 20 + "Item 2.02 Results of Operations and Financial Condition. EPS was $1.25."
    excerpt = extract_excerpt(body, "8-K")
    assert "Item 2.02" in excerpt or "Results of Operations" in excerpt
    assert len(excerpt) <= _CAP_8K


def test_extract_excerpt_10q_mda():
    body = (
        "Table of Contents\n"
        "UNITED STATES SECURITIES\n"
        "Management's Discussion and Analysis of Financial Condition. Revenue grew 15%."
    )
    excerpt = extract_excerpt(body, "10-Q")
    assert "Management" in excerpt
    assert len(excerpt) <= _CAP_QUARTERLY


def test_extract_excerpt_truncates_long_8k():
    body = "Item 2.02 Results. " + ("x" * 5000)
    excerpt = extract_excerpt(body, "8-K")
    assert len(excerpt) == _CAP_8K


def test_extract_excerpt_8k_fallback_without_anchor():
    body = "Company announced a new product partnership with a major cloud provider today."
    excerpt = extract_excerpt(body, "8-K")
    assert len(excerpt) >= 40
    assert "partnership" in excerpt


def test_extract_excerpt_6k_uses_8k_heuristics():
    body = "Item 2.02 Results of Operations. Revenue increased 12% year over year."
    excerpt_6k = extract_excerpt(body, "6-K")
    excerpt_8k = extract_excerpt(body, "8-K")
    assert excerpt_6k == excerpt_8k
    assert len(excerpt_6k) >= 40


@patch("trade_sentinel_api.services.sec.text.fetch_filing_text", return_value=None)
def test_build_filing_excerpt_fetch_fail(mock_fetch):
    from trade_sentinel_api.services.sec.text import build_filing_excerpt

    assert build_filing_excerpt("http://x", "8-K", cik="0001", accession="acc") is None


@patch("trade_sentinel_api.services.sec.text.set_cached_ttl")
@patch("trade_sentinel_api.services.sec.text.get_cached", return_value=None)
@patch("trade_sentinel_api.services.sec.text._build_edgartools_enrichment", return_value=None)
@patch(
    "trade_sentinel_api.services.sec.text.fetch_filing_text",
    return_value="<html><body><p>" + ("word " * 50) + "</p></body></html>",
)
def test_build_filing_excerpt_success(mock_fetch, _mock_edgar, mock_get, mock_set):
    from trade_sentinel_api.services.sec.text import build_filing_excerpt

    result = build_filing_excerpt("http://x", "8-K", cik="0001", accession="acc-1")
    assert result is not None
    assert len(result) >= _MIN_EXCERPT_CHARS
    mock_set.assert_called_once()
