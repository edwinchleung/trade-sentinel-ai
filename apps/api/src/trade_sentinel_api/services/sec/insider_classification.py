"""Centralized Form 4 transaction classification for open-market insider signals."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from trade_sentinel_api.models.schemas import InsiderTransaction

OPEN_MARKET_BUY = {"P"}
OPEN_MARKET_SELL = {"S"}
EXCLUDED_CODES = {"A", "M", "G", "F"}

InsiderSide = Literal["buy", "sell", "excluded", "other"]
ClassificationMode = Literal["open_market", "all"]


def classify_transaction_code(
    code: str | None,
    acquired_disposed: str | None = None,
) -> InsiderSide:
    """Classify a Form 4 transaction by SEC transaction code."""
    normalized = (code or "").strip().upper()[:1]
    if not normalized:
        ad = (acquired_disposed or "").strip().upper()[:1]
        if ad == "A":
            return "other"
        if ad == "D":
            return "other"
        return "other"

    if normalized in EXCLUDED_CODES:
        return "excluded"
    if normalized in OPEN_MARKET_BUY:
        return "buy"
    if normalized in OPEN_MARKET_SELL:
        return "sell"
    return "other"


def is_open_market_transaction(code: str | None, acquired_disposed: str | None = None) -> bool:
    return classify_transaction_code(code, acquired_disposed) in ("buy", "sell")


def classify_insider_transaction(
    tx: InsiderTransaction,
    *,
    mode: ClassificationMode = "open_market",
) -> InsiderSide:
    """Classify an InsiderTransaction row."""
    if tx.is_open_market is not None:
        if tx.is_open_market:
            code = (tx.transaction_code or "").upper()[:1]
            if code == "S" or "SALE" in (tx.transaction_type or "").upper():
                return "sell"
            return "buy"
        if mode == "open_market":
            code = (tx.transaction_code or "").upper()[:1]
            if code in EXCLUDED_CODES:
                return "excluded"
            return "other"

    side = classify_transaction_code(tx.transaction_code, tx.acquired_disposed)
    if side != "other":
        return side

    tx_type = (tx.transaction_type or "").upper()
    if "SALE" in tx_type or "SELL" in tx_type:
        return "sell" if mode == "all" else "other"
    if "PURCHASE" in tx_type:
        return "buy" if mode == "all" else "other"

    return "other"


def side_for_feed(
    *,
    transaction_code: str | None,
    acquired_disposed: str | None,
    transaction_type: str | None,
    is_open_market: bool | None,
) -> Literal["buy", "sell", "other"]:
    """Map to feed side for SmartMoneyFeedItem."""
    if is_open_market:
        code = (transaction_code or "").upper()[:1]
        if code == "S":
            return "sell"
        if code == "P":
            return "buy"
        ad = (acquired_disposed or "").strip().upper()[:1]
        if ad == "D":
            return "sell"
        if ad == "A":
            return "buy"
    side = classify_transaction_code(transaction_code, acquired_disposed)
    if side == "buy":
        return "buy"
    if side == "sell":
        return "sell"
    return "other"


def detect_cluster_buying(
    transactions: list[InsiderTransaction],
    *,
    window_days: int = 7,
    min_insiders: int = 2,
    reference_date: date | None = None,
) -> bool:
    """True when >= min_insiders distinct insiders open-market buy within window_days."""
    ref = reference_date or date.today()
    cutoff = ref - timedelta(days=window_days)
    buyers: set[str] = set()

    for tx in transactions:
        if not tx.is_open_market and classify_insider_transaction(tx) != "buy":
            continue
        if not tx.is_open_market:
            continue
        try:
            filing = date.fromisoformat(tx.filing_date[:10])
        except ValueError:
            continue
        if filing < cutoff or filing > ref:
            continue
        name = (tx.insider_name or "").strip().lower()
        if name and name != "unknown insider":
            buyers.add(name)

    return len(buyers) >= min_insiders


def detect_cluster_buying_by_ticker(
    items: list,
    *,
    window_days: int = 7,
    min_insiders: int = 2,
) -> dict[str, bool]:
    """Mark tickers with cluster open-market buying from feed-like items."""
    by_ticker: dict[str, list] = {}
    for item in items:
        ticker = getattr(item, "ticker", None) or (item.get("ticker") if isinstance(item, dict) else None)
        if not ticker:
            continue
        by_ticker.setdefault(ticker, []).append(item)

    result: dict[str, bool] = {}
    for ticker, group in by_ticker.items():
        txs = []
        for g in group:
            if getattr(g, "is_open_market", False) and getattr(g, "side", None) == "buy":
                txs.append(
                    InsiderTransaction(
                        filing_date=g.filing_date,
                        insider_name=g.insider_name or "Unknown insider",
                        transaction_type=g.transaction_type or "",
                        is_open_market=True,
                        transaction_code=getattr(g, "transaction_code", None),
                    )
                )
        result[ticker] = detect_cluster_buying(txs, window_days=window_days, min_insiders=min_insiders)
    return result
