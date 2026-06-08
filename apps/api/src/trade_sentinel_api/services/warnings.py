from trade_sentinel_api.models.schemas import (
    EarningsSnapshot,
    FundamentalsSnapshot,
    MacdSnapshot,
    TechnicalAssessment,
    ValuationAssessment,
    Warning,
    WarningSeverity,
)


def build_technical_warnings(
    rsi: float | None,
    volume_ratio: float | None,
    macd: MacdSnapshot | None = None,
    *,
    technical_assessment: TechnicalAssessment | None = None,
) -> list[Warning]:
    warnings: list[Warning] = []
    if rsi is not None:
        if rsi > 70:
            warnings.append(
                Warning(
                    code="RSI_OVERBOUGHT",
                    message=f"RSI is {rsi:.1f} (overbought > 70). Price may be extended.",
                    severity=WarningSeverity.HIGH,
                )
            )
        elif rsi < 30:
            warnings.append(
                Warning(
                    code="RSI_OVERSOLD",
                    message=f"RSI is {rsi:.1f} (oversold < 30). Potential bounce or continued weakness.",
                    severity=WarningSeverity.MEDIUM,
                )
            )
    if volume_ratio is not None:
        if volume_ratio > 2.0:
            warnings.append(
                Warning(
                    code="VOLUME_SPIKE",
                    message=f"Volume is {volume_ratio:.1f}x the 30-day average — elevated activity.",
                    severity=WarningSeverity.MEDIUM,
                )
            )
        elif volume_ratio < 0.5:
            warnings.append(
                Warning(
                    code="VOLUME_LOW",
                    message=f"Volume is only {volume_ratio:.1f}x the 30-day average — thin liquidity.",
                    severity=WarningSeverity.LOW,
                )
            )
    if macd and macd.macd is not None and macd.signal is not None:
        hist = macd.histogram if macd.histogram is not None else (macd.macd - macd.signal)
        if macd.macd < macd.signal and hist < 0:
            warnings.append(
                Warning(
                    code="MACD_BEARISH",
                    message=(
                        f"MACD ({macd.macd:.2f}) below signal ({macd.signal:.2f}) "
                        f"— bearish momentum."
                    ),
                    severity=WarningSeverity.MEDIUM,
                )
            )
        elif macd.macd > macd.signal and hist > 0:
            warnings.append(
                Warning(
                    code="MACD_BULLISH",
                    message=(
                        f"MACD ({macd.macd:.2f}) above signal ({macd.signal:.2f}) "
                        f"— bullish momentum."
                    ),
                    severity=WarningSeverity.LOW,
                )
            )

    if technical_assessment and technical_assessment.data_available:
        ta = technical_assessment
        if ta.macd_divergence == "bullish":
            warnings.append(
                Warning(
                    code="MACD_BULLISH_DIVERGENCE",
                    message="Bullish MACD divergence — price lower low vs MACD higher low.",
                    severity=WarningSeverity.MEDIUM,
                )
            )
        elif ta.macd_divergence == "bearish":
            warnings.append(
                Warning(
                    code="MACD_BEARISH_DIVERGENCE",
                    message="Bearish MACD divergence — price higher high vs MACD lower high.",
                    severity=WarningSeverity.MEDIUM,
                )
            )
        if ta.price_vs_sma_50_pct is not None:
            if ta.price_vs_sma_50_pct < -2:
                warnings.append(
                    Warning(
                        code="BELOW_SMA50",
                        message=(
                            f"Price is {abs(ta.price_vs_sma_50_pct):.1f}% below SMA50 "
                            f"(${ta.sma_50:.2f})."
                            if ta.sma_50
                            else f"Price is {abs(ta.price_vs_sma_50_pct):.1f}% below SMA50."
                        ),
                        severity=WarningSeverity.MEDIUM,
                    )
                )
            elif ta.price_vs_sma_50_pct > 2:
                warnings.append(
                    Warning(
                        code="ABOVE_SMA50",
                        message=(
                            f"Price is {ta.price_vs_sma_50_pct:.1f}% above SMA50 "
                            f"(${ta.sma_50:.2f})."
                            if ta.sma_50
                            else f"Price is {ta.price_vs_sma_50_pct:.1f}% above SMA50."
                        ),
                        severity=WarningSeverity.LOW,
                    )
                )
        if ta.range_position_pct is not None:
            if ta.range_position_pct > 90:
                warnings.append(
                    Warning(
                        code="NEAR_52W_HIGH",
                        message=(
                            f"Price near 52-week high ({ta.range_position_pct:.0f}% of range) "
                            "— limited upside cushion in the tape."
                        ),
                        severity=WarningSeverity.MEDIUM,
                    )
                )
            elif ta.range_position_pct < 10:
                warnings.append(
                    Warning(
                        code="NEAR_52W_LOW",
                        message=(
                            f"Price near 52-week low ({ta.range_position_pct:.0f}% of range) "
                            "— potential value or continued weakness."
                        ),
                        severity=WarningSeverity.MEDIUM,
                    )
                )

    return warnings


def build_fundamental_warnings(
    fundamentals: FundamentalsSnapshot | None,
    earnings: EarningsSnapshot | None = None,
    valuation: ValuationAssessment | None = None,
) -> list[Warning]:
    warnings: list[Warning] = []
    if not fundamentals or not fundamentals.data_available:
        return warnings

    if fundamentals.pe_forward is not None and fundamentals.pe_forward > 50:
        warnings.append(
            Warning(
                code="HIGH_VALUATION",
                message=f"Forward P/E is {fundamentals.pe_forward:.1f} — elevated vs typical ranges.",
                severity=WarningSeverity.MEDIUM,
            )
        )

    if fundamentals.debt_to_equity is not None and fundamentals.debt_to_equity > 200:
        warnings.append(
            Warning(
                code="ELEVATED_DEBT",
                message=f"Debt-to-equity is {fundamentals.debt_to_equity:.0f}% — balance sheet leverage is high.",
                severity=WarningSeverity.HIGH,
            )
        )

    if "REVENUE_DECLINE" in fundamentals.fundamental_flags:
        warnings.append(
            Warning(
                code="REVENUE_DECLINING",
                message="Revenue declined for two consecutive quarters (QoQ).",
                severity=WarningSeverity.MEDIUM,
            )
        )

    if earnings and earnings.days_until is not None and 0 <= earnings.days_until <= 7:
        warnings.append(
            Warning(
                code="EARNINGS_DATE_SOON",
                message=f"Earnings report in {earnings.days_until} day(s) — elevated event risk.",
                severity=WarningSeverity.MEDIUM,
            )
        )

    flag_messages = {
        "VALUATION_ABOVE_HISTORY": (
            "VALUATION_ABOVE_HISTORY",
            "Forward valuation is materially above the company's 3-year median.",
            WarningSeverity.MEDIUM,
        ),
        "MARGIN_CONTRACTING": (
            "MARGIN_CONTRACTING",
            "Operating margin is below the 3-year average.",
            WarningSeverity.MEDIUM,
        ),
        "GROWTH_DECELERATING": (
            "GROWTH_DECELERATING",
            "Revenue growth is decelerating vs recent YoY trends.",
            WarningSeverity.MEDIUM,
        ),
        "NEGATIVE_MARGIN": (
            "NEGATIVE_MARGIN",
            "Company reports negative profit margins.",
            WarningSeverity.HIGH,
        ),
        "HIGH_DEBT": (
            "HIGH_DEBT",
            "Debt-to-equity exceeds 200%.",
            WarningSeverity.HIGH,
        ),
    }
    for flag in fundamentals.fundamental_flags:
        if flag in flag_messages:
            code, msg, sev = flag_messages[flag]
            if not any(w.code == code for w in warnings):
                warnings.append(Warning(code=code, message=msg, severity=sev))

    if valuation and valuation.data_available and not valuation.is_fund:
        if valuation.mos_label == "overvalued" and valuation.mos_pct is not None:
            warnings.append(
                Warning(
                    code="PRICE_ABOVE_FAIR_VALUE",
                    message=(
                        f"Price is ~{valuation.mos_pct:.0f}% above model fair-value mid "
                        f"(${valuation.fair_value_mid:.2f})."
                        if valuation.fair_value_mid
                        else "Price is above model fair-value mid."
                    ),
                    severity=WarningSeverity.MEDIUM,
                )
            )
        elif valuation.mos_label == "undervalued" and valuation.mos_pct is not None:
            warnings.append(
                Warning(
                    code="MOS_POSITIVE",
                    message=(
                        f"Price is ~{abs(valuation.mos_pct):.0f}% below model fair-value mid "
                        f"(${valuation.fair_value_mid:.2f})."
                        if valuation.fair_value_mid
                        else "Price is below model fair-value mid."
                    ),
                    severity=WarningSeverity.LOW,
                )
            )
        if valuation.confidence == "low":
            warnings.append(
                Warning(
                    code="VALUATION_LOW_CONFIDENCE",
                    message="Fair-value band based on limited methods — treat as indicative only.",
                    severity=WarningSeverity.LOW,
                )
            )

    return warnings
