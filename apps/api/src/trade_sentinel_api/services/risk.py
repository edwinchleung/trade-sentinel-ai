import asyncio

import yfinance as yf

from trade_sentinel_api.models.schemas import (
    RiskEvaluateRequest,
    RiskEvaluateResponse,
    Warning,
    WarningSeverity,
)
from trade_sentinel_api.services.technicals import compute_atr

LEVERAGED_ETFS = {
    "TQQQ", "SQQQ", "UPRO", "SPXU", "TNA", "TZA", "LABU", "LABD",
    "FNGU", "FNGD", "SOXL", "SOXS", "TECL", "TECS",
}


def _detect_leveraged_etf(ticker: str) -> bool:
    return ticker.upper() in LEVERAGED_ETFS


async def _fetch_atr(ticker: str) -> float | None:
    def _sync():
        hist = yf.Ticker(ticker.upper()).history(period="3mo", interval="1d")
        if hist.empty or len(hist) < 15:
            return None
        return compute_atr(hist["High"], hist["Low"], hist["Close"])

    return await asyncio.to_thread(_sync)


async def evaluate_risk(req: RiskEvaluateRequest) -> RiskEvaluateResponse:
    position_value = req.quantity * req.entry_price
    portfolio_pct = (position_value / req.account_size) * 100
    exceeds = portfolio_pct > 2.0
    suggested_size = None
    if exceeds:
        suggested_size = round((req.account_size * 0.02) / req.entry_price, 2)

    atr = await _fetch_atr(req.ticker)
    stop = None
    if atr and req.direction == "long":
        stop = round(req.entry_price - 2 * atr, 2)
    elif atr and req.direction == "short":
        stop = round(req.entry_price + 2 * atr, 2)

    warnings: list[Warning] = []
    if exceeds:
        warnings.append(
            Warning(
                code="POSITION_SIZE_HIGH",
                message=f"Position is {portfolio_pct:.1f}% of account (limit 2%).",
                severity=WarningSeverity.HIGH,
            )
        )

    derivative_note = None
    symbol = req.ticker.upper()
    if req.instrument_type == "option":
        days = req.holding_days or 7
        derivative_note = (
            f"Options carry theta decay — estimated time decay accelerates into expiration. "
            f"Planned hold ~{days} days: IV crush and theta can erode premium quickly."
        )
        warnings.append(
            Warning(
                code="OPTION_THETA",
                message="Options are decaying assets; verify implied volatility and expiration.",
                severity=WarningSeverity.HIGH,
            )
        )
    elif req.instrument_type == "leveraged_etf" or _detect_leveraged_etf(symbol):
        derivative_note = (
            "Leveraged ETFs rebalance daily and suffer volatility decay (beta slippage) "
            "when held beyond short-term trades. Not suitable for long-term holds."
        )
        warnings.append(
            Warning(
                code="LEVERAGED_ETF",
                message="3x/leveraged ETF detected — beta slippage and path dependency risk.",
                severity=WarningSeverity.HIGH,
            )
        )

    return RiskEvaluateResponse(
        ticker=symbol,
        position_value=round(position_value, 2),
        portfolio_pct=round(portfolio_pct, 2),
        exceeds_risk_limit=exceeds,
        suggested_stop_loss=stop,
        suggested_position_size=suggested_size,
        atr=round(atr, 4) if atr else None,
        warnings=warnings,
        derivative_note=derivative_note,
    )
