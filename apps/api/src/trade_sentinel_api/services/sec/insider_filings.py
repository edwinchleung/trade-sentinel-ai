"""Form 4 filing excerpts for LLM and UI (structured, not full XML RAG)."""

import asyncio

from trade_sentinel_api.models.schemas import (
    InsiderFilingHighlight,
    InsiderSummary,
    InsiderTransaction,
    NotableInsiderTransaction,
)
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.sec.adapter import parse_form4_from_filing_url

_EXCERPT_CACHE_TTL = 7 * 24 * 3600
_EXCERPT_FAILURE_CACHE_TTL = 3600
_MAX_EXCERPTS = 5


def _side_label(tx_type: str, parsed: dict | None, tx: InsiderTransaction | None = None) -> str | None:
    if tx and tx.is_open_market:
        code = (tx.transaction_code or "").upper()[:1]
        if code == "P":
            return "Buy"
        if code == "S":
            return "Sell"
    if parsed:
        code = (parsed.get("transaction_code") or "").upper()[:1]
        if code == "P":
            return "Buy"
        if code == "S":
            return "Sell"
        if parsed.get("is_open_market"):
            return "Buy" if code == "P" else ("Sell" if code == "S" else None)
    upper = tx_type.upper()
    if "PURCHASE" in upper and "SALE" not in upper:
        return "Buy"
    if any(k in upper for k in ("SALE", "SELL")):
        return "Sell"
    return None


def build_form4_excerpt(tx: InsiderTransaction, parsed: dict | None = None) -> str:
    name = tx.insider_name or (parsed.get("insider_name") if parsed else None) or "Insider"
    tx_type = tx.transaction_type or (parsed.get("transaction_type") if parsed else "Transaction")
    if tx_type == "Form 4 filing" and parsed and parsed.get("transaction_type"):
        tx_type = parsed["transaction_type"]

    shares = tx.shares if tx.shares is not None else (parsed.get("shares") if parsed else None)
    price = tx.price if tx.price is not None else (parsed.get("price") if parsed else None)
    date = tx.filing_date or (parsed.get("filing_date") if parsed else "unknown")

    side = _side_label(tx_type, parsed, tx)
    type_part = f"{tx_type} ({side})" if side else tx_type
    parts = [f"{date} — {name} — {type_part}"]

    if shares is not None:
        sh = f"{shares:,.0f} sh"
        if price is not None:
            sh += f" @ ${price:.2f}"
        notional = shares * price if price else None
        if notional and notional >= 1_000_000:
            sh += f" (${notional / 1e6:.1f}M notional)"
        parts.append(sh)
    elif price is not None:
        parts.append(f"@ ${price:.2f}")

    has_detail = shares is not None or price is not None or side is not None
    if not has_detail:
        parts.append("(transaction details unavailable from filing)")

    return " — ".join(parts)


def _merge_tx_and_parsed(tx: InsiderTransaction, parsed: dict | None) -> InsiderTransaction:
    if not parsed:
        return tx
    return InsiderTransaction(
        filing_date=parsed.get("filing_date") or tx.filing_date,
        insider_name=parsed.get("insider_name") or tx.insider_name,
        title=tx.title,
        transaction_type=parsed.get("transaction_type") or tx.transaction_type,
        shares=parsed.get("shares") if parsed.get("shares") is not None else tx.shares,
        price=parsed.get("price") if parsed.get("price") is not None else tx.price,
        filing_url=tx.filing_url,
        acquired_disposed=parsed.get("acquired_disposed") or tx.acquired_disposed,
        transaction_code=parsed.get("transaction_code") or tx.transaction_code,
        is_open_market=bool(parsed.get("is_open_market")) if parsed.get("is_open_market") is not None else tx.is_open_market,
        is_derivative=bool(parsed.get("is_derivative")) if parsed.get("is_derivative") is not None else tx.is_derivative,
    )


def build_metadata_highlights(
    transactions: list[InsiderTransaction],
    limit: int = 3,
) -> list[InsiderFilingHighlight]:
    """Deterministic excerpts from transaction metadata only (no EDGAR fetch)."""
    highlights: list[InsiderFilingHighlight] = []
    for tx in transactions[:limit]:
        excerpt = build_form4_excerpt(tx)
        highlights.append(
            InsiderFilingHighlight(
                filing_date=tx.filing_date,
                insider_name=tx.insider_name,
                transaction_type=tx.transaction_type,
                excerpt=excerpt,
                excerpt_available=bool(excerpt),
                filing_url=tx.filing_url,
            )
        )
    return highlights


def _fetch_form4_parsed(url: str) -> dict | None:
    cached = get_cached("form4_excerpt", url)
    if isinstance(cached, dict):
        return cached
    if cached == "":
        return None
    try:
        parsed = parse_form4_from_filing_url(url)
    except Exception:
        set_cached_ttl("form4_excerpt", url, "", _EXCERPT_FAILURE_CACHE_TTL)
        return None
    if not parsed:
        set_cached_ttl("form4_excerpt", url, "", _EXCERPT_FAILURE_CACHE_TTL)
        return None
    set_cached_ttl("form4_excerpt", url, parsed, _EXCERPT_CACHE_TTL)
    return parsed


def _notable_to_transaction(n: NotableInsiderTransaction) -> InsiderTransaction:
    return InsiderTransaction(
        filing_date=n.filing_date,
        insider_name=n.insider_name,
        transaction_type=n.transaction_type,
        shares=n.shares,
        price=n.price,
        filing_url=n.filing_url,
    )


def _select_insider_targets(
    summary: InsiderSummary | None,
    timeline_transactions: list[InsiderTransaction],
    max_n: int = _MAX_EXCERPTS,
) -> list[InsiderTransaction]:
    targets: list[InsiderTransaction] = []
    seen: set[tuple[str, str]] = set()

    def add(tx: InsiderTransaction) -> None:
        key = (tx.filing_date, tx.insider_name)
        if key in seen:
            return
        seen.add(key)
        targets.append(tx)

    for n in summary.notable_transactions if summary else []:
        match = _find_tx(timeline_transactions, n.filing_date, n.insider_name)
        add(match if match else _notable_to_transaction(n))
        if len(targets) >= max_n:
            return targets[:max_n]

    for tx in timeline_transactions:
        if len(targets) >= max_n:
            break
        add(tx)

    return targets[:max_n]


async def enrich_insider_filings(
    summary: InsiderSummary | None,
    timeline_transactions: list[InsiderTransaction],
) -> tuple[InsiderSummary | None, list[InsiderFilingHighlight]]:
    if not summary and not timeline_transactions:
        return summary, []

    targets = _select_insider_targets(summary, timeline_transactions)
    if not targets:
        return summary, []

    async def _one(tx: InsiderTransaction) -> InsiderFilingHighlight:
        parsed = None
        if tx.filing_url:
            parsed = await asyncio.to_thread(_fetch_form4_parsed, tx.filing_url)
        merged = _merge_tx_and_parsed(tx, parsed)
        excerpt = build_form4_excerpt(merged, parsed)
        return InsiderFilingHighlight(
            filing_date=merged.filing_date,
            insider_name=merged.insider_name,
            transaction_type=merged.transaction_type,
            excerpt=excerpt,
            excerpt_available=bool(excerpt),
            filing_url=merged.filing_url,
        )

    highlights = list(await asyncio.gather(*[_one(tx) for tx in targets]))

    if summary and highlights:
        enriched_notable = []
        for n in summary.notable_transactions:
            ex = next(
                (
                    h.excerpt
                    for h in highlights
                    if h.filing_date == n.filing_date and h.insider_name == n.insider_name
                ),
                None,
            )
            enriched_notable.append(
                n.model_copy(
                    update={
                        "excerpt": ex,
                        "excerpt_available": bool(ex),
                        "filing_url": n.filing_url
                        or next(
                            (
                                h.filing_url
                                for h in highlights
                                if h.filing_date == n.filing_date
                                and h.insider_name == n.insider_name
                            ),
                            None,
                        ),
                    }
                )
            )
        summary = summary.model_copy(update={"notable_transactions": enriched_notable})

    return summary, highlights


def _filing_has_details(highlight: InsiderFilingHighlight) -> bool:
    excerpt = highlight.excerpt or ""
    return "transaction details unavailable" not in excerpt.lower()


def compute_insider_data_quality(
    highlights: list[InsiderFilingHighlight],
    *,
    insider_requested: bool,
    timeline_count: int = 0,
) -> dict:
    """Deterministic insider parse quality for LLM facts and gap sanitization."""
    if not insider_requested:
        return {"level": "not_requested", "filings_without_details": 0, "insider_requested": False}

    if timeline_count == 0 and not highlights:
        return {"level": "none", "filings_without_details": 0, "insider_requested": True}

    if not highlights:
        return {
            "level": "partial",
            "filings_without_details": timeline_count,
            "insider_requested": True,
        }

    without = sum(1 for h in highlights if not _filing_has_details(h))
    if without == 0:
        level = "full"
    elif without < len(highlights):
        level = "partial"
    else:
        level = "partial"

    return {
        "level": level,
        "filings_without_details": without,
        "filings_total": len(highlights),
        "insider_requested": True,
    }


def _find_tx(
    transactions: list[InsiderTransaction],
    filing_date: str,
    insider_name: str,
) -> InsiderTransaction | None:
    for tx in transactions:
        if tx.filing_date == filing_date and tx.insider_name == insider_name:
            return tx
    return None
