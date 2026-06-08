import asyncio
from datetime import UTC, date, datetime, timedelta

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import EarningsSnapshot


async def fetch_earnings_snapshot(ticker: str) -> EarningsSnapshot:
    symbol = ticker.upper().strip()
    historical = await _fetch_finnhub_historical(symbol)
    upcoming = await _fetch_finnhub_earnings_calendar(symbol)
    yf_extra = await asyncio.to_thread(_fetch_yfinance_earnings_extra_sync, symbol)

    if historical:
        return _merge_earnings_snapshot(historical, upcoming, yf_extra)
    if yf_extra and yf_extra.data_available:
        return _merge_earnings_snapshot(yf_extra, upcoming, None)
    return EarningsSnapshot(data_available=False, message="Earnings data unavailable.")


async def _fetch_finnhub_historical(ticker: str) -> EarningsSnapshot | None:
    settings = get_settings()
    if not settings.finnhub_api_key:
        return None
    url = "https://finnhub.io/api/v1/stock/earnings"
    params = {"symbol": ticker, "token": settings.finnhub_api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    if not isinstance(data, list) or not data:
        return None

    latest = data[0]
    actual = latest.get("actual")
    estimate = latest.get("estimate")
    surprise_pct = latest.get("surprisePercent")
    rev_actual = latest.get("revenueActual") or latest.get("revenue")
    rev_estimate = latest.get("revenueEstimate") or latest.get("revenueEst")
    revenue_surprise_pct = _revenue_surprise_pct(rev_actual, rev_estimate)
    if surprise_pct is None and actual is not None and estimate:
        try:
            surprise_pct = ((float(actual) - float(estimate)) / abs(float(estimate))) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            surprise_pct = None

    return EarningsSnapshot(
        last_eps_actual=_safe_float(actual),
        last_eps_estimate=_safe_float(estimate),
        surprise_pct=_safe_float(surprise_pct),
        revenue_beat_miss=_beat_miss(rev_actual, rev_estimate),
        last_revenue_actual=_safe_float(rev_actual),
        last_revenue_estimate=_safe_float(rev_estimate),
        revenue_surprise_pct=revenue_surprise_pct,
        data_available=bool(actual is not None or estimate is not None or rev_actual),
    )


async def _fetch_finnhub_earnings_calendar(ticker: str) -> dict | None:
    settings = get_settings()
    if not settings.finnhub_api_key:
        return None
    today = datetime.now(UTC).date()
    end = today + timedelta(days=90)
    url = "https://finnhub.io/api/v1/calendar/earnings"
    params = {
        "symbol": ticker,
        "from": today.isoformat(),
        "to": end.isoformat(),
        "token": settings.finnhub_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    rows = data.get("earningsCalendar") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return None

    best_date = None
    best_days = None
    rev_est = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym = (row.get("symbol") or row.get("ticker") or "").upper()
        if sym and sym != ticker:
            continue
        raw_date = row.get("date") or row.get("period")
        if not raw_date:
            continue
        try:
            d = datetime.fromisoformat(str(raw_date)[:10]).date()
        except ValueError:
            continue
        if d < today:
            continue
        days = (d - today).days
        if best_days is None or days < best_days:
            best_days = days
            best_date = d.isoformat()
            rev_est = row.get("revenueEstimate") or row.get("revenueEst")

    if best_date is None:
        return None
    return {
        "next_report_date": best_date,
        "days_until": best_days,
        "last_revenue_estimate": _safe_float(rev_est),
    }


def _fetch_yfinance_earnings_extra_sync(ticker: str) -> EarningsSnapshot:
    from trade_sentinel_api.services.yfinance_bundle import (
        earnings_from_bundle,
        load_ticker_bundle_sync,
    )

    bundle = load_ticker_bundle_sync(ticker)
    return earnings_from_bundle(bundle)


def _coerce_to_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, list):
        for item in val:
            d = _coerce_to_date(item)
            if d is not None:
                return d
        return None
    try:
        if hasattr(val, "date") and callable(val.date):
            return val.date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(str(val)[:10]).date()
    except (TypeError, ValueError):
        return None


def _dates_from_calendar_dict(cal: dict) -> list[date]:
    dates: list[date] = []
    for key, val in cal.items():
        key_lower = str(key).lower()
        if "earnings" not in key_lower or "date" not in key_lower:
            continue
        items = val if isinstance(val, list) else [val]
        for item in items:
            d = _coerce_to_date(item)
            if d is not None:
                dates.append(d)
    return dates


def _parse_yfinance_next_earnings(stock, info: dict, cal) -> tuple[str | None, int | None]:
    today = datetime.now(UTC).date()
    candidates: list[date] = []

    earnings_dates = info.get("earningsDate")
    if earnings_dates is not None:
        items = earnings_dates if isinstance(earnings_dates, list) else [earnings_dates]
        for dt in items:
            try:
                if hasattr(dt, "date"):
                    candidates.append(dt.date())
                else:
                    candidates.append(datetime.fromisoformat(str(dt)[:10]).date())
            except (TypeError, ValueError):
                continue

    try:
        edf = stock.earnings_dates
    except Exception:
        edf = None

    if edf is not None and not getattr(edf, "empty", True):
        for idx in edf.index:
            try:
                d = idx.date() if hasattr(idx, "date") else datetime.fromisoformat(str(idx)[:10]).date()
                candidates.append(d)
            except (TypeError, ValueError):
                continue

    if isinstance(cal, dict):
        candidates.extend(_dates_from_calendar_dict(cal))

    if cal is not None:
        try:
            if hasattr(cal, "index"):
                for idx in cal.index:
                    if "earnings" in str(idx).lower():
                        val = cal.loc[idx]
                        if hasattr(val, "iloc"):
                            val = val.iloc[0]
                        try:
                            if hasattr(val, "date"):
                                candidates.append(val.date())
                            else:
                                candidates.append(datetime.fromisoformat(str(val)[:10]).date())
                        except (TypeError, ValueError):
                            pass
        except Exception:
            pass

    future = sorted({d for d in candidates if d >= today})
    if not future:
        return None, None
    next_d = future[0]
    return next_d.isoformat(), (next_d - today).days


def _merge_earnings_snapshot(
    base: EarningsSnapshot,
    upcoming: dict | None,
    yf_extra: EarningsSnapshot | None,
) -> EarningsSnapshot:
    next_date = base.next_report_date
    days_until = base.days_until
    rev_est = base.last_revenue_estimate

    if upcoming:
        if not next_date and upcoming.get("next_report_date"):
            next_date = upcoming["next_report_date"]
            days_until = upcoming.get("days_until")
        if rev_est is None and upcoming.get("last_revenue_estimate") is not None:
            rev_est = upcoming["last_revenue_estimate"]

    if yf_extra:
        if not next_date and yf_extra.next_report_date:
            next_date = yf_extra.next_report_date
            days_until = yf_extra.days_until
        if base.last_eps_actual is None and yf_extra.last_eps_actual is not None:
            base = base.model_copy(update={"last_eps_actual": yf_extra.last_eps_actual})
        if base.last_eps_estimate is None and yf_extra.last_eps_estimate is not None:
            base = base.model_copy(update={"last_eps_estimate": yf_extra.last_eps_estimate})
        if base.last_revenue_actual is None and yf_extra.last_revenue_actual is not None:
            base = base.model_copy(
                update={"last_revenue_actual": yf_extra.last_revenue_actual}
            )

    rev_actual = base.last_revenue_actual
    revenue_surprise_pct = _revenue_surprise_pct(rev_actual, rev_est)

    data_available = bool(
        next_date
        or base.last_eps_actual is not None
        or base.last_eps_estimate is not None
        or rev_actual is not None
    )

    message = None
    if data_available and not next_date:
        message = "Next earnings date unavailable from data providers."

    return base.model_copy(
        update={
            "next_report_date": next_date,
            "days_until": days_until,
            "last_revenue_estimate": rev_est,
            "revenue_beat_miss": _beat_miss(rev_actual, rev_est),
            "revenue_surprise_pct": revenue_surprise_pct,
            "data_available": data_available,
            "message": message,
        }
    )


def _revenue_surprise_pct(rev_actual, rev_estimate) -> float | None:
    if rev_actual is None or rev_estimate is None:
        return None
    try:
        return round(
            ((float(rev_actual) - float(rev_estimate)) / abs(float(rev_estimate))) * 100,
            2,
        )
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val), 4)
    except (TypeError, ValueError):
        return None


def _beat_miss(actual, estimate) -> str | None:
    try:
        if actual is None or estimate is None:
            return None
        a, e = float(actual), float(estimate)
        if a > e:
            return "beat"
        if a < e:
            return "miss"
        return "inline"
    except (TypeError, ValueError):
        return None
