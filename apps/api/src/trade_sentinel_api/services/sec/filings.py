import asyncio
import logging

import httpx

from trade_sentinel_api.models.schemas import SecFilingHighlight, SecFilingsFeed
from trade_sentinel_api.services.sec.adapter import (
    _filing_date_str,
    _filing_url,
    fetch_company_filings,
)
from trade_sentinel_api.services.sec.edgar import fetch_submissions_json, get_cik_for_ticker
from trade_sentinel_api.services.sec.text import build_filing_enrichment


def _api():
    import trade_sentinel_api.services.sec.filings as filings_api

    return filings_api


logger = logging.getLogger(__name__)

_FILING_FORMS = {
    "8-K",
    "10-Q",
    "10-K",
    "10-K/A",
    "10-Q/A",
    "8-K/A",
    "6-K",
    "6-K/A",
    "20-F",
    "20-F/A",
}
_MAX_FILINGS = 5
_8K_FORMS = {"8-K", "8-K/A"}
_6K_FORMS = {"6-K", "6-K/A"}
_QUARTERLY_FORMS = {"10-Q", "10-Q/A", "10-K", "10-K/A"}
_PERIODIC_FORMS = _QUARTERLY_FORMS | {"20-F", "20-F/A"}
_CURRENT_REPORT_FORMS = _8K_FORMS | _6K_FORMS
_EMPTY_FILINGS_MSG = "No recent SEC filings (8-K, 10-Q, 10-K, 6-K, 20-F) found."


async def fetch_sec_filings(ticker: str) -> SecFilingsFeed:
    symbol = ticker.upper().strip()
    feed, cik, excerpt_targets = await asyncio.to_thread(_build_feed_sync, symbol)
    if not feed.data_available or not cik:
        return feed
    return await _attach_excerpts_async(cik, feed, excerpt_targets)


def _normalize_form(form: str) -> str:
    if form in _CURRENT_REPORT_FORMS or form.startswith("8-K") or form.startswith("6-K"):
        if form.startswith("6-K") or form in _6K_FORMS:
            return "6-K"
        return "8-K"
    if form in _PERIODIC_FORMS or form.startswith("10-Q"):
        if form.startswith("20-F") or form in {"20-F", "20-F/A"}:
            return "20-F"
        if form.startswith("10-K") or form in ("10-K", "10-K/A"):
            return "10-K"
        return "10-Q"
    return form


def _is_current_report(form: str) -> bool:
    return _normalize_form(form) in ("8-K", "6-K")


def _filing_obj_to_highlight(filing: object) -> SecFilingHighlight | None:
    form = getattr(filing, "form", None)
    if not form or form not in _FILING_FORMS:
        return None
    acc = getattr(filing, "accession_no", None) or getattr(filing, "accession_number", None)
    title = (
        getattr(filing, "description", None)
        or getattr(filing, "primary_doc_description", None)
        or form
    )
    return SecFilingHighlight(
        form=str(form),
        filing_date=_api()._filing_date_str(filing),
        title=str(title) if title else str(form),
        url=_api()._filing_url(filing),
        accession=str(acc) if acc else None,
    )


def _highlights_from_submissions(cik: str, data: dict) -> list[SecFilingHighlight]:
    recent = data.get("filings", {}).get("recent", {})
    cik_int = int(cik)
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", []) or recent.get("description", [])

    highlights: list[SecFilingHighlight] = []
    for i, form in enumerate(forms):
        if form not in _FILING_FORMS:
            continue
        filing_date = filing_dates[i] if i < len(filing_dates) else "unknown"
        acc = accession[i] if i < len(accession) else None
        doc = primary_docs[i] if i < len(primary_docs) else None
        title = descriptions[i] if i < len(descriptions) else form
        doc_url = None
        if acc and doc:
            acc_path = acc.replace("-", "")
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_path}/{doc}"
        highlights.append(
            SecFilingHighlight(
                form=form,
                filing_date=filing_date,
                title=str(title) if title else form,
                url=doc_url,
                accession=acc,
            )
        )
    return highlights


def _assemble_feed(
    ticker: str,
    highlights: list[SecFilingHighlight],
) -> tuple[SecFilingsFeed, list[SecFilingHighlight]]:
    filings: list[SecFilingHighlight] = []
    latest_periodic: SecFilingHighlight | None = None

    for highlight in highlights:
        nf = _normalize_form(highlight.form)
        if latest_periodic is None and nf in ("10-Q", "10-K", "20-F"):
            latest_periodic = highlight
        if len(filings) < _MAX_FILINGS:
            filings.append(highlight)

    if not filings:
        return (
            SecFilingsFeed(
                ticker=ticker,
                data_available=False,
                message=_EMPTY_FILINGS_MSG,
            ),
            [],
        )

    if latest_periodic and not _filing_in_list(latest_periodic, filings):
        filings = [latest_periodic, *filings]
        if len(filings) > _MAX_FILINGS:
            filings = filings[:_MAX_FILINGS]

    feed = SecFilingsFeed(ticker=ticker, filings=filings, data_available=True)
    excerpt_targets: list[SecFilingHighlight] = []
    seen_keys: set[tuple[str, str, str | None]] = set()

    def _add_target(h: SecFilingHighlight) -> None:
        key = (h.form, h.filing_date, h.url)
        if key in seen_keys or not h.url or not h.accession:
            return
        seen_keys.add(key)
        excerpt_targets.append(h)

    if latest_periodic:
        _add_target(latest_periodic)

    for f in filings:
        if _is_current_report(f.form):
            _add_target(f)
        if len(excerpt_targets) >= _MAX_FILINGS:
            break

    return feed, excerpt_targets[:_MAX_FILINGS]


def _build_feed_sync(ticker: str) -> tuple[SecFilingsFeed, str | None, list[SecFilingHighlight]]:
    cik = _api().get_cik_for_ticker(ticker)
    if not cik:
        return (
            SecFilingsFeed(
                ticker=ticker,
                data_available=False,
                message=f"No SEC CIK found for ticker {ticker}.",
            ),
            None,
            [],
        )

    highlights: list[SecFilingHighlight] = []
    try:
        raw_filings = _api().fetch_company_filings(ticker, list(_FILING_FORMS), limit=50)
        for filing in raw_filings:
            highlight = _filing_obj_to_highlight(filing)
            if highlight:
                highlights.append(highlight)
    except Exception as exc:
        logger.debug("EdgarTools company filings failed for %s: %s", ticker, exc)

    if not highlights:
        try:
            data = _api().fetch_submissions_json(cik)
            if data is None:
                return (
                    SecFilingsFeed(
                        ticker=ticker,
                        data_available=False,
                        message="SEC submissions API returned HTTP error or is unavailable.",
                    ),
                    cik,
                    [],
                )
            highlights = _highlights_from_submissions(cik, data)
        except (httpx.HTTPError, ValueError):
            return (
                SecFilingsFeed(
                    ticker=ticker,
                    data_available=False,
                    message="SEC submissions API request failed.",
                ),
                cik,
                [],
            )

    feed, excerpt_targets = _assemble_feed(ticker, highlights)
    return feed, cik, excerpt_targets


def _filing_in_list(candidate: SecFilingHighlight, filings: list[SecFilingHighlight]) -> bool:
    for f in filings:
        if candidate.accession and f.accession and candidate.accession == f.accession:
            return True
        if candidate.url and f.url and candidate.url == f.url:
            return True
    return False


async def _attach_excerpts_async(
    cik: str,
    feed: SecFilingsFeed,
    targets: list[SecFilingHighlight],
) -> SecFilingsFeed:
    if not targets:
        return feed

    async def _fetch_one(
        h: SecFilingHighlight,
    ) -> tuple[tuple[str, str, str | None], dict | None]:
        enrichment = await asyncio.to_thread(
            _api().build_filing_enrichment,
            h.url,
            h.form,
            cik=cik,
            accession=h.accession or "",
        )
        return (h.form, h.filing_date, h.url), enrichment

    results = await asyncio.gather(*[_fetch_one(h) for h in targets])
    by_key = {key: enrichment for key, enrichment in results if enrichment}

    new_filings = []
    for f in feed.filings:
        key = (f.form, f.filing_date, f.url)
        enrichment = by_key.get(key)
        if enrichment and enrichment.get("excerpt"):
            update: dict = {
                "excerpt": enrichment["excerpt"],
                "excerpt_available": True,
                "excerpt_chars": len(enrichment["excerpt"]),
            }
            event_items = enrichment.get("event_items")
            if event_items:
                update["event_items"] = event_items
            new_filings.append(f.model_copy(update=update))
        else:
            new_filings.append(f)

    return feed.model_copy(update={"filings": new_filings})
