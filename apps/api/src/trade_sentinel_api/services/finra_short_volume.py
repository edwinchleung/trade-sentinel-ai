"""FINRA short-volume DIX proxy."""

from __future__ import annotations

import csv
import io
import logging
from datetime import UTC, datetime

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import DixProxySnapshot

logger = logging.getLogger(__name__)

_FINRA_URL = "https://cdn.finra.org/equity/regsho/daily"


def fetch_finra_short_volume(ticker: str, *, date_label: str | None = None) -> dict | None:
    symbol = ticker.upper()
    label = date_label or datetime.now(UTC).strftime("%Y%m%d")
    url = f"{_FINRA_URL}/{label}/CNMSshvol{label}.txt"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            text = resp.text
    except httpx.HTTPError as exc:
        logger.debug("FINRA short volume fetch failed: %s", exc)
        return None

    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    for row in reader:
        if (row.get("Symbol") or "").upper() == symbol:
            return row
    return None


def compute_dix_proxy(ticker: str) -> DixProxySnapshot:
    settings = get_settings()
    sym = ticker.upper()
    if not settings.dix_finra_proxy_enabled:
        return DixProxySnapshot(
            ticker=sym,
            as_of=datetime.now(UTC),
            message="DIX FINRA proxy disabled.",
        )

    row = fetch_finra_short_volume(sym)
    if not row:
        return DixProxySnapshot(
            ticker=sym,
            as_of=datetime.now(UTC),
            message="FINRA short volume file unavailable for today.",
        )

    try:
        short_vol = float(row.get("ShortVolume") or 0)
        total_vol = float(row.get("TotalVolume") or 0)
    except ValueError:
        return DixProxySnapshot(ticker=sym, as_of=datetime.now(UTC), message="Invalid FINRA row.")

    ratio = round(short_vol / total_vol * 100, 2) if total_vol > 0 else None
    elevated = bool(ratio and ratio >= 45.0)
    return DixProxySnapshot(
        ticker=sym,
        as_of=datetime.now(UTC),
        short_volume_ratio=ratio,
        elevated_dark_accumulation=elevated,
        data_source="finra_proxy",
        data_available=ratio is not None,
        message="High short-volume ratio may indicate dark-pool accumulation (proxy)." if elevated else None,
    )
