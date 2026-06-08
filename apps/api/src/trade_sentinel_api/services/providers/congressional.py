"""Congressional trade data providers."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import CongressionalTrade
from trade_sentinel_api.services.providers.base import ProviderResult

logger = logging.getLogger(__name__)


class CapitolTradesProvider:
    name = "capitol_trades"

    def is_available(self) -> bool:
        return True

    def fetch_trades(self, *, days: int = 30) -> ProviderResult:
        settings = get_settings()
        headers = {}
        if settings.congressional_trades_api_key.strip():
            headers["Authorization"] = f"Bearer {settings.congressional_trades_api_key}"
        url = "https://api.capitoltrades.com/trades"
        params = {"pageSize": 100}
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url, params=params, headers=headers)
                if resp.status_code == 404:
                    return ProviderResult(message="Capitol Trades API unavailable.")
                resp.raise_for_status()
                body = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("Capitol trades fetch failed: %s", exc)
            return ProviderResult(message=str(exc))

        raw = body.get("data") or body.get("trades") or []
        cutoff = date.today() - timedelta(days=days)
        trades: list[CongressionalTrade] = []
        for item in raw:
            disc = (item.get("disclosureDate") or item.get("disclosure_date") or "")[:10]
            try:
                if disc and date.fromisoformat(disc) < cutoff:
                    continue
            except ValueError:
                pass
            trades.append(
                CongressionalTrade(
                    politician=str(item.get("politician") or item.get("name") or "Unknown"),
                    chamber=_normalize_chamber(item.get("chamber")),
                    ticker=(item.get("ticker") or item.get("assetTicker") or "").upper() or None,
                    transaction_date=(item.get("transactionDate") or item.get("txDate") or "")[:10] or None,
                    disclosure_date=disc or None,
                    transaction_type=item.get("transactionType") or item.get("type"),
                    amount_range=item.get("amount") or item.get("amountRange"),
                    source_url=item.get("sourceUrl") or item.get("url"),
                )
            )
        return ProviderResult(
            data_available=bool(trades),
            data_source=self.name,
            payload=trades,
        )


class HouseSenateScrapeProvider:
    name = "house_senate_scrape"

    def is_available(self) -> bool:
        return True

    def fetch_trades(self, *, days: int = 30) -> ProviderResult:
        del days
        return ProviderResult(
            message="House/Senate scrape provider not populated; configure Capitol Trades or API key.",
        )


def _normalize_chamber(raw: str | None) -> str:
    val = (raw or "").lower()
    if "senate" in val:
        return "senate"
    if "house" in val:
        return "house"
    return "unknown"
