import asyncio
import json
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import NewsItem
from trade_sentinel_api.services.market_data import fetch_macro_headlines, fetch_yfinance_news

_FEEDS_PATH = Path(__file__).resolve().parents[3] / "data" / "macro_news_feeds.json"


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())[:120]


def _parse_rss_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    except (TypeError, ValueError, OSError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw[:25], fmt.replace("%z", ""))
            return dt.replace(tzinfo=UTC).isoformat()
        except ValueError:
            continue
    return None


def _text_el(parent, tag: str) -> str | None:
    for local in (tag, f"{{{''}}}{tag}"):
        el = parent.find(local)
        if el is not None and el.text:
            return el.text.strip()
    for child in parent:
        local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if local == tag and child.text:
            return child.text.strip()
    return None


def _parse_rss_xml(content: str, source: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return items

    for item in root.iter():
        local = item.tag.split("}")[-1] if "}" in item.tag else item.tag
        if local not in ("item", "entry"):
            continue
        title = _text_el(item, "title")
        if not title:
            continue
        link = _text_el(item, "link")
        if not link:
            for child in item:
                cl = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if cl == "link" and child.get("href"):
                    link = child.get("href")
                    break
        pub = _text_el(item, "pubDate") or _text_el(item, "published") or _text_el(item, "updated")
        items.append(
            NewsItem(
                title=title,
                url=link,
                published_at=_parse_rss_date(pub),
                source=source,
            )
        )
    return items


def _load_feed_configs() -> list[dict]:
    if not _FEEDS_PATH.is_file():
        return []
    with _FEEDS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("feeds", [])


async def _fetch_rss_feed(feed: dict, per_feed: int) -> tuple[list[NewsItem], str | None]:
    feed_id = feed.get("id", "rss")
    url = feed.get("url")
    source = feed.get("source", feed_id)
    if not url:
        return [], f"{feed_id}_no_url"
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "TradeSentinelAI/1.0"})
            resp.raise_for_status()
            items = _parse_rss_xml(resp.text, source)[:per_feed]
            return items, None
    except (httpx.HTTPError, ValueError):
        return [], f"{feed_id}_fetch_failed"


async def _fetch_newsapi(limit: int) -> tuple[list[NewsItem], str | None]:
    settings = get_settings()
    if not settings.newsapi_key:
        return [], "newsapi_key_missing"
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": '("Federal Reserve" OR CPI OR "jobs report" OR inflation OR "interest rate")',
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(limit, 20),
        "apiKey": settings.newsapi_key,
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return [], "newsapi_fetch_failed"

    articles = data.get("articles") or []
    items: list[NewsItem] = []
    for article in articles[:limit]:
        if not isinstance(article, dict):
            continue
        title = article.get("title")
        if not title or title == "[Removed]":
            continue
        published = article.get("publishedAt")
        items.append(
            NewsItem(
                title=str(title),
                url=article.get("url"),
                published_at=published,
                source=article.get("source", {}).get("name") or "newsapi",
            )
        )
    return items, None


def _dedupe_and_sort(items: list[NewsItem], limit: int) -> list[NewsItem]:
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        key = _normalize_title(item.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    def sort_key(n: NewsItem) -> str:
        return n.published_at or ""

    unique.sort(key=sort_key, reverse=True)
    return unique[:limit]


async def fetch_macro_news(limit: int | None = None) -> tuple[list[NewsItem], dict[str, int], list[str]]:
    """
    Aggregate macro news from Finnhub, yfinance (SPY), RSS, and optional NewsAPI.
    Returns (items, counts_by_source_id, data_gaps).
    """
    settings = get_settings()
    total_limit = limit or settings.macro_news_limit
    per_source = max(3, total_limit // 4)
    gaps: list[str] = []
    source_issues: list[str] = []
    counts: dict[str, int] = {}
    collected: list[NewsItem] = []

    finnhub = await fetch_macro_headlines(per_source)
    if finnhub:
        counts["finnhub"] = len(finnhub)
        collected.extend(finnhub)
    else:
        source_issues.append("finnhub_empty_or_unconfigured")

    yf_spy = await fetch_yfinance_news("SPY", per_source)
    if yf_spy:
        counts["yfinance_spy"] = len(yf_spy)
        collected.extend(yf_spy)
    else:
        yf_gspc = await fetch_yfinance_news("^GSPC", per_source)
        if yf_gspc:
            counts["yfinance_gspc"] = len(yf_gspc)
            collected.extend(yf_gspc)
        else:
            source_issues.append("yfinance_macro_news_empty")

    feed_tasks = [
        _fetch_rss_feed(feed, per_source) for feed in _load_feed_configs()
    ]
    if feed_tasks:
        results = await asyncio.gather(*feed_tasks)
        for feed, (items, err) in zip(_load_feed_configs(), results):
            fid = feed.get("id", "rss")
            if err:
                source_issues.append(err)
            elif items:
                counts[fid] = len(items)
                collected.extend(items)

    newsapi_items, newsapi_err = await _fetch_newsapi(per_source)
    if newsapi_err:
        source_issues.append(newsapi_err)
    elif newsapi_items:
        counts["newsapi"] = len(newsapi_items)
        collected.extend(newsapi_items)

    merged = _dedupe_and_sort(collected, total_limit)
    if not merged:
        gaps.extend(source_issues)
        gaps.append("macro_news_all_sources_empty")
    return merged, counts, gaps
