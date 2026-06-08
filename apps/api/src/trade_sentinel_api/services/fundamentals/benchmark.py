"""Sector/history benchmark assembly."""

from trade_sentinel_api.models.schemas import FundamentalBenchmark, QuarterlyMetric
from trade_sentinel_api.services.fundamentals.helpers import (
    _build_metric_percentiles,
    _debt_trend,
    _eps_trend,
    _fcf_margin_series,
    _historical_pe_reliable,
    _margin_series,
    _margin_vs_history,
    _pe_vs_history,
    _percentile_rank,
    _revenue_cagr_3y,
    _revenue_growth_acceleration,
    _revenue_growth_series,
    _safe_float,
)

def _build_benchmark(
    hist_quarters: list[QuarterlyMetric],
    q_inc,
    q_bal,
    annual,
    hist,
    price: float | None,
    forward_pe: float | None,
    trailing_pe: float | None,
    *,
    usd_rate: float | None = None,
) -> FundamentalBenchmark:
    if len(hist_quarters) < 4:
        return FundamentalBenchmark(data_available=False)

    revenue_cagr = _revenue_cagr_3y(annual, q_inc, usd_rate=usd_rate)
    eps_trend = _eps_trend(hist_quarters)
    margin_vs_avg = _margin_vs_history(q_inc)
    pe_vs_median, pe_label, median_pe_3y, pe_percentiles, pe_rank = _pe_vs_history(
        hist, q_inc, price, forward_pe, trailing_pe, usd_rate=usd_rate
    )
    hist_pe_reliable = _historical_pe_reliable(median_pe_3y, forward_pe)
    accel = _revenue_growth_acceleration(hist_quarters, q_inc)
    debt_trend = _debt_trend(q_bal)

    margin_series = _margin_series(q_inc)
    margin_percentiles = _build_metric_percentiles(margin_series) if margin_series else None
    margin_rank = (
        _percentile_rank(margin_series[0], margin_series) if len(margin_series) >= 2 else None
    )

    rev_growth_series = _revenue_growth_series(hist_quarters, q_inc)
    revenue_growth_percentiles = (
        _build_metric_percentiles(rev_growth_series) if len(rev_growth_series) >= 2 else None
    )
    revenue_growth_rank = (
        _percentile_rank(rev_growth_series[0], rev_growth_series)
        if len(rev_growth_series) >= 2
        else None
    )

    fcf_series = _fcf_margin_series(q_inc, usd_rate=usd_rate)
    fcf_margin_percentiles = (
        _build_metric_percentiles(fcf_series) if len(fcf_series) >= 4 else None
    )
    fcf_margin_rank = (
        _percentile_rank(fcf_series[0], fcf_series) if len(fcf_series) >= 4 else None
    )

    current_pe = forward_pe or trailing_pe or pe_label

    bullets: list[str] = []
    if revenue_cagr is not None:
        bullets.append(f"Revenue CAGR {revenue_cagr:.1f}% over ~3 years.")
    if margin_vs_avg is not None:
        sign = "+" if margin_vs_avg >= 0 else ""
        bullets.append(f"Operating margin {sign}{margin_vs_avg:.1f} pp vs 3Y average.")
    if pe_vs_median is not None and pe_label is not None and median_pe_3y is not None:
        direction = "above" if pe_vs_median > 0 else "below"
        label = "Forward" if forward_pe else "Trailing"
        bullets.append(
            f"{label} P/E {pe_label:.1f} is ~{abs(pe_vs_median):.0f}% {direction} "
            f"3Y TTM P/E median ({median_pe_3y:.1f})."
        )
    if pe_rank is not None:
        bullets.append(
            f"{('Forward' if forward_pe else 'Trailing')} P/E at ~{pe_rank:.0f}th percentile of own 3Y TTM range."
        )
    if margin_rank is not None:
        bullets.append(
            f"Latest operating margin at ~{margin_rank:.0f}th percentile vs ~3Y history."
        )
    if accel is not None:
        word = "accelerating" if accel > 0 else "decelerating"
        bullets.append(f"Latest YoY revenue growth vs prior periods: {word} ({accel:+.1f} pp).")

    bench_msg = None
    if pe_vs_median is None and current_pe is not None:
        bench_msg = "Insufficient quarterly EPS history for 3Y P/E comparison."

    return FundamentalBenchmark(
        revenue_cagr_3y=revenue_cagr,
        eps_trend=eps_trend,
        margin_vs_3y_avg_pct=margin_vs_avg,
        pe_vs_3y_median_pct=pe_vs_median,
        median_pe_3y=median_pe_3y,
        pe_percentiles=pe_percentiles,
        pe_current_percentile=pe_rank,
        margin_percentiles=margin_percentiles,
        margin_current_percentile=margin_rank,
        revenue_growth_percentiles=revenue_growth_percentiles,
        revenue_growth_current_percentile=revenue_growth_rank,
        fcf_margin_percentiles=fcf_margin_percentiles,
        fcf_margin_current_percentile=fcf_margin_rank,
        historical_pe_reliable=hist_pe_reliable,
        revenue_growth_acceleration=accel,
        debt_trend=debt_trend,
        benchmark_bullets=bullets[:5],
        data_available=len(bullets) > 0,
        message=bench_msg,
    )

def _build_flags(info, price, quarters, benchmark: FundamentalBenchmark | None) -> list[str]:
    flags: list[str] = []
    de = _safe_float(info.get("debtToEquity"))
    if de is not None and de > 200:
        flags.append("HIGH_DEBT")
    margin = _safe_float(info.get("profitMargins"))
    if margin is not None and margin < 0:
        flags.append("NEGATIVE_MARGIN")
    if len(quarters) >= 2 and all(
        q.revenue_qoq_pct is not None and q.revenue_qoq_pct < 0 for q in quarters[:2]
    ):
        flags.append("REVENUE_DECLINE")
    hi = _safe_float(info.get("fiftyTwoWeekHigh"))
    if price and hi and hi > 0 and price >= hi * 0.95:
        flags.append("NEAR_52W_HIGH")
    if benchmark and benchmark.data_available:
        if benchmark.pe_vs_3y_median_pct is not None and benchmark.pe_vs_3y_median_pct > 25:
            flags.append("VALUATION_ABOVE_HISTORY")
        elif benchmark.pe_vs_3y_median_pct is not None and benchmark.pe_vs_3y_median_pct < -15:
            flags.append("VALUATION_BELOW_HISTORY")
        if benchmark.margin_vs_3y_avg_pct is not None:
            if benchmark.margin_vs_3y_avg_pct > 1:
                flags.append("MARGIN_EXPANDING")
            elif benchmark.margin_vs_3y_avg_pct < -1:
                flags.append("MARGIN_CONTRACTING")
        if benchmark.revenue_growth_acceleration is not None and benchmark.revenue_growth_acceleration < -5:
            flags.append("GROWTH_DECELERATING")
    return flags


def _valuation_label(pe_forward: float | None) -> str | None:
    if pe_forward is None:
        return None
    if pe_forward > 40:
        return "premium"
    if pe_forward < 15:
        return "discount"
    return "moderate"
