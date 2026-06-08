import asyncio
from datetime import date

import yfinance as yf

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    OptionsExpiryBreakdown,
    OptionsFlowFlag,
    OptionsStrikeVolume,
    OptionsUnusualContract,
    Warning,
    WarningSeverity,
)
from trade_sentinel_api.services.polygon_client import fetch_options_snapshot, is_polygon_enabled

_MAX_EXPIRIES = 3
_MAX_OI_EXPIRIES = 12
_TOP_STRIKES = 5
_OTM_PCT = 0.05
_SHORT_DATED_DTE = 7
_SWING_DTE_MIN = 30
_SWING_DTE_MAX = 90
_MACRO_DTE_MIN = 180


def _strike_open_interest(row) -> float | None:
    if "openInterest" not in row.index:
        return None
    raw = row.get("openInterest")
    if raw is None or (isinstance(raw, float) and raw != raw):
        return None
    try:
        oi = float(raw)
    except (TypeError, ValueError):
        return None
    return oi if oi > 0 else None


def _days_to_expiry(expiry: str) -> int | None:
    try:
        exp = date.fromisoformat(expiry)
        return (exp - date.today()).days
    except ValueError:
        return None


def _is_otm(strike: float, spot: float, side: str) -> bool:
    if spot <= 0:
        return False
    if side == "call":
        return strike > spot * (1 + _OTM_PCT)
    return strike < spot * (1 - _OTM_PCT)


def _conviction_band_from_contracts(contracts: list[OptionsUnusualContract]) -> str | None:
    if not contracts:
        return None
    short_prem = 0.0
    swing_prem = 0.0
    macro_prem = 0.0
    for c in contracts:
        prem = c.premium_estimate or 0.0
        dte = c.days_to_expiry
        if dte is None:
            continue
        if dte <= _SHORT_DATED_DTE:
            short_prem += prem
        elif _SWING_DTE_MIN <= dte <= _SWING_DTE_MAX:
            swing_prem += prem
        elif dte >= _MACRO_DTE_MIN:
            macro_prem += prem
    totals = {"short": short_prem, "swing": swing_prem, "macro": macro_prem}
    best = max(totals, key=totals.get)
    return best if totals[best] > 0 else None


def _build_flow_flag(
    *,
    aggregate_ratio: float | None,
    total_call_vol: float,
    total_put_vol: float,
    total_premium_est: float,
    max_vol_oi: float,
    unusual_contracts: list[OptionsUnusualContract],
    expiry_breakdown: list[OptionsExpiryBreakdown],
    top_strikes: list[OptionsStrikeVolume],
    total_oi_value: float | None,
    oi_rows_seen: int,
    otm_premium_total: float | None,
    short_dated_premium: float,
    warnings: list[Warning],
) -> tuple[OptionsFlowFlag, list[Warning]]:
    settings = get_settings()
    vol_oi_unusual = settings.options_vol_oi_unusual
    vol_oi_high = settings.options_vol_oi_high
    pc_bullish_max = settings.options_pc_bullish_max
    pc_fear_min = settings.options_pc_fear_min
    min_premium = settings.options_min_premium_usd

    uoa_count = sum(1 for c in unusual_contracts if c.unusual_opening)
    pc_skew_unusual = aggregate_ratio is not None and (
        aggregate_ratio < pc_bullish_max or aggregate_ratio > pc_fear_min
    )
    unusual = pc_skew_unusual or uoa_count > 0 or max_vol_oi >= vol_oi_unusual

    high_opening = any(
        (c.vol_oi_ratio or 0) >= vol_oi_high and c.unusual_opening for c in unusual_contracts
    )
    institutional_grade = (
        total_premium_est >= min_premium
        and max_vol_oi >= vol_oi_high
        and (high_opening or uoa_count > 0)
    )
    conviction_band = _conviction_band_from_contracts(unusual_contracts)

    unusual_reason = None
    if institutional_grade:
        unusual_reason = (
            f"Institutional-grade flow: ${total_premium_est:,.0f} premium, "
            f"max Vol/OI {max_vol_oi:.1f}x"
        )
    elif uoa_count > 0:
        unusual_reason = f"{uoa_count} contract(s) with Vol/OI ≥ {vol_oi_unusual}"
    elif unusual and aggregate_ratio is not None:
        if aggregate_ratio > pc_fear_min:
            unusual_reason = f"Elevated put/call ratio ({aggregate_ratio:.2f}) — hedging/fear"
        elif aggregate_ratio < pc_bullish_max:
            unusual_reason = f"Low put/call ratio ({aggregate_ratio:.2f}) — bullish call skew"

    call_skew = None
    put_skew = None
    if aggregate_ratio is not None:
        if aggregate_ratio < pc_bullish_max:
            call_skew = round(pc_bullish_max - aggregate_ratio, 2)
        if aggregate_ratio > pc_fear_min:
            put_skew = round(aggregate_ratio - pc_fear_min, 2)

    short_dated_pct = None
    if total_premium_est > 0 and short_dated_premium > 0:
        short_dated_pct = round(short_dated_premium / total_premium_est * 100, 1)

    msg = None
    if aggregate_ratio is not None:
        msg = (
            f"Aggregate P/C volume ratio: {aggregate_ratio:.2f} "
            f"(puts {total_put_vol:,.0f} / calls {total_call_vol:,.0f})"
        )
        if uoa_count:
            msg += f"; {uoa_count} unusual Vol/OI contract(s)"
        if institutional_grade:
            msg += f"; institutional-grade (${total_premium_est:,.0f} premium)"

    if unusual:
        warnings.append(
            Warning(
                code="OPTIONS_UNUSUAL",
                message=msg or unusual_reason or "Unusual options activity detected.",
                severity=WarningSeverity.MEDIUM,
            )
        )

    nearest_expiry = expiry_breakdown[0].expiry if expiry_breakdown else None
    return (
        OptionsFlowFlag(
            put_call_ratio=round(aggregate_ratio, 2) if aggregate_ratio is not None else None,
            unusual=unusual,
            high_conviction=institutional_grade,
            institutional_grade=institutional_grade,
            conviction_band=conviction_band,
            premium_total_usd=round(total_premium_est, 2) if total_premium_est else None,
            message=msg,
            call_volume=total_call_vol,
            put_volume=total_put_vol,
            expiry=nearest_expiry,
            expiry_breakdown=expiry_breakdown,
            top_strikes=top_strikes,
            total_open_interest=total_oi_value,
            open_interest_available=oi_rows_seen > 0,
            unusual_reason=unusual_reason,
            unusual_contracts=unusual_contracts,
            max_vol_oi_ratio=round(max_vol_oi, 2) if max_vol_oi > 0 else None,
            otm_premium_total=round(otm_premium_total, 2) if otm_premium_total else None,
            short_dated_premium_pct=short_dated_pct,
            call_skew_score=call_skew,
            put_skew_score=put_skew,
        ),
        warnings,
    )


async def analyze_options_flow(ticker: str) -> tuple[OptionsFlowFlag, list[Warning]]:
    symbol = ticker.upper()
    if is_polygon_enabled():
        poly_result = await asyncio.to_thread(_analyze_polygon, symbol)
        if poly_result[0].put_call_ratio is not None or poly_result[0].unusual:
            return poly_result
    return await asyncio.to_thread(_analyze_sync, symbol)


def _analyze_polygon(ticker: str) -> tuple[OptionsFlowFlag, list[Warning]]:
    """Build options flow metrics from Polygon snapshot when available."""
    settings = get_settings()
    warnings: list[Warning] = []
    contracts = fetch_options_snapshot(ticker)
    if not contracts:
        return OptionsFlowFlag(message="Options data unavailable."), warnings

    total_call_vol = 0.0
    total_put_vol = 0.0
    total_premium_est = 0.0
    max_vol_oi = 0.0
    unusual_contracts: list[OptionsUnusualContract] = []

    for item in contracts[:500]:
        details = item.get("details") or {}
        day = item.get("day") or {}
        side = (details.get("contract_type") or "").lower()
        if side not in ("call", "put"):
            continue
        vol = float(day.get("volume") or 0)
        oi = float(day.get("open_interest") or 0)
        strike = float(details.get("strike_price") or 0)
        expiry = details.get("expiration_date") or ""
        last = item.get("last_quote") or {}
        price = float(last.get("midpoint") or last.get("ask") or 0)
        premium = vol * price * 100 if price > 0 else 0.0
        total_premium_est += premium
        if side == "call":
            total_call_vol += vol
        else:
            total_put_vol += vol
        vol_oi = (vol / oi) if oi > 0 else None
        if vol_oi and vol_oi > max_vol_oi:
            max_vol_oi = vol_oi
        dte = _days_to_expiry(expiry) if expiry else None
        if vol_oi and vol_oi >= settings.options_vol_oi_unusual:
            unusual_contracts.append(
                OptionsUnusualContract(
                    strike=strike,
                    side=side,
                    expiry=expiry,
                    volume=vol,
                    open_interest=oi,
                    vol_oi_ratio=round(vol_oi, 2),
                    premium_estimate=round(premium, 2) if premium else None,
                    is_otm=False,
                    days_to_expiry=dte,
                    unusual_opening=True,
                )
            )

    aggregate_ratio = (total_put_vol / total_call_vol) if total_call_vol > 0 else None
    return _build_flow_flag(
        aggregate_ratio=aggregate_ratio,
        total_call_vol=total_call_vol,
        total_put_vol=total_put_vol,
        total_premium_est=total_premium_est,
        max_vol_oi=max_vol_oi,
        unusual_contracts=unusual_contracts[:10],
        expiry_breakdown=[],
        top_strikes=[],
        total_oi_value=None,
        oi_rows_seen=0,
        otm_premium_total=None,
        short_dated_premium=0.0,
        warnings=warnings,
    )


def _analyze_sync(ticker: str) -> tuple[OptionsFlowFlag, list[Warning]]:
    settings = get_settings()
    vol_oi_unusual = settings.options_vol_oi_unusual

    warnings: list[Warning] = []
    try:
        stock = yf.Ticker(ticker)
        expirations = list(stock.options or [])
        if not expirations:
            return OptionsFlowFlag(message="No options chain data available."), warnings

        info = stock.info or {}
        spot = float(info.get("regularMarketPrice") or info.get("currentPrice") or 0)

        expiry_breakdown: list[OptionsExpiryBreakdown] = []
        all_strikes: list[OptionsStrikeVolume] = []
        unusual_contracts: list[OptionsUnusualContract] = []
        total_call_vol = 0.0
        total_put_vol = 0.0
        total_oi = 0.0
        oi_rows_seen = 0
        max_vol_oi = 0.0
        otm_premium_total = 0.0
        short_dated_premium = 0.0
        total_premium_est = 0.0

        for expiry in expirations[:_MAX_EXPIRIES]:
            chain = stock.option_chain(expiry)
            calls = chain.calls
            puts = chain.puts
            call_vol = float(calls["volume"].fillna(0).sum())
            put_vol = float(puts["volume"].fillna(0).sum())
            call_oi = float(calls["openInterest"].fillna(0).sum()) if "openInterest" in calls else 0.0
            put_oi = float(puts["openInterest"].fillna(0).sum()) if "openInterest" in puts else 0.0
            ratio = (put_vol / call_vol) if call_vol > 0 else None
            dte = _days_to_expiry(expiry)

            total_call_vol += call_vol
            total_put_vol += put_vol

            expiry_breakdown.append(
                OptionsExpiryBreakdown(
                    expiry=expiry,
                    call_volume=call_vol,
                    put_volume=put_vol,
                    put_call_ratio=round(ratio, 2) if ratio is not None else None,
                    call_oi=call_oi,
                    put_oi=put_oi,
                )
            )

            for frame, side in ((calls, "call"), (puts, "put")):
                for _, row in frame.iterrows():
                    vol = float(row.get("volume") or 0)
                    if vol <= 0 or "strike" not in row:
                        continue
                    strike = float(row["strike"])
                    oi = _strike_open_interest(row)
                    last_price = float(row.get("lastPrice") or row.get("ask") or 0)
                    premium = vol * last_price * 100 if last_price > 0 else 0.0
                    total_premium_est += premium

                    vol_oi = (vol / oi) if oi and oi > 0 else None
                    if vol_oi and vol_oi > max_vol_oi:
                        max_vol_oi = vol_oi

                    is_uoa = vol_oi is not None and vol_oi >= vol_oi_unusual
                    is_otm_flag = _is_otm(strike, spot, side)
                    if is_otm_flag and premium > 0:
                        otm_premium_total += premium
                    if dte is not None and dte <= _SHORT_DATED_DTE and premium > 0:
                        short_dated_premium += premium

                    if is_uoa or (is_otm_flag and vol >= 100):
                        unusual_contracts.append(
                            OptionsUnusualContract(
                                strike=strike,
                                side=side,
                                expiry=expiry,
                                volume=vol,
                                open_interest=oi,
                                vol_oi_ratio=round(vol_oi, 2) if vol_oi else None,
                                premium_estimate=round(premium, 2) if premium else None,
                                is_otm=is_otm_flag,
                                days_to_expiry=dte,
                                unusual_opening=is_uoa,
                            )
                        )

            for _, row in calls.nlargest(_TOP_STRIKES, "volume").iterrows():
                vol = float(row.get("volume") or 0)
                if vol > 0 and "strike" in row:
                    all_strikes.append(
                        OptionsStrikeVolume(
                            strike=float(row["strike"]),
                            side="call",
                            volume=vol,
                            open_interest=_strike_open_interest(row),
                        )
                    )
            for _, row in puts.nlargest(_TOP_STRIKES, "volume").iterrows():
                vol = float(row.get("volume") or 0)
                if vol > 0 and "strike" in row:
                    all_strikes.append(
                        OptionsStrikeVolume(
                            strike=float(row["strike"]),
                            side="put",
                            volume=vol,
                            open_interest=_strike_open_interest(row),
                        )
                    )

        oi_cap = min(len(expirations), _MAX_OI_EXPIRIES)
        for expiry in expirations[:oi_cap]:
            chain = stock.option_chain(expiry)
            for frame in (chain.calls, chain.puts):
                if "openInterest" not in frame.columns:
                    continue
                for val in frame["openInterest"].fillna(0):
                    oi = float(val)
                    if oi > 0:
                        total_oi += oi
                        oi_rows_seen += 1

        all_strikes.sort(key=lambda s: s.volume, reverse=True)
        top_strikes = all_strikes[:_TOP_STRIKES]
        unusual_contracts.sort(
            key=lambda c: (c.vol_oi_ratio or 0, c.volume),
            reverse=True,
        )
        unusual_contracts = unusual_contracts[:10]

        aggregate_ratio = (total_put_vol / total_call_vol) if total_call_vol > 0 else None
        total_oi_value = round(total_oi) if oi_rows_seen > 0 else None

        return _build_flow_flag(
            aggregate_ratio=aggregate_ratio,
            total_call_vol=total_call_vol,
            total_put_vol=total_put_vol,
            total_premium_est=total_premium_est,
            max_vol_oi=max_vol_oi,
            unusual_contracts=unusual_contracts,
            expiry_breakdown=expiry_breakdown,
            top_strikes=top_strikes,
            total_oi_value=total_oi_value,
            oi_rows_seen=oi_rows_seen,
            otm_premium_total=otm_premium_total,
            short_dated_premium=short_dated_premium,
            warnings=warnings,
        )
    except Exception:
        return OptionsFlowFlag(message="Options data unavailable."), warnings
