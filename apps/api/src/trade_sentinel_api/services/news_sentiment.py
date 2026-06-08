"""Deterministic rule-based news sentiment and theme tagging."""

from __future__ import annotations

import re
from collections import Counter

from trade_sentinel_api.models.schemas import NewsDigest, NewsItem, NewsSentiment

_BULLISH = (
    r"\bbeats?\b",
    r"\bbeat\b",
    r"\bupgrade[ds]?\b",
    r"\braises?\s+guidance\b",
    r"\braised\s+outlook\b",
    r"\brecord\s+(revenue|earnings|profit)\b",
    r"\bsurges?\b",
    r"\bjumps?\b",
    r"\brallies\b",
    r"\bsoars?\b",
    r"\bbuy\s+rating\b",
    r"\boutperform\b",
)
_BEARISH = (
    r"\bmiss(es|ed)?\b",
    r"\bdowngrade[ds]?\b",
    r"\bcuts?\s+guidance\b",
    r"\blayoffs?\b",
    r"\blawsuit\b",
    r"\binvestigation\b",
    r"\brecall\b",
    r"\bplunges?\b",
    r"\btumbles?\b",
    r"\bslumps?\b",
    r"\bwarning\b",
    r"\bshort\s+seller\b",
)
_THEMES: list[tuple[str, tuple[str, ...]]] = [
    ("earnings", (r"\bearnings\b", r"\beps\b", r"\bquarterly\s+results\b")),
    ("regulatory", (r"\bsec\b", r"\bftc\b", r"\bdoj\b", r"\bantitrust\b", r"\bprobe\b")),
    ("product", (r"\blaunch\b", r"\bproduct\b", r"\bpartnership\b", r"\bcontract\b")),
    ("macro", (r"\bfed\b", r"\binflation\b", r"\brate\s+cut\b", r"\btariff\b")),
    ("management", (r"\bceo\b", r"\bcfo\b", r"\bexecutive\b", r"\bresign\b")),
]


def _score_text(text: str) -> tuple[float, str]:
    lower = text.lower()
    bull = sum(1 for p in _BULLISH if re.search(p, lower))
    bear = sum(1 for p in _BEARISH if re.search(p, lower))
    if bull > bear:
        return min(1.0, 0.3 + bull * 0.2), "bullish"
    if bear > bull:
        return max(-1.0, -0.3 - bear * 0.2), "bearish"
    return 0.0, "neutral"


def _extract_themes(text: str) -> list[str]:
    lower = text.lower()
    themes: list[str] = []
    for name, patterns in _THEMES:
        if any(re.search(p, lower) for p in patterns):
            themes.append(name)
    return themes


def enrich_news_item(item: NewsItem) -> NewsItem:
    blob = " ".join(p for p in (item.title, item.summary or "") if p)
    score, label = _score_text(blob)
    themes = _extract_themes(blob)
    return item.model_copy(
        update={
            "sentiment_label": label,
            "sentiment_score": round(score, 2),
            "themes": themes,
        }
    )


def build_news_digest(items: list[NewsItem]) -> NewsDigest:
    if not items:
        return NewsDigest(data_available=False, message="No news items available.")

    enriched = [enrich_news_item(i) for i in items]
    bull = sum(1 for i in enriched if i.sentiment_label == "bullish")
    bear = sum(1 for i in enriched if i.sentiment_label == "bearish")
    neutral = sum(1 for i in enriched if i.sentiment_label == "neutral")

    if bull > bear and bull >= 2:
        overall: NewsSentiment = "bullish"
    elif bear > bull and bear >= 2:
        overall = "bearish"
    elif bull > 0 and bear > 0:
        overall = "mixed"
    else:
        overall = "neutral"

    theme_counts = Counter(t for i in enriched for t in i.themes)
    top_themes = [t for t, _ in theme_counts.most_common(4)]

    summary_line = (
        f"News tone is {overall} across {len(enriched)} headlines "
        f"({bull} bullish, {bear} bearish)."
    )
    if top_themes:
        summary_line += f" Top themes: {', '.join(top_themes)}."

    return NewsDigest(
        overall_sentiment=overall,
        summary_line=summary_line,
        top_themes=top_themes,
        bullish_count=bull,
        bearish_count=bear,
        neutral_count=neutral,
        data_available=True,
    )
