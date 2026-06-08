"""Merge, dedupe, and enrich ticker news with summaries and sentiment."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from trade_sentinel_api.models.schemas import NewsDigest, NewsItem
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.market_data import fetch_finnhub_news, fetch_yfinance_news
from trade_sentinel_api.services.news_sentiment import build_news_digest, enrich_news_item

_NEWS_LIMIT = 12
_SUMMARY_FETCH_MAX = 2
_SUMMARY_CAP = 2000
_SUMMARY_CACHE_TTL = 7 * 24 * 3600
_PAYWALL_DOMAINS = frozenset({
    "wsj.com", "ft.com", "bloomberg.com", "nytimes.com", "barrons.com",
})


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.lower().strip())


def _dedupe_key(item: NewsItem) -> str:
    if item.url:
        return item.url.strip().lower()
    return _normalize_title(item.title)


def merge_news_items(*groups: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    merged: list[NewsItem] = []
    for group in groups:
        for item in group:
            key = _dedupe_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= _NEWS_LIMIT:
                return merged
    return merged


def _fetch_article_summary(url: str) -> str | None:
    cached = get_cached("news_summary", url)
    if isinstance(cached, dict) and cached.get("text"):
        return cached["text"]

    domain = urlparse(url).netloc.lower().removeprefix("www.")
    if any(domain.endswith(d) for d in _PAYWALL_DOMAINS):
        return None

    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "TradeSentinel/1.0"})
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            if len(text) < 80:
                return None
            summary = text[:_SUMMARY_CAP].strip()
            set_cached_ttl("news_summary", url, {"text": summary}, _SUMMARY_CACHE_TTL)
            return summary
    except (httpx.HTTPError, UnicodeDecodeError):
        return None


async def _attach_summaries(items: list[NewsItem]) -> list[NewsItem]:
    to_fetch = [i for i in items if not i.summary and i.url][: _SUMMARY_FETCH_MAX]
    if not to_fetch:
        return items

    async def _one(item: NewsItem) -> NewsItem:
        summary = await asyncio.to_thread(_fetch_article_summary, item.url or "")
        if summary:
            return item.model_copy(update={"summary": summary})
        return item

    fetched = await asyncio.gather(*[_one(i) for i in to_fetch])
    by_url = {i.url: i for i in fetched if i.url}
    return [by_url.get(i.url, i) if i.url else i for i in items]


async def fetch_enriched_news(ticker: str, limit: int = _NEWS_LIMIT) -> tuple[list[NewsItem], NewsDigest]:
    finnhub_task = fetch_finnhub_news(ticker, limit)
    yfinance_task = fetch_yfinance_news(ticker, limit)
    finnhub, yfinance = await asyncio.gather(finnhub_task, yfinance_task)

    for item in finnhub:
        if not item.summary and hasattr(item, "model_extra"):
            pass  # Finnhub may include summary in raw API — attach if present in fetch

    merged = merge_news_items(finnhub, yfinance)
    merged = await _attach_summaries(merged)
    enriched = [enrich_news_item(i) for i in merged]
    digest = build_news_digest(enriched)
    return enriched, digest
