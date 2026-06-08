"""Dark pool flow with vendor or FINRA proxy fallback."""

from __future__ import annotations

from datetime import UTC, datetime

from trade_sentinel_api.models.schemas import DarkPoolPrint, DarkPoolSummary
from trade_sentinel_api.services.finra_short_volume import fetch_finra_short_volume
from trade_sentinel_api.services.providers import get_provider


class FinraDarkPoolProxyProvider:
    name = "finra_proxy"

    def is_available(self) -> bool:
        return True

    def fetch_prints(self, ticker: str, *, days: int = 5) -> object:
        del days
        return fetch_finra_short_volume(ticker)


async def fetch_dark_pool_summary(ticker: str, *, days: int = 5) -> DarkPoolSummary:
    sym = ticker.upper()
    provider = get_provider("dark_pool")
    if getattr(provider, "is_available", lambda: False)() and provider.name == "unusual_whales":
        result = provider.fetch_prints(sym, days=days)  # type: ignore[attr-defined]
        if result.data_available and result.payload:
            prints = [
                DarkPoolPrint(
                    ticker=sym,
                    trade_date=str(p.get("date") or p.get("trade_date") or "")[:10],
                    price=float(p["price"]) if p.get("price") is not None else None,
                    size=float(p["size"]) if p.get("size") is not None else None,
                    data_source=result.data_source,
                )
                for p in result.payload
            ]
            return DarkPoolSummary(
                ticker=sym,
                as_of=datetime.now(UTC),
                prints=prints,
                print_count=len(prints),
                data_source=result.data_source,
                data_available=True,
            )

    row = fetch_finra_short_volume(sym)
    if not row:
        return DarkPoolSummary(
            ticker=sym,
            as_of=datetime.now(UTC),
            message="Dark pool data unavailable (no vendor key; FINRA file missing).",
        )

    try:
        short_vol = float(row.get("ShortVolume") or 0)
        total = float(row.get("TotalVolume") or 0)
        ratio = short_vol / total if total else 0
    except ValueError:
        ratio = 0

    spot = _last_price(sym)
    print_row = DarkPoolPrint(
        ticker=sym,
        trade_date=datetime.now(UTC).strftime("%Y-%m-%d"),
        size=short_vol if short_vol else None,
        price=spot,
        signature_bullish=ratio >= 0.45 if ratio else None,
        data_source="finra_proxy",
    )
    return DarkPoolSummary(
        ticker=sym,
        as_of=datetime.now(UTC),
        prints=[print_row] if short_vol else [],
        print_count=1 if short_vol else 0,
        bullish_signature_count=1 if ratio >= 0.45 else 0,
        data_source="finra_proxy",
        data_available=bool(short_vol),
        message="FINRA short-volume proxy (not true dark-pool prints).",
    )


def _last_price(ticker: str) -> float | None:
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).fast_info
        val = getattr(info, "last_price", None) or info.get("lastPrice")
        return float(val) if val else None
    except Exception:
        return None
