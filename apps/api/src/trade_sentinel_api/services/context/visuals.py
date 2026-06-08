"""Deterministic visual snapshot for AI context section cards."""

from __future__ import annotations

from trade_sentinel_api.models.schemas import (
    ContextVisualMetric,
    ContextVisualPillar,
    ContextVisualSection,
    ContextVisualSnapshot,
    ContextVisualSparkPoint,
    EarningsSnapshot,
    ForwardOutlook,
    FundamentalAssessment,
    FundamentalsSnapshot,
    InsiderSummary,
    MacroContextOverlay,
    OptionsFlowFlag,
    SecFilingsFeed,
    SectorContext,
    TechnicalAssessment,
    TickerContext,
    ValuationAssessment,
    VisualStance,
    Warning,
)

_CAUTION_FLAGS = frozenset(
    {
        "HIGH_DEBT",
        "NEGATIVE_MARGIN",
        "REVENUE_DECLINE",
        "GROWTH_DECELERATING",
        "MARGIN_CONTRACTING",
        "VALUATION_ABOVE_HISTORY",
    }
)
_FAVORABLE_FLAGS = frozenset(
    {
        "NEAR_52W_HIGH",
        "VALUATION_BELOW_HISTORY",
        "MARGIN_EXPANDING",
    }
)


def _fmt_pct(n: float | None, *, signed: bool = False, digits: int = 1) -> str:
    if n is None:
        return "—"
    sign = "+" if signed and n > 0 else ""
    return f"{sign}{n:.{digits}f}%"


def _fmt_money(n: float | None) -> str:
    if n is None:
        return "—"
    if abs(n) >= 1e9:
        return f"${n / 1e9:.2f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:.1f}M"
    return f"${n:,.0f}"


def _stance_valuation(valuation: ValuationAssessment | None) -> VisualStance:
    if not valuation or not valuation.data_available:
        return "unavailable"
    if valuation.is_fund:
        return "neutral"
    label = valuation.mos_label
    if label == "undervalued":
        return "favorable"
    if label == "overvalued":
        return "caution"
    if valuation.confidence == "low":
        return "neutral"
    return "neutral"


def _stance_fundamentals(
    fundamentals: FundamentalsSnapshot | None,
    fundamental_assessment: FundamentalAssessment | None = None,
) -> VisualStance:
    if fundamental_assessment and fundamental_assessment.data_available:
        label = fundamental_assessment.overall_label
        if label == "favorable":
            return "favorable"
        if label == "caution":
            return "caution"
        if label == "neutral":
            return "neutral"
    if not fundamentals or not fundamentals.data_available:
        return "unavailable"
    flags = set(fundamentals.fundamental_flags or [])
    if flags & _CAUTION_FLAGS:
        return "caution"
    bench = fundamentals.benchmark
    if bench and bench.debt_trend == "improving" and not flags:
        return "favorable"
    if bench and bench.debt_trend == "worsening":
        return "caution"
    if flags & _FAVORABLE_FLAGS:
        return "favorable"
    return "neutral"


def _stance_sector(sector_context: SectorContext | None) -> VisualStance:
    if not sector_context or not sector_context.data_available:
        return "unavailable"
    pe_pct = sector_context.pe_forward_sector_percentile
    if pe_pct is not None and pe_pct >= 75:
        return "caution"
    if pe_pct is not None and pe_pct <= 25:
        return "favorable"
    return "neutral"


def _stance_macro(macro_overlay: MacroContextOverlay | None) -> VisualStance:
    if not macro_overlay or not macro_overlay.has_content:
        return "unavailable"
    signals = macro_overlay.macro_signals
    if signals and signals.risk_tone == "elevated_vix":
        return "caution"
    impact = macro_overlay.impact_summary or {}
    if impact.get("high", 0) >= 2:
        return "caution"
    if impact.get("high", 0) == 0 and impact.get("moderate", 0) <= 1:
        return "favorable"
    return "neutral"


def _stance_sentiment(
    insider_summary: InsiderSummary | None,
    options_flow: OptionsFlowFlag | None,
) -> VisualStance:
    has_insider = insider_summary and insider_summary.data_available
    has_options = options_flow and (
        options_flow.put_call_ratio is not None or options_flow.unusual
    )
    if not has_insider and not has_options:
        return "unavailable"
    caution = False
    favorable = False
    if has_insider:
        if insider_summary.sentiment == "distribution":
            caution = True
        elif insider_summary.sentiment == "accumulation":
            favorable = True
    if has_options and options_flow:
        if options_flow.unusual:
            caution = True
        pc = options_flow.put_call_ratio
        if pc is not None:
            if pc < 0.8:
                favorable = True
            elif pc > 1.2:
                caution = True
    if caution and favorable:
        return "neutral"
    if caution:
        return "caution"
    if favorable:
        return "favorable"
    return "neutral"


def _stance_technical(
    *,
    rsi: float | None,
    warnings: list[Warning],
    technical_assessment: TechnicalAssessment | None = None,
) -> VisualStance:
    if technical_assessment and technical_assessment.data_available:
        ta = technical_assessment
        if ta.macd_divergence == "bearish":
            return "caution"
        if ta.trend_label == "bearish":
            return "caution"
        if ta.trend_label == "bullish" and ta.macd_divergence != "bearish":
            return "favorable"
        if ta.trend_label == "mixed":
            return "neutral"
        high_warnings = [w for w in warnings if w.severity.value == "high"]
        if high_warnings:
            return "caution"
        return "neutral"
    if rsi is None and not warnings:
        return "unavailable"
    high_warnings = [w for w in warnings if w.severity.value == "high"]
    if rsi is not None and (rsi > 70 or rsi < 30):
        return "caution"
    if high_warnings:
        return "caution"
    if rsi is not None and 40 <= rsi <= 60:
        return "favorable"
    return "neutral"


def _price_sparkline(price_history: list[dict]) -> list[ContextVisualSparkPoint]:
    points: list[ContextVisualSparkPoint] = []
    for row in price_history[-30:]:
        close = row.get("close")
        period = row.get("date", "")
        if close is not None:
            points.append(ContextVisualSparkPoint(period=str(period), value=float(close)))
    return points


def _stance_growth(
    fundamentals: FundamentalsSnapshot | None,
    fundamental_assessment: FundamentalAssessment | None = None,
) -> VisualStance:
    if fundamental_assessment and fundamental_assessment.data_available:
        g = fundamental_assessment.growth_label
        if g == "bullish":
            return "favorable"
        if g in ("bearish", "mixed"):
            return "caution"
    if not fundamentals or not fundamentals.data_available:
        return "unavailable"
    flags = set(fundamentals.fundamental_flags or [])
    if "GROWTH_DECELERATING" in flags or "REVENUE_DECLINE" in flags:
        return "caution"
    if "MARGIN_EXPANDING" in flags:
        return "favorable"
    bench = fundamentals.benchmark
    if bench and bench.eps_trend == "up":
        return "favorable"
    if bench and bench.eps_trend == "down":
        return "caution"
    return "neutral"


def _stance_balance_sheet(
    fundamentals: FundamentalsSnapshot | None,
    fundamental_assessment: FundamentalAssessment | None = None,
) -> VisualStance:
    if fundamental_assessment and fundamental_assessment.data_available:
        b = fundamental_assessment.balance_sheet_label
        if b == "bullish":
            return "favorable"
        if b == "bearish":
            return "caution"
    if not fundamentals or not fundamentals.data_available:
        return "unavailable"
    flags = set(fundamentals.fundamental_flags or [])
    if "HIGH_DEBT" in flags or "NEGATIVE_MARGIN" in flags:
        return "caution"
    bench = fundamentals.benchmark
    if bench and bench.debt_trend == "improving":
        return "favorable"
    if bench and bench.debt_trend == "worsening":
        return "caution"
    cash = fundamentals.total_cash
    debt = fundamentals.total_debt
    if cash is not None and debt is not None and cash > debt:
        return "favorable"
    return "neutral"


def _stance_catalysts(
    earnings: EarningsSnapshot | None,
    sec_filings: SecFilingsFeed | None,
) -> VisualStance:
    has_earnings = earnings and earnings.data_available
    has_filings = sec_filings and sec_filings.data_available and sec_filings.filings
    if not has_earnings and not has_filings:
        return "unavailable"
    if earnings and earnings.days_until is not None and earnings.days_until <= 7:
        return "caution"
    if earnings and earnings.surprise_pct is not None and earnings.surprise_pct > 5:
        return "favorable"
    if earnings and earnings.surprise_pct is not None and earnings.surprise_pct < -5:
        return "caution"
    return "neutral"


def _stance_forward(forward_outlook: ForwardOutlook | None) -> VisualStance:
    if not forward_outlook or not forward_outlook.data_available:
        return "unavailable"
    if forward_outlook.target_upside_pct is not None and forward_outlook.target_upside_pct > 15:
        return "favorable"
    if forward_outlook.target_upside_pct is not None and forward_outlook.target_upside_pct < -10:
        return "caution"
    return "neutral"


def _margin_sparkline(
    fundamentals: FundamentalsSnapshot | None,
) -> list[ContextVisualSparkPoint]:
    if not fundamentals or not fundamentals.income_statement_trends:
        return []
    trends = list(reversed(fundamentals.income_statement_trends))
    points: list[ContextVisualSparkPoint] = []
    for row in trends:
        if row.operating_margin_pct is not None:
            points.append(
                ContextVisualSparkPoint(period=row.period, value=row.operating_margin_pct)
            )
    return points


def _fcf_sparkline(
    fundamentals: FundamentalsSnapshot | None,
) -> list[ContextVisualSparkPoint]:
    if not fundamentals or not fundamentals.cash_flow_trends:
        return []
    trends = list(reversed(fundamentals.cash_flow_trends))
    points: list[ContextVisualSparkPoint] = []
    for row in trends:
        val = row.fcf_margin_pct
        if val is None and row.free_cash_flow is not None:
            val = row.free_cash_flow / 1e6
        if val is not None:
            points.append(ContextVisualSparkPoint(period=row.period, value=val))
    return points


def build_context_visuals(
    *,
    valuation: ValuationAssessment | None,
    fundamentals: FundamentalsSnapshot | None,
    sector_context: SectorContext | None = None,
    macro_overlay: MacroContextOverlay | None,
    earnings: EarningsSnapshot | None,
    sec_filings: SecFilingsFeed | None,
    insider_summary: InsiderSummary | None,
    options_flow: OptionsFlowFlag | None,
    forward_outlook: ForwardOutlook | None,
    market: dict,
    warnings: list[Warning],
    technical_assessment: TechnicalAssessment | None = None,
    fundamental_assessment: FundamentalAssessment | None = None,
    price_history: list[dict] | None = None,
) -> ContextVisualSnapshot:
    rsi = market.get("rsi")
    change_pct = market.get("change_pct")
    volume_ratio = market.get("volume_ratio")

    pillars = [
        ContextVisualPillar(id="valuation", label="Valuation", stance=_stance_valuation(valuation)),
        ContextVisualPillar(
            id="fundamentals", label="Fundamentals", stance=_stance_fundamentals(
                fundamentals, fundamental_assessment
            )
        ),
        ContextVisualPillar(id="macro", label="Macro", stance=_stance_macro(macro_overlay)),
        ContextVisualPillar(
            id="sentiment", label="Sentiment", stance=_stance_sentiment(insider_summary, options_flow)
        ),
        ContextVisualPillar(
            id="technical",
            label="Technical",
            stance=_stance_technical(
                rsi=rsi,
                warnings=warnings,
                technical_assessment=technical_assessment,
            ),
        ),
    ]

    val_metrics: list[ContextVisualMetric] = []
    if valuation and valuation.data_available and not valuation.is_fund:
        mos_tone: str | None = None
        if valuation.mos_label == "undervalued":
            mos_tone = "positive"
        elif valuation.mos_label == "overvalued":
            mos_tone = "negative"
        val_metrics = [
            ContextVisualMetric(
                label="Premium vs mid",
                value=_fmt_pct(valuation.mos_pct, signed=True),
                tone=mos_tone,  # type: ignore[arg-type]
            ),
            ContextVisualMetric(
                label="Fair band",
                value=(
                    f"{_fmt_money(valuation.fair_value_low)}–{_fmt_money(valuation.fair_value_high)}"
                    if valuation.fair_value_low and valuation.fair_value_high
                    else _fmt_money(valuation.fair_value_mid)
                ),
                tone="muted",
            ),
            ContextVisualMetric(
                label="Confidence",
                value=(valuation.confidence or "—").capitalize(),
                tone="muted",
            ),
        ]
        if valuation.fair_value_stress_low and valuation.fair_value_stress_high:
            val_metrics.append(
                ContextVisualMetric(
                    label="Stress band",
                    value=(
                        f"{_fmt_money(valuation.fair_value_stress_low)}–"
                        f"{_fmt_money(valuation.fair_value_stress_high)}"
                    ),
                    tone="muted",
                )
            )

    macro_metrics: list[ContextVisualMetric] = []
    if macro_overlay and macro_overlay.has_content:
        signals = macro_overlay.macro_signals
        vix_tone: str | None = None
        vix_val = "—"
        if signals:
            if signals.risk_tone == "elevated_vix":
                vix_val = "Elevated"
                vix_tone = "negative"
            elif signals.risk_tone == "normal":
                vix_val = "Normal"
                vix_tone = "positive"
            macro_metrics.append(
                ContextVisualMetric(label="VIX tone", value=vix_val, tone=vix_tone)  # type: ignore[arg-type]
            )
            if signals.yield_curve_10y_3m_bps is not None:
                macro_metrics.append(
                    ContextVisualMetric(
                        label="10Y–3M",
                        value=f"{signals.yield_curve_10y_3m_bps} bps",
                        tone="muted",
                    )
                )
            if signals.signals:
                top = signals.signals[0]
                macro_metrics.append(
                    ContextVisualMetric(
                        label=top.label,
                        value=_fmt_pct(top.change_1d_pct, signed=True),
                        tone="neutral",
                    )
                )

    growth_metrics: list[ContextVisualMetric] = []
    if fundamentals and fundamentals.data_available:
        rev_yoy = None
        if fundamentals.quarterly_trends:
            rev_yoy = fundamentals.quarterly_trends[0].revenue_yoy_pct
        op_margin = None
        if fundamentals.income_statement_trends:
            op_margin = fundamentals.income_statement_trends[0].operating_margin_pct
        bench = fundamentals.benchmark
        eps_trend = bench.eps_trend if bench else None
        pe_hist_pct = bench.pe_current_percentile if bench else None
        growth_metrics = [
            ContextVisualMetric(
                label="Rev YoY",
                value=_fmt_pct(rev_yoy, signed=True) if rev_yoy is not None else "—",
                tone="positive" if rev_yoy and rev_yoy > 10 else "neutral",
            ),
            ContextVisualMetric(
                label="Op margin",
                value=_fmt_pct(op_margin) if op_margin is not None else "—",
                tone="muted",
            ),
            ContextVisualMetric(
                label="EPS trend",
                value=(eps_trend or "—").capitalize(),
                tone="positive" if eps_trend == "up" else ("negative" if eps_trend == "down" else "muted"),
            ),
        ]
        if pe_hist_pct is not None:
            growth_metrics.append(
                ContextVisualMetric(
                    label="P/E vs 3Y",
                    value=f"{pe_hist_pct:.0f}th pctile",
                    tone="negative" if pe_hist_pct >= 75 else ("positive" if pe_hist_pct <= 25 else "muted"),
                )
            )

    sector_metrics: list[ContextVisualMetric] = []
    if sector_context and sector_context.data_available:
        if sector_context.pe_forward_sector_percentile is not None:
            pct = sector_context.pe_forward_sector_percentile
            sector_metrics.append(
                ContextVisualMetric(
                    label="Sector P/E rank",
                    value=f"{pct:.0f}th pctile",
                    tone="negative" if pct >= 75 else ("positive" if pct <= 25 else "neutral"),
                )
            )
        if sector_context.pe_vs_sector_prior_pct is not None:
            prior = sector_context.pe_vs_sector_prior_pct
            sector_metrics.append(
                ContextVisualMetric(
                    label="vs sector prior",
                    value=_fmt_pct(prior, signed=True),
                    tone="negative" if prior > 15 else ("positive" if prior < -10 else "muted"),
                )
            )
        if sector_context.peer_count:
            sector_metrics.append(
                ContextVisualMetric(
                    label="Peers",
                    value=str(sector_context.peer_count),
                    tone="muted",
                )
            )

    balance_metrics: list[ContextVisualMetric] = []
    if fundamentals and fundamentals.data_available:
        net = None
        if fundamentals.total_cash is not None and fundamentals.total_debt is not None:
            net = fundamentals.total_cash - fundamentals.total_debt
        fcf = fundamentals.free_cash_flow
        balance_metrics = [
            ContextVisualMetric(
                label="Net cash",
                value=_fmt_money(net),
                tone="positive" if net and net > 0 else ("negative" if net and net < 0 else "muted"),
            ),
            ContextVisualMetric(
                label="D/E",
                value=f"{fundamentals.debt_to_equity:.2f}"
                if fundamentals.debt_to_equity is not None
                else "—",
                tone="muted",
            ),
            ContextVisualMetric(
                label="FCF (TTM)",
                value=_fmt_money(fcf),
                tone="positive" if fcf and fcf > 0 else ("negative" if fcf and fcf < 0 else "muted"),
            ),
        ]

    catalyst_metrics: list[ContextVisualMetric] = []
    if earnings and earnings.data_available:
        days = earnings.days_until
        catalyst_metrics.append(
            ContextVisualMetric(
                label="Earnings",
                value=f"{days}d" if days is not None else "—",
                tone="negative" if days is not None and days <= 7 else "muted",
            )
        )
        catalyst_metrics.append(
            ContextVisualMetric(
                label="Last EPS surprise",
                value=_fmt_pct(earnings.surprise_pct, signed=True)
                if earnings.surprise_pct is not None
                else "—",
                tone="positive"
                if earnings.surprise_pct and earnings.surprise_pct > 0
                else "neutral",
            )
        )
    if sec_filings and sec_filings.filings:
        latest = sec_filings.filings[0]
        catalyst_metrics.append(
            ContextVisualMetric(label="Latest filing", value=latest.form, tone="muted")
        )

    insider_metrics: list[ContextVisualMetric] = []
    if insider_summary and insider_summary.data_available:
        insider_metrics.append(
            ContextVisualMetric(
                label="Insider tone",
                value=insider_summary.sentiment.capitalize(),
                tone="positive"
                if insider_summary.sentiment == "accumulation"
                else ("negative" if insider_summary.sentiment == "distribution" else "neutral"),
            )
        )
        insider_metrics.append(
            ContextVisualMetric(
                label="Buys / sells",
                value=f"{insider_summary.buy_count} / {insider_summary.sell_count}",
                tone="muted",
            )
        )
    if options_flow and options_flow.put_call_ratio is not None:
        pc = options_flow.put_call_ratio
        insider_metrics.append(
            ContextVisualMetric(
                label="P/C ratio",
                value=f"{pc:.2f}",
                tone="positive" if pc < 0.9 else ("negative" if pc > 1.1 else "neutral"),
            )
        )
    if options_flow and options_flow.unusual:
        insider_metrics.append(
            ContextVisualMetric(label="Options", value="Unusual activity", tone="negative")
        )

    technical_metrics: list[ContextVisualMetric] = []
    if technical_assessment and technical_assessment.data_available:
        ta = technical_assessment
        trend_val = (ta.trend_label or "—").capitalize()
        trend_tone: str | None = "positive" if ta.trend_label == "bullish" else (
            "negative" if ta.trend_label == "bearish" else "neutral"
        )
        technical_metrics.append(
            ContextVisualMetric(label="Trend", value=trend_val, tone=trend_tone)  # type: ignore[arg-type]
        )
        if ta.short_term_trend:
            technical_metrics.append(
                ContextVisualMetric(
                    label="Short",
                    value=ta.short_term_trend.capitalize(),
                    tone="positive" if ta.short_term_trend == "bullish" else (
                        "negative" if ta.short_term_trend == "bearish" else "neutral"
                    ),
                )
            )
        if ta.mid_term_trend:
            technical_metrics.append(
                ContextVisualMetric(
                    label="Mid",
                    value=ta.mid_term_trend.capitalize(),
                    tone="positive" if ta.mid_term_trend == "bullish" else (
                        "negative" if ta.mid_term_trend == "bearish" else "neutral"
                    ),
                )
            )
        if ta.long_term_trend:
            technical_metrics.append(
                ContextVisualMetric(
                    label="Long",
                    value=ta.long_term_trend.capitalize(),
                    tone="positive" if ta.long_term_trend == "bullish" else (
                        "negative" if ta.long_term_trend == "bearish" else "neutral"
                    ),
                )
            )
        rsi_val = ta.rsi_14 if ta.rsi_14 is not None else rsi
        technical_metrics.append(
            ContextVisualMetric(
                label="RSI",
                value=f"{rsi_val:.1f}" if rsi_val is not None else "—",
                tone="negative" if rsi_val and (rsi_val > 70 or rsi_val < 30) else "neutral",
            )
        )
        hist = ta.macd.histogram if ta.macd else None
        technical_metrics.append(
            ContextVisualMetric(
                label="MACD hist",
                value=f"{hist:.2f}" if hist is not None else "—",
                tone="positive" if hist and hist > 0 else ("negative" if hist and hist < 0 else "muted"),
            )
        )
        technical_metrics.append(
            ContextVisualMetric(
                label="52W range",
                value=f"{ta.range_position_pct:.0f}%" if ta.range_position_pct is not None else "—",
                tone="muted",
            )
        )
        technical_metrics.append(
            ContextVisualMetric(
                label="ATR %",
                value=_fmt_pct(ta.atr_pct) if ta.atr_pct is not None else "—",
                tone="muted",
            )
        )
    else:
        technical_metrics = [
            ContextVisualMetric(
                label="RSI",
                value=f"{rsi:.1f}" if rsi is not None else "—",
                tone="negative" if rsi and (rsi > 70 or rsi < 30) else "neutral",
            ),
            ContextVisualMetric(
                label="Vol ratio",
                value=f"{volume_ratio:.2f}x" if volume_ratio is not None else "—",
                tone="muted",
            ),
            ContextVisualMetric(
                label="Chg %",
                value=_fmt_pct(change_pct, signed=True) if change_pct is not None else "—",
                tone="positive"
                if change_pct and change_pct > 0
                else ("negative" if change_pct and change_pct < 0 else "neutral"),
            ),
        ]

    tech_sparkline = _price_sparkline(price_history or [])

    forward_metrics: list[ContextVisualMetric] = []
    if forward_outlook and forward_outlook.data_available:
        for item in forward_outlook.watch_items[:2]:
            forward_metrics.append(
                ContextVisualMetric(
                    label="Watch",
                    value=item[:48] + ("…" if len(item) > 48 else ""),
                    tone="muted",
                )
            )

    sections = [
        ContextVisualSection(
            id="valuation",
            title="Valuation",
            stance=_stance_valuation(valuation),
            metrics=val_metrics,
        ),
        ContextVisualSection(
            id="macro",
            title="Macro",
            stance=_stance_macro(macro_overlay),
            metrics=macro_metrics,
        ),
        ContextVisualSection(
            id="sector",
            title="Sector",
            stance=_stance_sector(sector_context),
            metrics=sector_metrics,
        ),
        ContextVisualSection(
            id="growth",
            title="Growth & profitability",
            stance=_stance_growth(fundamentals, fundamental_assessment),
            metrics=growth_metrics,
            sparkline=_margin_sparkline(fundamentals),
        ),
        ContextVisualSection(
            id="balance_sheet",
            title="Balance sheet & cash flow",
            stance=_stance_balance_sheet(fundamentals, fundamental_assessment),
            metrics=balance_metrics,
            sparkline=_fcf_sparkline(fundamentals),
        ),
        ContextVisualSection(
            id="catalysts",
            title="Catalysts",
            stance=_stance_catalysts(earnings, sec_filings),
            metrics=catalyst_metrics,
        ),
        ContextVisualSection(
            id="insider_options",
            title="Insider / options",
            stance=_stance_sentiment(insider_summary, options_flow),
            metrics=insider_metrics,
        ),
        ContextVisualSection(
            id="technical",
            title="Technical",
            stance=_stance_technical(
                rsi=rsi,
                warnings=warnings,
                technical_assessment=technical_assessment,
            ),
            metrics=technical_metrics,
            sparkline=tech_sparkline if len(tech_sparkline) >= 2 else [],
        ),
        ContextVisualSection(
            id="forward",
            title="Forward outlook",
            stance=_stance_forward(forward_outlook),
            metrics=forward_metrics,
        ),
    ]

    return ContextVisualSnapshot(pillars=pillars, sections=sections)


def attach_context_visuals(ctx: TickerContext) -> TickerContext:
    """Recompute visuals from current context fields (safe for cached payloads)."""
    visuals = build_context_visuals(
        valuation=ctx.valuation,
        fundamentals=ctx.fundamentals,
        sector_context=ctx.sector_context,
        macro_overlay=ctx.macro_overlay,
        earnings=ctx.earnings,
        sec_filings=ctx.sec_filings,
        insider_summary=ctx.insider_summary,
        options_flow=ctx.options_flow,
        forward_outlook=ctx.forward_outlook,
        market={
            "rsi": ctx.rsi,
            "change_pct": ctx.change_pct,
            "volume_ratio": ctx.volume_ratio,
        },
        warnings=ctx.warnings,
        technical_assessment=ctx.technical_assessment,
        fundamental_assessment=ctx.fundamental_assessment,
        price_history=ctx.price_history,
    )
    return ctx.model_copy(update={"context_visuals": visuals})
