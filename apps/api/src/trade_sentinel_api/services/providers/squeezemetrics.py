"""SqueezeMetrics GEX/DIX vendor (optional API key)."""

from __future__ import annotations

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.providers.base import ProviderResult

_BASE = "https://squeezemetrics.com/monitor/api"


class SqueezeMetricsProvider:
    name = "squeezemetrics"

    def is_available(self) -> bool:
        return bool(get_settings().squeezemetrics_api_key.strip())

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {get_settings().squeezemetrics_api_key}"}

    def fetch_gex(self, symbol: str) -> ProviderResult:
        if not self.is_available():
            return ProviderResult(message="SqueezeMetrics API key not set.")
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(f"{_BASE}/gex/{symbol.upper()}", headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            return ProviderResult(message=str(exc))
        return ProviderResult(data_available=True, data_source=self.name, payload=data)

    def fetch_dix(self, symbol: str) -> ProviderResult:
        if not self.is_available():
            return ProviderResult(message="SqueezeMetrics API key not set.")
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(f"{_BASE}/dix/{symbol.upper()}", headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            return ProviderResult(message=str(exc))
        return ProviderResult(data_available=True, data_source=self.name, payload=data)
