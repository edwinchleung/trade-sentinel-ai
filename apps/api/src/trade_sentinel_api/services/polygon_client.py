"""Optional Polygon.io client — falls back when API key unset."""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import pandas as pd

from trade_sentinel_api.config import get_settings

_BASE = "https://api.polygon.io"


def is_polygon_enabled() -> bool:
    return bool(get_settings().polygon_api_key.strip())


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().polygon_api_key}"}


def fetch_ohlcv(ticker: str, *, days: int = 60) -> pd.DataFrame | None:
    if not is_polygon_enabled():
        return None
    end = date.today()
    start = end - timedelta(days=days)
    url = (
        f"{_BASE}/v2/aggs/ticker/{ticker.upper()}/range/1/day/"
        f"{start.isoformat()}/{end.isoformat()}"
    )
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params={"adjusted": "true", "sort": "asc"}, headers=_headers())
            resp.raise_for_status()
            results = resp.json().get("results") or []
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    if not results:
        return None
    rows = []
    for bar in results:
        ts = bar.get("t")
        if ts is None:
            continue
        rows.append(
            {
                "Date": pd.Timestamp(ts, unit="ms"),
                "Open": bar.get("o"),
                "High": bar.get("h"),
                "Low": bar.get("l"),
                "Close": bar.get("c"),
                "Volume": bar.get("v"),
            }
        )
    if not rows:
        return None
    df = pd.DataFrame(rows).set_index("Date")
    return df


def fetch_options_snapshot(ticker: str) -> list[dict] | None:
    """Fetch options contracts with day volume/OI from Polygon snapshot."""
    if not is_polygon_enabled():
        return None
    url = f"{_BASE}/v3/snapshot/options/{ticker.upper()}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, headers=_headers())
            resp.raise_for_status()
            return resp.json().get("results") or []
    except (httpx.HTTPError, ValueError, KeyError):
        return None
