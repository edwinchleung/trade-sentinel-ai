import asyncio
import logging
import math
from datetime import UTC, datetime

import httpx
import yfinance as yf

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import FredObservation, MacroSignal, MacroSignalsSnapshot

logger = logging.getLogger(__name__)

_SIGNAL_CATALOG: list[tuple[str, str]] = [
    ("^VIX", "VIX"),
    ("^TNX", "US 10Y Yield"),
    ("^IRX", "US 3M Yield"),
    ("^FVX", "US 5Y Yield"),
    ("DX-Y.NYB", "US Dollar Index"),
    ("CL=F", "WTI Crude"),
    ("GC=F", "Gold"),
    ("SPY", "S&P 500 (SPY)"),
    ("QQQ", "Nasdaq 100 (QQQ)"),
    ("IWM", "Russell 2000 (IWM)"),
    ("HYG", "High Yield Credit (HYG)"),
    ("TLT", "Long Treasury (TLT)"),
]

_FRED_SIMPLE_SERIES: list[tuple[str, str]] = [
    ("UNRATE", "Unemployment Rate"),
    ("FEDFUNDS", "Fed Funds Rate"),
]

_CPI_SERIES = "CPIAUCSL"
_T10Y2Y_SERIES = "T10Y2Y"
_CPI_YOY_MONTHS = 13


def _finite_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _pct_change(current: float, prior: float) -> float | None:
    if prior == 0:
        return None
    return round((current - prior) / abs(prior) * 100, 2)


def _parse_fred_value(raw) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s == ".":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _valid_fred_observations(observations: list) -> list[tuple[str, float]]:
    """Return (date, value) pairs with numeric values, preserving API sort order."""
    out: list[tuple[str, float]] = []
    for row in observations:
        if not isinstance(row, dict):
            continue
        val = _parse_fred_value(row.get("value"))
        if val is None:
            continue
        out.append((str(row.get("date", "")), val))
    return out


def _fred_http_gap(status_code: int | None, series_id: str) -> str:
    if status_code in (401, 403):
        return "fred_auth_failed"
    return f"fred_{series_id}_fetch_failed"


def _fetch_signal_sync(symbol: str, label: str) -> MacroSignal:
    try:
        hist = yf.Ticker(symbol).history(period="1mo", interval="1d")
    except Exception:
        return MacroSignal(symbol=symbol, label=label)

    if hist is None or hist.empty:
        return MacroSignal(symbol=symbol, label=label)

    close = hist["Close"]
    level = _finite_float(close.iloc[-1])
    if level is None:
        return MacroSignal(symbol=symbol, label=label)

    change_1d = None
    change_5d = None
    if len(close) > 1:
        prior_1d = _finite_float(close.iloc[-2])
        if prior_1d is not None:
            change_1d = _pct_change(level, prior_1d)
    if len(close) > 5:
        prior_5d = _finite_float(close.iloc[-6])
        if prior_5d is not None:
            change_5d = _pct_change(level, prior_5d)
    elif len(close) > 1:
        prior_start = _finite_float(close.iloc[0])
        if prior_start is not None:
            change_5d = _pct_change(level, prior_start)

    return MacroSignal(
        symbol=symbol,
        label=label,
        level=round(level, 4),
        change_1d_pct=change_1d,
        change_5d_pct=change_5d,
    )


def _t10y2y_proxy_from_signals(signals: list[MacroSignal]) -> FredObservation | None:
    by_symbol = {s.symbol: s for s in signals}
    tnx = by_symbol.get("^TNX")
    fvx = by_symbol.get("^FVX")
    if not tnx or not fvx or tnx.level is None or fvx.level is None:
        return None
    spread = round(tnx.level - fvx.level, 4)
    return FredObservation(
        series_id="T10Y2Y_PROXY",
        label="10Y-5Y spread (yfinance proxy)",
        value=spread,
        observation_date=datetime.now(UTC).date().isoformat(),
    )


def _apply_fred_fallbacks(
    signals: list[MacroSignal],
    official: list[FredObservation],
    gaps: list[str],
) -> tuple[list[FredObservation], list[str]]:
    """Remove redundant gaps when yfinance fallbacks cover FRED failures."""
    has_t10y2y = any(o.series_id in (_T10Y2Y_SERIES, "T10Y2Y_PROXY") for o in official)
    if not has_t10y2y and "fred_T10Y2Y_fetch_failed" in gaps:
        proxy = _t10y2y_proxy_from_signals(signals)
        if proxy:
            official.append(proxy)
            gaps = [g for g in gaps if g != "fred_T10Y2Y_fetch_failed"]

    has_cpi_yoy = any(o.series_id == "CPI_YOY" for o in official)
    if not has_cpi_yoy:
        gaps = [
            g
            for g in gaps
            if g not in (f"fred_{_CPI_SERIES}_fetch_failed", "fred_CPI_YOY_compute_failed")
        ]
        if "fred_cpi_yoy_unavailable" not in gaps:
            gaps.append("fred_cpi_yoy_unavailable")

    if _derive_risk_and_curve(signals)[0] is not None:
        gaps = [g for g in gaps if g != "fred_T10Y2Y_fetch_failed"]

    return official, gaps


async def _fetch_fred_series(
    client: httpx.AsyncClient,
    api_key: str,
    series_id: str,
    limit: int,
) -> tuple[list, str | None, int | None]:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    try:
        resp = await client.get(url, params=params)
        status = resp.status_code
        resp.raise_for_status()
        data = resp.json()
        return data.get("observations") or [], None, status
    except httpx.HTTPStatusError as exc:
        logger.debug("FRED %s HTTP %s", series_id, exc.response.status_code)
        return [], _fred_http_gap(exc.response.status_code, series_id), exc.response.status_code
    except (httpx.HTTPError, ValueError, TypeError):
        logger.debug("FRED %s request failed", series_id, exc_info=True)
        return [], _fred_http_gap(None, series_id), None


async def _fetch_fred_observations(
    signals: list[MacroSignal],
) -> tuple[list[FredObservation], list[str]]:
    settings = get_settings()
    if not settings.fred_api_key:
        return _apply_fred_fallbacks(signals, [], ["fred_api_key_missing"])

    gaps: list[str] = []
    official: list[FredObservation] = []
    auth_failed = False

    async with httpx.AsyncClient(timeout=12.0) as client:
        for series_id, label in _FRED_SIMPLE_SERIES:
            obs, gap, _ = await _fetch_fred_series(client, settings.fred_api_key, series_id, 1)
            if gap:
                gaps.append(gap)
                if gap == "fred_auth_failed":
                    auth_failed = True
                continue
            valid = _valid_fred_observations(obs)
            if not valid:
                gaps.append(f"fred_{series_id}_empty")
                continue
            date_str, val = valid[0]
            official.append(
                FredObservation(
                    series_id=series_id,
                    label=label,
                    value=val,
                    observation_date=date_str or None,
                )
            )

        if not auth_failed:
            obs, gap, _ = await _fetch_fred_series(
                client, settings.fred_api_key, _T10Y2Y_SERIES, 1
            )
            if gap:
                gaps.append(gap)
            else:
                valid = _valid_fred_observations(obs)
                if valid:
                    date_str, val = valid[0]
                    official.append(
                        FredObservation(
                            series_id=_T10Y2Y_SERIES,
                            label="10Y-2Y Treasury Spread",
                            value=val,
                            observation_date=date_str or None,
                        )
                    )
                else:
                    gaps.append(f"fred_{_T10Y2Y_SERIES}_empty")

            obs, gap, _ = await _fetch_fred_series(
                client, settings.fred_api_key, _CPI_SERIES, _CPI_YOY_MONTHS
            )
            if gap:
                gaps.append(gap)
            else:
                valid = _valid_fred_observations(obs)
                if len(valid) >= _CPI_YOY_MONTHS:
                    latest_date, latest = valid[0]
                    _, year_ago = valid[_CPI_YOY_MONTHS - 1]
                    yoy = _pct_change(latest, year_ago)
                    if yoy is not None:
                        official.append(
                            FredObservation(
                                series_id="CPI_YOY",
                                label="CPI YoY %",
                                value=yoy,
                                observation_date=latest_date or None,
                            )
                        )
                    else:
                        gaps.append("fred_cpi_yoy_unavailable")
                else:
                    gaps.append("fred_cpi_yoy_unavailable")

    if auth_failed:
        gaps = ["fred_auth_failed"]

    return _apply_fred_fallbacks(signals, official, gaps)


def _derive_risk_and_curve(signals: list[MacroSignal]) -> tuple[float | None, str]:
    settings = get_settings()
    by_symbol = {s.symbol: s for s in signals}
    tnx = by_symbol.get("^TNX")
    irx = by_symbol.get("^IRX")
    curve_bps = None
    if tnx and irx and tnx.level is not None and irx.level is not None:
        curve_bps = round((tnx.level - irx.level) * 100, 1)

    vix = by_symbol.get("^VIX")
    if vix and vix.level is not None:
        if vix.level >= settings.macro_vix_elevated_threshold:
            return curve_bps, "elevated_vix"
        return curve_bps, "normal"
    return curve_bps, "unavailable"


async def fetch_macro_signals() -> MacroSignalsSnapshot:
    as_of = datetime.now(UTC)
    gaps: list[str] = []

    signal_tasks = [
        asyncio.to_thread(_fetch_signal_sync, sym, label) for sym, label in _SIGNAL_CATALOG
    ]
    signals = list(await asyncio.gather(*signal_tasks))
    if not any(s.level is not None for s in signals):
        gaps.append("yfinance_signals_unavailable")

    official, fred_gaps = await _fetch_fred_observations(signals)
    gaps.extend(fred_gaps)

    curve_bps, risk_tone = _derive_risk_and_curve(signals)

    return MacroSignalsSnapshot(
        as_of=as_of,
        signals=signals,
        yield_curve_10y_3m_bps=curve_bps,
        risk_tone=risk_tone,
        official=official,
        data_gaps=gaps,
    )
