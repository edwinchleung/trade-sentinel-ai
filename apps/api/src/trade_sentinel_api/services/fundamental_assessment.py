"""Deterministic fundamental quality assessment from FundamentalsSnapshot."""

from __future__ import annotations

from trade_sentinel_api.models.schemas import (
    FundamentalAssessment,
    FundamentalsSnapshot,
    TrendLabel,
)

_FLAG_SIGNALS = {
    "HIGH_DEBT": "HIGH_DEBT",
    "NEGATIVE_MARGIN": "NEGATIVE_MARGIN",
    "REVENUE_DECLINE": "REVENUE_DECLINE",
    "NEAR_52W_HIGH": "NEAR_52W_HIGH",
    "VALUATION_ABOVE_HISTORY": "VALUATION_ABOVE_HISTORY",
    "VALUATION_BELOW_HISTORY": "VALUATION_BELOW_HISTORY",
    "MARGIN_EXPANDING": "MARGIN_EXPANDING",
    "MARGIN_CONTRACTING": "MARGIN_CONTRACTING",
    "GROWTH_DECELERATING": "GROWTH_DECELERATING",
}


def _quality_label(fund: FundamentalsSnapshot) -> str:
    score = 0
    if fund.roe is not None and fund.roe > 0.15:
        score += 1
    if fund.profit_margin is not None and fund.profit_margin > 0.1:
        score += 1
    if fund.operating_margin is not None and fund.operating_margin > 0.1:
        score += 1
    cf = fund.cash_flow_trends
    if cf and cf[0].fcf_margin_pct is not None and cf[0].fcf_margin_pct > 5:
        score += 1
    if "NEGATIVE_MARGIN" in fund.fundamental_flags:
        score -= 2
    if score >= 3:
        return "strong"
    if score >= 1:
        return "adequate"
    return "weak"


def _growth_label(fund: FundamentalsSnapshot) -> TrendLabel:
    flags = fund.fundamental_flags
    rev_g = fund.revenue_growth
    if rev_g is not None and abs(rev_g) > 1.5:
        rev_g = rev_g / 100
    bench = fund.benchmark
    if "REVENUE_DECLINE" in flags:
        return "bearish"
    if "GROWTH_DECELERATING" in flags:
        return "mixed"
    if rev_g is not None and rev_g > 0.15:
        return "bullish"
    if bench and bench.eps_trend == "up":
        return "bullish"
    if bench and bench.eps_trend == "down":
        return "bearish"
    return "neutral"


def _balance_sheet_label(fund: FundamentalsSnapshot) -> TrendLabel:
    flags = fund.fundamental_flags
    if "HIGH_DEBT" in flags:
        return "bearish"
    if fund.total_cash and fund.total_debt and fund.total_cash > fund.total_debt:
        return "bullish"
    bench = fund.benchmark
    if bench and bench.debt_trend == "improving":
        return "bullish"
    if bench and bench.debt_trend == "worsening":
        return "bearish"
    return "neutral"


def _valuation_context(fund: FundamentalsSnapshot) -> str:
    flags = fund.fundamental_flags
    if "VALUATION_ABOVE_HISTORY" in flags:
        return "rich"
    if "VALUATION_BELOW_HISTORY" in flags:
        return "cheap"
    if fund.valuation_label == "premium":
        return "rich"
    if fund.valuation_label == "discount":
        return "cheap"
    return "fair"


def _overall_label(quality: str, growth: TrendLabel, balance: TrendLabel) -> str:
    caution = 0
    favorable = 0
    if quality == "strong":
        favorable += 1
    elif quality == "weak":
        caution += 1
    if growth == "bullish":
        favorable += 1
    elif growth in ("bearish", "mixed"):
        caution += 1
    if balance == "bullish":
        favorable += 1
    elif balance == "bearish":
        caution += 1
    if favorable >= 2 and caution == 0:
        return "favorable"
    if caution >= 2:
        return "caution"
    if favorable > caution:
        return "favorable"
    if caution > favorable:
        return "caution"
    return "neutral"


def _build_highlights(fund: FundamentalsSnapshot) -> list[str]:
    highlights: list[str] = []
    bench = fund.benchmark
    if bench and bench.benchmark_bullets:
        highlights.extend(bench.benchmark_bullets[:2])
    if fund.revenue_growth is not None:
        rg = fund.revenue_growth / 100 if abs(fund.revenue_growth) > 1.5 else fund.revenue_growth
        highlights.append(f"Revenue growth running at {rg * 100:.0f}% YoY.")
    cf = fund.cash_flow_trends
    if len(cf) >= 2 and cf[0].free_cash_flow is not None and cf[1].free_cash_flow is not None:
        if cf[0].free_cash_flow < cf[1].free_cash_flow:
            highlights.append("Free cash flow compressed vs prior quarter.")
        elif cf[0].free_cash_flow > cf[1].free_cash_flow:
            highlights.append("Free cash flow improved vs prior quarter.")
    if fund.total_cash and fund.total_debt and fund.total_cash > fund.total_debt:
        highlights.append("Balance sheet carries net cash.")
    return highlights[:5]


def build_fundamental_assessment(fund: FundamentalsSnapshot | None) -> FundamentalAssessment:
    if not fund or not fund.data_available:
        return FundamentalAssessment(
            data_available=False,
            message="Fundamentals unavailable for assessment.",
            data_gaps=["fundamentals_unavailable"],
        )

    quality = _quality_label(fund)
    growth = _growth_label(fund)
    balance = _balance_sheet_label(fund)
    val_ctx = _valuation_context(fund)
    overall = _overall_label(quality, growth, balance)
    signals = [_FLAG_SIGNALS[f] for f in fund.fundamental_flags if f in _FLAG_SIGNALS]
    highlights = _build_highlights(fund)

    summary_parts = [
        f"Fundamental quality is {quality}",
        f"growth profile {growth}",
        f"balance sheet {balance}",
    ]
    if val_ctx != "fair":
        summary_parts.append(f"valuation vs own history looks {val_ctx}")
    summary = "; ".join(summary_parts) + "."

    return FundamentalAssessment(
        quality_label=quality,
        growth_label=growth,
        balance_sheet_label=balance,
        valuation_context_label=val_ctx,
        overall_label=overall,
        summary=summary,
        signals=signals,
        highlights=highlights,
        data_available=True,
    )
