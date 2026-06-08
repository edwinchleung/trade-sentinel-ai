"""Unusual Whales dark pool vendor (optional API key)."""

from __future__ import annotations

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.providers.base import ProviderResult

_BASE = "https://api.unusualwhales.com/api"


class UnusualWhalesDarkPoolProvider:
    name = "unusual_whales"

    def is_available(self) -> bool:
        return bool(get_settings().unusual_whales_api_key.strip())

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {get_settings().unusual_whales_api_key}"}

    def fetch_prints(self, ticker: str, *, days: int = 5) -> ProviderResult:
        if not self.is_available():
            return ProviderResult(message="Unusual Whales API key not set.")
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    f"{_BASE}/darkpool/{ticker.upper()}",
                    params={"days": days},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            return ProviderResult(message=str(exc))
        prints = data if isinstance(data, list) else data.get("data") or []
        return ProviderResult(
            data_available=bool(prints),
            data_source=self.name,
            payload=prints,
        )
