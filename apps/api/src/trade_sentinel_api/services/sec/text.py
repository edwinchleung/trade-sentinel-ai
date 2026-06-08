"""Fetch SEC filing HTML and produce bounded plain-text excerpts."""

import re
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.sec.http import sec_get

_EXCERPT_CACHE_TTL = 7 * 24 * 3600
_MIN_EXCERPT_CHARS = 80
_MIN_EXCERPT_CHARS_8K = 40
_MIN_EXCERPT_CHARS_QUARTERLY = 40
_CAP_8K = 4000
_CAP_QUARTERLY = 3000
_excerpt_memory: dict[str, tuple[float, str]] = {}

_8K_ANCHORS = (
    r"item\s+2\.02",
    r"results\s+of\s+operations",
)
_QUARTERLY_ANCHORS = (
    r"management['\u2019]?s\s+discussion\s+and\s+analysis",
    r"management['\u2019]?s\s+discussion",
    r"item\s+2\.\s*management",
)
_SKIP_LINE = re.compile(
    r"^(table\s+of\s+contents|united\s+states\s+securities|sec\s+urities)",
    re.I,
)
_CURRENT_EVENT_FORMS = {"8-K", "8-K/A", "6-K", "6-K/A"}


def _normalize_form(form: str) -> str:
    base = form.upper().split("/")[0]
    if base.startswith("6-K"):
        return "8-K"
    if base.startswith("8-K"):
        return "8-K"
    if base.startswith("20-F"):
        return "10-K"
    if base.startswith("10-Q"):
        return "10-Q"
    if base.startswith("10-K"):
        return "10-K"
    return base


def _is_current_event_form(form: str) -> bool:
    return form.upper() in _CURRENT_EVENT_FORMS or form.upper().startswith(("8-K", "6-K"))


def fetch_filing_text(url: str) -> str | None:
    try:
        resp = sec_get(url, timeout=30.0, follow_redirects=True)
        if resp.status_code != 200:
            return None
        return resp.text
    except (httpx.HTTPError, UnicodeDecodeError):
        return None


def html_to_plain_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or _SKIP_LINE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _find_anchor(text: str, patterns: tuple[str, ...]) -> int | None:
    lower = text.lower()
    best = None
    for pat in patterns:
        m = re.search(pat, lower, re.I)
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


def extract_excerpt(text: str, form: str) -> str:
    normalized = _normalize_form(form)
    if normalized == "8-K":
        start = _find_anchor(text, _8K_ANCHORS)
        window = text[start:] if start is not None else text
        excerpt = window[:_CAP_8K].strip()
        if len(excerpt) < _MIN_EXCERPT_CHARS_8K:
            excerpt = text[:_CAP_8K].strip()
        return excerpt
    if normalized in ("10-Q", "10-K"):
        start = _find_anchor(text, _QUARTERLY_ANCHORS)
        window = text[start:] if start is not None else text
        excerpt = window[:_CAP_QUARTERLY].strip()
        if len(excerpt) < _MIN_EXCERPT_CHARS_QUARTERLY:
            excerpt = text[:_CAP_QUARTERLY].strip()
        return excerpt
    return text[:_CAP_QUARTERLY].strip()


def _build_edgartools_enrichment(url: str, form: str) -> dict[str, Any] | None:
    if not _is_current_event_form(form):
        return None
    try:
        from trade_sentinel_api.services.sec.adapter import (
            eightk_to_highlight,
            filing_from_url,
            parse_filing,
        )

        filing = filing_from_url(url)
        if filing is None:
            return None
        obj, _ = parse_filing(filing)
        if obj is None:
            return None
        highlight = eightk_to_highlight(filing, obj, form=form)
        if not highlight.excerpt:
            return None
        return {
            "excerpt": highlight.excerpt,
            "event_items": highlight.event_items,
        }
    except Exception:
        return None


def build_filing_enrichment(
    url: str,
    form: str,
    *,
    cik: str,
    accession: str,
) -> dict[str, Any] | None:
    """Return excerpt + optional event_items for 8-K/6-K/periodic filings."""
    cache_key = f"{cik}:{accession.replace('-', '')}"
    now = time.time()
    if cache_key in _excerpt_memory:
        expires, val = _excerpt_memory[cache_key]
        if expires > now:
            return {"excerpt": val} if val else None
        del _excerpt_memory[cache_key]

    cached = get_cached("filing_excerpt", cache_key)
    if isinstance(cached, dict) and cached.get("excerpt"):
        _excerpt_memory[cache_key] = (now + _EXCERPT_CACHE_TTL, cached["excerpt"])
        return cached
    if cached == "":
        _excerpt_memory[cache_key] = (now + _EXCERPT_CACHE_TTL, "")
        return None

    edgar_enrichment = _build_edgartools_enrichment(url, form)
    if edgar_enrichment and len(edgar_enrichment.get("excerpt") or "") >= _MIN_EXCERPT_CHARS_8K:
        set_cached_ttl("filing_excerpt", cache_key, edgar_enrichment, _EXCERPT_CACHE_TTL)
        _excerpt_memory[cache_key] = (now + _EXCERPT_CACHE_TTL, edgar_enrichment["excerpt"])
        return edgar_enrichment

    html = fetch_filing_text(url)
    if not html:
        set_cached_ttl("filing_excerpt", cache_key, "", _EXCERPT_CACHE_TTL)
        _excerpt_memory[cache_key] = (now + _EXCERPT_CACHE_TTL, "")
        return None

    plain = html_to_plain_text(html)
    if len(plain) < _MIN_EXCERPT_CHARS:
        set_cached_ttl("filing_excerpt", cache_key, "", _EXCERPT_CACHE_TTL)
        _excerpt_memory[cache_key] = (now + _EXCERPT_CACHE_TTL, "")
        return None

    excerpt = extract_excerpt(plain, form)
    norm = _normalize_form(form)
    if norm == "8-K":
        min_len = _MIN_EXCERPT_CHARS_8K
    elif norm in ("10-Q", "10-K"):
        min_len = _MIN_EXCERPT_CHARS_QUARTERLY
    else:
        min_len = _MIN_EXCERPT_CHARS
    if len(excerpt) < min_len:
        set_cached_ttl("filing_excerpt", cache_key, "", _EXCERPT_CACHE_TTL)
        _excerpt_memory[cache_key] = (now + _EXCERPT_CACHE_TTL, "")
        return None

    payload = {"excerpt": excerpt, "event_items": None}
    set_cached_ttl("filing_excerpt", cache_key, payload, _EXCERPT_CACHE_TTL)
    _excerpt_memory[cache_key] = (now + _EXCERPT_CACHE_TTL, excerpt)
    return payload


def build_filing_excerpt(url: str, form: str, *, cik: str, accession: str) -> str | None:
    enrichment = build_filing_enrichment(url, form, cik=cik, accession=accession)
    if enrichment is None:
        return None
    return enrichment.get("excerpt")
