"""Context fact assembly for LLM prompts."""

from __future__ import annotations

from trade_sentinel_api.models.schemas import (
    FundamentalBenchmark,
    FundamentalsSnapshot,
    MacroContextOverlay,
    ValuationAssessment,
    Warning,
)
from trade_sentinel_api.services.macro.context import macro_context_facts
from trade_sentinel_api.services.valuation import build_valuation_summary


def _macd_histogram(market: dict) -> float | None:
    macd = market.get("macd")
    if macd is None:
        return None
    if hasattr(macd, "histogram"):
        return macd.histogram
    if isinstance(macd, dict):
        return macd.get("histogram")
    return None


def _normalize_growth_rate(val: float | None) -> float | None:
    if val is None:
        return None
    if abs(val) > 1.5:
        return val / 100
    return val


_FLAG_NARRATIVES: dict[str, str] = {
    "HIGH_DEBT": "Debt-to-equity exceeds 200% — balance sheet leverage is elevated.",
    "NEGATIVE_MARGIN": "Company reports negative profit margins.",
    "REVENUE_DECLINE": "Revenue declined for two consecutive quarters (QoQ).",
    "NEAR_52W_HIGH": "Price is near the 52-week high — limited upside cushion in the tape.",
    "VALUATION_ABOVE_HISTORY": "Forward valuation is materially above the company's 3-year median.",
    "VALUATION_BELOW_HISTORY": "Forward valuation sits below the company's 3-year median.",
    "MARGIN_EXPANDING": "Operating margin is above the 3-year average.",
    "MARGIN_CONTRACTING": "Operating margin is below the 3-year average.",
    "GROWTH_DECELERATING": "Revenue growth is decelerating vs recent YoY trends.",
}


def _build_qualitative_hints(
    *,
    fundamentals: FundamentalsSnapshot | None,
    news: list,
    sec_filings,
    insider_summary,
    forward_outlook: ForwardOutlook | None,
    warnings: list[Warning],
    fundamental_warnings: list[Warning] | None,
    institutional_13f=None,
    activist_filing=None,
) -> list[str]:
    """Deterministic business-story anchors for qualitative_analysis (max 5)."""
    hints: list[str] = []

    if fundamentals:
        parts = [p for p in (fundamentals.sector, fundamentals.industry) if p]
        if parts:
            hints.append(f"Business context: {' / '.join(parts)}.")
        if fundamentals.valuation_label or fundamentals.recommendation:
            label = fundamentals.valuation_label or "unknown"
            rec = fundamentals.recommendation or "no consensus label"
            hints.append(
                f"Market framing: {label} valuation label with consensus recommendation '{rec}'."
            )
        for flag in fundamentals.fundamental_flags:
            narrative = _FLAG_NARRATIVES.get(flag)
            if narrative and narrative not in hints:
                hints.append(narrative)

    for item in news[:2]:
        title = item.title if hasattr(item, "title") else item.get("title")
        if title:
            hint = f"Recent headline theme: {title}"
            if hasattr(item, "sentiment_label") and item.sentiment_label:
                hint += f" ({item.sentiment_label})"
            hints.append(hint)

    if sec_filings and sec_filings.data_available and sec_filings.filings:
        f0 = sec_filings.filings[0]
        if f0.event_items:
            hints.append(
                f"Latest filing ({f0.form}): Items {', '.join(f0.event_items[:3])}"
            )
        elif f0.excerpt_available and f0.excerpt:
            snippet = f0.excerpt.split("\n")[0][:160].strip()
            if snippet:
                hints.append(f"Latest filing ({f0.form}): {snippet}")
        elif f0.title:
            hints.append(f"Latest SEC filing: {f0.form} — {f0.title}")

    if insider_summary and insider_summary.data_available:
        hints.append(
            f"Insider tone (90d): {insider_summary.sentiment} "
            f"({insider_summary.buy_count} buys / {insider_summary.sell_count} sells)."
        )

    if institutional_13f and institutional_13f.data_available and institutional_13f.changes:
        for ch in institutional_13f.changes[:2]:
            pct = (
                f" ({ch.pct_change:+.0f}% QoQ)"
                if ch.pct_change is not None
                else ""
            )
            hints.append(f"13F: {ch.filer_name} {ch.change_type}{pct}.")

    if activist_filing:
        pct = (
            f" at {activist_filing.percent_owned:.1f}%"
            if activist_filing.percent_owned is not None
            else ""
        )
        filer = activist_filing.filer_name or "Unknown filer"
        hints.append(f"Activist 13D ({activist_filing.filing_date}): {filer}{pct}.")

    if forward_outlook and forward_outlook.watch_items:
        for item in forward_outlook.watch_items[:2]:
            hints.append(f"Near-term watch: {item}")

    for w in (fundamental_warnings or []) + warnings:
        if w.message and w.message not in hints:
            hints.append(w.message)
            if len(hints) >= 5:
                break

    return hints[:5]


def _build_synthesis_hints(
    *,
    fundamentals: FundamentalsSnapshot | None,
    valuation: ValuationAssessment | None,
    warnings: list[Warning],
    macro_overlay: MacroContextOverlay | None,
    market: dict,
    forward_outlook: ForwardOutlook | None,
    technical_assessment=None,
    fundamental_assessment=None,
    news_digest=None,
    sector_context: SectorContext | None = None,
    insider_summary=None,
    institutional_13f=None,
    activist_filing=None,
    options_flow=None,
) -> list[str]:
    """Deterministic interpretation anchors for the LLM (max 6)."""
    hints: list[str] = []

    if valuation and valuation.data_available and not valuation.is_fund:
        upside = fundamentals.target_upside_pct if fundamentals else None
        if valuation.mos_label == "overvalued" and upside is not None and upside > 15:
            hints.append(
                "Model fair mid implies rich vs current price, but consensus target "
                "implies further upside — valuation methods disagree."
            )
        if valuation.confidence == "low" or (
            valuation.method_spread_pct is not None and valuation.method_spread_pct > 150
        ):
            hints.append(
                "Fair-value methods span a wide range; treat the headline band as low confidence."
            )
        flags = fundamentals.fundamental_flags if fundamentals else []
        if (
            valuation.mos_label == "overvalued"
            and flags
            and "VALUATION_BELOW_HISTORY" in flags
        ):
            hints.append(
                "Forward P/E is below own 3Y median while price sits above model fair mid "
                "— mixed valuation signals."
            )

    if sector_context and sector_context.data_available:
        if sector_context.sector_headline:
            hints.append(sector_context.sector_headline)
        for bullet in sector_context.sector_bullets[:2]:
            hints.append(bullet)

    if fundamentals and fundamentals.benchmark:
        bench = fundamentals.benchmark
        if bench.pe_current_percentile is not None:
            hints.append(
                f"Forward/trailing P/E at ~{bench.pe_current_percentile:.0f}th percentile "
                "of own 3Y TTM history."
            )
        if (
            bench.debt_trend == "improving"
            and fundamentals.total_cash
            and fundamentals.total_debt
            and fundamentals.total_cash > fundamentals.total_debt
        ):
            hints.append(
                "Balance sheet is de-risking with net cash — strong liquidity supports "
                "operations and capital returns."
            )

    if fundamentals:
        trends = fundamentals.balance_sheet_trends
        if len(trends) >= 2:
            latest = trends[0].net_debt
            prior = trends[-1].net_debt
            if latest is not None and prior is not None and latest < prior:
                hints.append(
                    "Net debt has declined across recent quarters — leverage improving."
                )

        income_trends = fundamentals.income_statement_trends
        if len(income_trends) >= 2:
            latest_margin = income_trends[0].operating_margin_pct
            oldest_margin = income_trends[-1].operating_margin_pct
            if (
                latest_margin is not None
                and oldest_margin is not None
                and latest_margin - oldest_margin >= 2
            ):
                hints.append(
                    "Operating margin has expanded across recent quarters — "
                    "profitability improving vs own recent history."
                )

        cf_trends = fundamentals.cash_flow_trends
        if len(cf_trends) >= 2:
            latest_fcf = cf_trends[0].free_cash_flow
            prior_fcf = cf_trends[1].free_cash_flow
            rev_yoy = None
            if fundamentals.quarterly_trends:
                rev_yoy = fundamentals.quarterly_trends[0].revenue_yoy_pct
            if (
                latest_fcf is not None
                and prior_fcf is not None
                and latest_fcf < prior_fcf
                and rev_yoy is not None
                and rev_yoy > 10
            ):
                hints.append(
                    "Free cash flow has compressed despite strong revenue growth — "
                    "check capex intensity and cash conversion."
                )

        if cf_trends:
            latest_cf = cf_trends[0]
            if (
                latest_cf.operating_cash_flow is not None
                and latest_cf.operating_cash_flow > 0
                and latest_cf.free_cash_flow is not None
                and latest_cf.free_cash_flow < 0
            ):
                hints.append(
                    "Operating cash flow is positive but free cash flow is negative — "
                    "heavy capex is absorbing cash despite earnings quality."
                )

    rev_growth = _normalize_growth_rate(
        fundamentals.revenue_growth if fundamentals else None
    )
    hist = _macd_histogram(market)
    if hist is not None and hist < 0 and rev_growth is not None and rev_growth > 0.2:
        hints.append(
            "Short-term technical weakness (bearish MACD) contrasts with strong "
            "fundamental revenue growth — distinguish time horizons."
        )

    sector = (fundamentals.sector or "") if fundamentals else ""
    if macro_overlay and macro_overlay.has_content and sector:
        signals = macro_overlay.macro_signals
        if signals:
            for sig in signals.signals:
                label = (sig.label or sig.symbol or "").upper()
                if "WTI" in label or "CRUDE" in label or sig.symbol in ("CL=F", "USO"):
                    if sig.change_5d_pct is not None and sig.change_5d_pct > 5:
                        if "tech" in sector.lower() or "semiconductor" in sector.lower():
                            hints.append(
                                "Oil has rallied sharply; energy costs and risk-off sentiment "
                                "can pressure tech multiples even when company fundamentals are strong."
                            )
                            break

    if forward_outlook and forward_outlook.data_available and forward_outlook.watch_items:
        if len(forward_outlook.watch_items) >= 2:
            hints.append(
                "Multiple near-term watch items (earnings, macro, filings) could shift "
                "the narrative — prioritize forward_outlook.watch_items."
            )

    if any(w.code == "PRICE_ABOVE_FAIR_VALUE" for w in warnings):
        if not any("fair mid" in h.lower() for h in hints):
            hints.append(
                "Price sits above the app's model fair-value mid — premium vs deterministic band."
            )

    if technical_assessment and technical_assessment.data_available:
        ta = technical_assessment
        if valuation and valuation.data_available and valuation.mos_label:
            if ta.trend_label == "bearish" and valuation.mos_label == "undervalued":
                hints.append(
                    "Bearish technical trend contrasts with undervalued model band — "
                    "momentum may lag fundamental value."
                )
            elif ta.trend_label == "bullish" and valuation.mos_label == "overvalued":
                hints.append(
                    "Bullish technical momentum vs overvalued model band — "
                    "tape may run ahead of deterministic fair value."
                )
        if ta.macd_divergence == "bearish":
            hints.append(
                "Bearish MACD divergence suggests waning momentum despite recent price action."
            )
        elif ta.macd_divergence == "bullish":
            hints.append(
                "Bullish MACD divergence suggests momentum may be stabilizing despite weak tape."
            )
        if ta.range_position_pct is not None and ta.range_position_pct > 90:
            if valuation and valuation.mos_label == "overvalued":
                hints.append(
                    "Price near 52-week high while model band flags overvaluation — "
                    "extended tape with rich fundamentals."
                )
        if ta.horizon_summary:
            hints.append(f"Horizon trends: {ta.horizon_summary}.")

    if news_digest and news_digest.data_available and news_digest.summary_line:
        hints.append(news_digest.summary_line)

    if fundamental_assessment and fundamental_assessment.data_available:
        if fundamental_assessment.summary:
            hints.append(fundamental_assessment.summary)

    if (
        insider_summary
        and insider_summary.data_available
        and insider_summary.sentiment == "distribution"
        and activist_filing
    ):
        hints.append(
            "Insider distribution contrasts with a recent activist 13D stake — "
            "management selling vs external pressure for change."
        )

    if (
        institutional_13f
        and institutional_13f.crowding_risk == "high"
        and options_flow
        and options_flow.unusual
    ):
        hints.append(
            "High 13F ownership crowding alongside unusual options activity — "
            "crowded institutional book with elevated derivative interest."
        )

    return hints[:6]


def _benchmark_quantiles_for_facts(bench: FundamentalBenchmark | None) -> dict | None:
    if not bench or not bench.data_available:
        return None
    payload: dict = {}
    if bench.pe_percentiles:
        payload["pe_percentiles"] = bench.pe_percentiles.model_dump()
        payload["pe_current_percentile"] = bench.pe_current_percentile
    if bench.margin_percentiles:
        payload["margin_percentiles"] = bench.margin_percentiles.model_dump()
        payload["margin_current_percentile"] = bench.margin_current_percentile
    if bench.revenue_growth_percentiles:
        payload["revenue_growth_percentiles"] = bench.revenue_growth_percentiles.model_dump()
        payload["revenue_growth_current_percentile"] = bench.revenue_growth_current_percentile
    if bench.fcf_margin_percentiles:
        payload["fcf_margin_percentiles"] = bench.fcf_margin_percentiles.model_dump()
        payload["fcf_margin_current_percentile"] = bench.fcf_margin_current_percentile
    return payload or None


def _build_facts(
    symbol,
    market,
    news,
    earnings,
    fundamentals,
    valuation,
    sec_filings,
    insider_summary,
    insider_filings,
    options_flow,
    forward_outlook,
    *,
    macro_overlay=None,
    include_insider: bool = False,
    insider_data_quality: dict | None = None,
    warnings: list[Warning] | None = None,
    fundamental_warnings: list[Warning] | None = None,
    technical_assessment=None,
    fundamental_assessment=None,
    news_digest=None,
    reality_check=None,
    sector_context: SectorContext | None = None,
    smart_money_assessment=None,
    institutional_13f=None,
    activist_filing=None,
    volume_footprint=None,
) -> dict:
    facts: dict = {
        "ticker": symbol,
        "price": market.get("price"),
        "change_pct": market.get("change_pct"),
        "market_state": market.get("market_state"),
        "is_extended_hours": market.get("is_extended_hours"),
        "previous_close": market.get("previous_close"),
        "volume": market.get("volume"),
        "volume_avg_30d": market.get("volume_avg_30d"),
        "volume_ratio": market.get("volume_ratio"),
        "news": [n.model_dump() for n in news],
        "technicals": {
            "rsi": market.get("rsi"),
            "macd": market.get("macd").model_dump() if market.get("macd") else None,
            "volume_ratio": market.get("volume_ratio"),
        },
    }
    if technical_assessment and technical_assessment.data_available:
        facts["technical_assessment"] = technical_assessment.model_dump()
    elif technical_assessment:
        facts["technical_assessment"] = technical_assessment.model_dump()
    if macro_overlay and macro_overlay.has_content:
        facts["macro_context"] = macro_context_facts(macro_overlay)
    if fundamentals:
        facts["fundamentals"] = fundamentals.model_dump()
        bq = _benchmark_quantiles_for_facts(fundamentals.benchmark)
        if bq:
            facts["benchmark_quantiles"] = bq
        facts["business_context"] = {
            "sector": fundamentals.sector,
            "industry": fundamentals.industry,
            "valuation_label": fundamentals.valuation_label,
            "recommendation": fundamentals.recommendation,
            "trading_currency": fundamentals.trading_currency,
            "financial_currency": fundamentals.financial_currency,
            "monetary_values_normalized": fundamentals.monetary_values_normalized,
            "fx_rate_financial_to_trading": fundamentals.fx_rate_financial_to_trading,
        }
    if fundamental_assessment and fundamental_assessment.data_available:
        facts["fundamental_assessment"] = fundamental_assessment.model_dump()
    if news_digest and news_digest.data_available:
        facts["news_digest"] = news_digest.model_dump()
    if reality_check and reality_check.data_available:
        facts["reality_check"] = reality_check.model_dump()
    risk_msgs = [
        w.message
        for w in (*(fundamental_warnings or []), *(warnings or []))
        if w.message
    ]
    if risk_msgs:
        facts["risk_narratives"] = risk_msgs[:5]
    if sector_context and sector_context.data_available:
        facts["sector_context"] = sector_context.model_dump()
    if valuation and valuation.data_available:
        facts["valuation"] = valuation.model_dump()
        facts["valuation_summary"] = build_valuation_summary(valuation)
    if earnings and earnings.data_available:
        facts["earnings"] = earnings.model_dump()
    if sec_filings and sec_filings.data_available:
        facts["sec_filings"] = [
            {
                **f.model_dump(),
                **(
                    {"excerpt": f.excerpt}
                    if f.excerpt_available and f.excerpt
                    else {}
                ),
            }
            for f in sec_filings.filings
        ]
    if insider_summary and insider_summary.data_available:
        facts["insider_summary"] = insider_summary.model_dump()
    if include_insider:
        facts["insider_filings"] = [h.model_dump() for h in insider_filings]
    if insider_data_quality:
        facts["insider_data_quality"] = insider_data_quality
    if forward_outlook and forward_outlook.data_available:
        facts["forward_outlook"] = forward_outlook.model_dump()
    if options_flow and options_flow.put_call_ratio is not None:
        options_summary: dict = {
            "put_call_ratio": options_flow.put_call_ratio,
            "unusual": options_flow.unusual,
            "unusual_reason": options_flow.unusual_reason,
            "call_volume": options_flow.call_volume,
            "put_volume": options_flow.put_volume,
            "open_interest_available": options_flow.open_interest_available,
            "top_strikes": [
                s.model_dump(exclude_none=True) for s in options_flow.top_strikes[:3]
            ],
            "expiry_breakdown": [e.model_dump() for e in options_flow.expiry_breakdown[:3]],
        }
        if options_flow.total_open_interest is not None:
            options_summary["total_open_interest"] = options_flow.total_open_interest
        facts["options_summary"] = options_summary

    if smart_money_assessment and smart_money_assessment.data_available:
        facts["smart_money_assessment"] = {
            "headline": smart_money_assessment.headline,
            "conviction_pct": smart_money_assessment.conviction_pct,
            "layers": [
                {
                    "label": layer.label,
                    "stance": layer.stance,
                    "detail": layer.detail,
                }
                for layer in smart_money_assessment.layers[:5]
            ],
        }

    if institutional_13f:
        facts["institutional_13f"] = {
            "conviction_buy": institutional_13f.conviction_buy,
            "crowding_risk": institutional_13f.crowding_risk,
            "data_available": institutional_13f.data_available,
            "disclaimer": institutional_13f.disclaimer,
            "changes": [
                {
                    "filer_name": ch.filer_name,
                    "change_type": ch.change_type,
                    "pct_change": ch.pct_change,
                    "quarter_note": ch.quarter_note,
                }
                for ch in institutional_13f.changes[:5]
            ],
        }

    if activist_filing:
        facts["activist_filing"] = {
            "form_type": activist_filing.form_type,
            "filing_date": activist_filing.filing_date,
            "filer_name": activist_filing.filer_name,
            "percent_owned": activist_filing.percent_owned,
            "signal": activist_filing.signal,
        }

    if volume_footprint and volume_footprint.data_available:
        facts["volume_footprint"] = {
            "stance": volume_footprint.stance,
            "analysis_bullets": volume_footprint.analysis_bullets[:2],
        }

    hints = _build_synthesis_hints(
        fundamentals=fundamentals,
        valuation=valuation,
        warnings=warnings or [],
        macro_overlay=macro_overlay,
        market=market,
        forward_outlook=forward_outlook,
        technical_assessment=technical_assessment,
        fundamental_assessment=fundamental_assessment,
        news_digest=news_digest,
        sector_context=sector_context,
        insider_summary=insider_summary,
        institutional_13f=institutional_13f,
        activist_filing=activist_filing,
        options_flow=options_flow,
    )
    if hints:
        facts["synthesis_hints"] = hints

    qual_hints = _build_qualitative_hints(
        fundamentals=fundamentals,
        news=news,
        sec_filings=sec_filings,
        insider_summary=insider_summary,
        forward_outlook=forward_outlook,
        warnings=warnings or [],
        fundamental_warnings=fundamental_warnings,
        institutional_13f=institutional_13f,
        activist_filing=activist_filing,
    )
    if qual_hints:
        facts["qualitative_hints"] = qual_hints

    return facts
