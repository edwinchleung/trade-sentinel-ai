"""Shared row/period utilities and benchmark math helpers."""

from __future__ import annotations

import math
from typing import Literal

from trade_sentinel_api.models.schemas import (
    FundamentalBenchmark,
    MetricPercentiles,
    QuarterlyMetric,
)
from trade_sentinel_api.services.currency import convert_amount

_REVENUE_ROWS = ("Total Revenue", "Revenue")
_EPS_ROWS = ("Diluted EPS", "Basic EPS")
_OP_INCOME_ROWS = ("Operating Income", "Total Operating Income As Reported")
_NET_INCOME_ROWS = ("Net Income", "Net Income Common Stockholders")
_GROSS_PROFIT_ROWS = ("Gross Profit",)
_OCF_ROWS = (
    "Operating Cash Flow",
    "Total Cash From Operating Activities",
    "Cash Flow From Continuing Operating Activities",
)
_CAPEX_ROWS = ("Capital Expenditure", "Capital Expenditures", "Purchase Of PPE")
_FCF_ROWS = ("Free Cash Flow",)
_DEBT_ROWS = ("Total Debt", "Long Term Debt")
_EQUITY_ROWS = ("Stockholders Equity", "Total Equity Gross Minority Interest")
_CASH_ROWS = (
    "Cash And Cash Equivalents",
    "Cash Cash Equivalents And Short Term Investments",
)
_CURRENT_ASSETS_ROWS = ("Current Assets", "Total Current Assets")
_CURRENT_LIAB_ROWS = ("Current Liabilities", "Total Current Liabilities")


def _scale_amount(val: float | None, usd_rate: float | None) -> float | None:
    if val is None or usd_rate is None or usd_rate == 1.0:
        return val
    return convert_amount(val, usd_rate)


def _ttm_revenue_from_income(trends: list) -> float | None:
    revs = [q.revenue for q in trends[:4] if getattr(q, "revenue", None) is not None]
    if len(revs) < 4:
        return None
    total = sum(revs)
    return total if total > 0 else None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _row_value(df, row_names: tuple[str, ...], col_idx: int) -> float | None:
    if df is None or df.empty or col_idx >= df.shape[1]:
        return None
    for name in row_names:
        if name in df.index:
            return _safe_float(df.loc[name, df.columns[col_idx]])
    return None


def _period_label(ts) -> str:
    try:
        return ts.strftime("%Y-Q") + str((ts.month - 1) // 3 + 1)
    except Exception:
        return str(ts)[:10]
def _revenue_cagr_3y(annual, q_inc, *, usd_rate: float | None = None) -> float | None:
    revenues: list[float] = []
    if annual is not None and not annual.empty:
        for i in range(min(4, annual.shape[1])):
            rev = _scale_amount(_row_value(annual, _REVENUE_ROWS, i), usd_rate)
            if rev is not None and rev > 0:
                revenues.append(rev)
    if len(revenues) < 2 and q_inc is not None and not q_inc.empty:
        for i in range(min(12, q_inc.shape[1])):
            rev = _scale_amount(_row_value(q_inc, _REVENUE_ROWS, i), usd_rate)
            if rev is not None and rev > 0:
                revenues.append(rev)
        revenues = revenues[::-1]
    if len(revenues) < 2:
        return None
    start, end = revenues[-1], revenues[0]
    years = max(len(revenues) - 1, 1)
    if start <= 0 or end <= 0:
        return None
    cagr = (pow(end / start, 1 / years) - 1) * 100
    return round(cagr, 2)


def _eps_trend(quarters: list[QuarterlyMetric]) -> Literal["up", "flat", "down"] | None:
    eps_vals = [q.eps for q in reversed(quarters[:8]) if q.eps is not None]
    if len(eps_vals) < 3:
        return None
    first_half = sum(eps_vals[: len(eps_vals) // 2]) / (len(eps_vals) // 2)
    second_half = sum(eps_vals[len(eps_vals) // 2 :]) / (len(eps_vals) - len(eps_vals) // 2)
    if second_half > first_half * 1.05:
        return "up"
    if second_half < first_half * 0.95:
        return "down"
    return "flat"


def _margin_vs_history(q_inc) -> float | None:
    if q_inc is None or q_inc.empty:
        return None
    margins: list[float] = []
    n = min(12, q_inc.shape[1])
    for i in range(n):
        rev = _row_value(q_inc, _REVENUE_ROWS, i)
        op = _row_value(q_inc, _OP_INCOME_ROWS, i)
        if rev and op is not None and rev != 0:
            margins.append(op / rev * 100)
    if len(margins) < 2:
        return None
    latest = margins[0]
    avg = sum(margins) / len(margins)
    return round(latest - avg, 2)


def _normalize_hist_index(hist):
    if hist is None or hist.empty:
        return None
    idx = hist.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    return hist.set_axis(idx, axis=0)


def _quarter_end_ts(col):
    if hasattr(col, "to_pydatetime"):
        ts = col.to_pydatetime()
    elif hasattr(col, "date"):
        ts = col
    else:
        ts = col
    if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
        try:
            ts = ts.replace(tzinfo=None)
        except Exception:
            pass
    return ts


def _price_on_or_before(hist, end_ts) -> float | None:
    if hist is None or hist.empty:
        return None
    h = _normalize_hist_index(hist)
    try:
        import pandas as pd

        target = pd.Timestamp(end_ts)
        if hasattr(h.index, "tz") and h.index.tz is not None:
            target = target.tz_localize(None)
        mask = h.index <= target
        if mask.any():
            return float(h.loc[mask, "Close"].iloc[-1])
    except Exception:
        pass
    return None


_PE_WINSORIZE_CAP = 80.0


def _percentile_value(sorted_vals: list[float], pct: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    k = (len(sorted_vals) - 1) * pct / 100
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return round(sorted_vals[f], 2)
    return round(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f), 2)


def _build_metric_percentiles(values: list[float]) -> MetricPercentiles | None:
    if len(values) < 2:
        return None
    s = sorted(values)
    return MetricPercentiles(
        p10=_percentile_value(s, 10),
        p25=_percentile_value(s, 25),
        p50=_percentile_value(s, 50),
        p75=_percentile_value(s, 75),
        p90=_percentile_value(s, 90),
    )


def _percentile_rank(current: float, sorted_vals: list[float]) -> float | None:
    if not sorted_vals or len(sorted_vals) < 2:
        return None
    s = sorted(sorted_vals)
    below = sum(1 for v in s if v < current)
    return round(below / (len(s) - 1) * 100, 1)


def _margin_series(q_inc) -> list[float]:
    if q_inc is None or q_inc.empty:
        return []
    margins: list[float] = []
    n = min(12, q_inc.shape[1])
    for i in range(n):
        rev = _row_value(q_inc, _REVENUE_ROWS, i)
        op = _row_value(q_inc, _OP_INCOME_ROWS, i)
        if rev and op is not None and rev != 0:
            margins.append(op / rev * 100)
    return margins


def _revenue_growth_series(
    quarters: list[QuarterlyMetric],
    q_inc=None,
) -> list[float]:
    yoys = [q.revenue_yoy_pct for q in quarters if q.revenue_yoy_pct is not None]
    if len(yoys) >= 2:
        return yoys
    if q_inc is None or q_inc.empty:
        return []
    yoys = []
    for i in range(min(8, q_inc.shape[1])):
        yoy = _revenue_yoy_from_q_inc(q_inc, i)
        if yoy is not None:
            yoys.append(yoy)
    return yoys


def _fcf_margin_series(q_inc, *, usd_rate: float | None = None) -> list[float]:
    if q_inc is None or q_inc.empty:
        return []
    margins: list[float] = []
    n = min(12, q_inc.shape[1])
    for i in range(n):
        rev = _scale_amount(_row_value(q_inc, _REVENUE_ROWS, i), usd_rate)
        fcf = _scale_amount(_row_value(q_inc, _FCF_ROWS, i), usd_rate)
        if fcf is None:
            ocf = _scale_amount(_row_value(q_inc, _OCF_ROWS, i), usd_rate)
            capex = _scale_amount(_row_value(q_inc, _CAPEX_ROWS, i), usd_rate)
            if ocf is not None and capex is not None:
                fcf = ocf + capex
        if rev and fcf is not None and rev != 0:
            margins.append(fcf / rev * 100)
    return margins


def _ttm_eps_at(q_inc, col_idx: int, *, usd_rate: float | None = None) -> float | None:
    """Sum EPS over 4 quarters starting at col_idx (rolling TTM)."""
    if q_inc is None or q_inc.empty or col_idx + 3 >= q_inc.shape[1]:
        return None
    total = 0.0
    for j in range(col_idx, col_idx + 4):
        eps = _scale_amount(_row_value(q_inc, _EPS_ROWS, j), usd_rate)
        if eps is None:
            return None
        total += eps
    return total if total > 0 else None


def _winsorize_pe_series(pe_series: list[float]) -> list[float]:
    if len(pe_series) < 2:
        return pe_series
    ordered = sorted(pe_series)
    p80_idx = min(int(len(ordered) * 0.8), len(ordered) - 1)
    p80 = ordered[p80_idx]
    cap = min(_PE_WINSORIZE_CAP, max(p80, 1.0) * 1.05)
    return [min(p, cap) for p in pe_series]


def _pe_series_ttm(
    hist, q_inc, price: float | None, *, usd_rate: float | None = None
) -> list[float]:
    """Trailing P/E at each quarter using price / TTM EPS (not single-quarter EPS)."""
    if q_inc is None or q_inc.empty:
        return []
    series: list[float] = []
    n = min(12, q_inc.shape[1])
    for i in range(n):
        ttm_eps = _ttm_eps_at(q_inc, i, usd_rate=usd_rate)
        if ttm_eps is None or ttm_eps <= 0:
            continue
        col = q_inc.columns[i]
        q_price = _price_on_or_before(hist, _quarter_end_ts(col))
        if q_price is None and price is not None and i == 0:
            q_price = price
        if q_price is not None and q_price > 0:
            pe = q_price / ttm_eps
            if 0 < pe < 500:
                series.append(pe)
    return _winsorize_pe_series(series)


def _historical_pe_reliable(median_pe: float | None, forward_pe: float | None) -> bool:
    if median_pe is None or median_pe <= 0:
        return False
    if median_pe > _PE_WINSORIZE_CAP:
        return False
    if forward_pe is not None and forward_pe > 0 and median_pe > forward_pe * 2:
        return False
    return True


def _pe_vs_history(
    hist,
    q_inc,
    price: float | None,
    forward_pe: float | None,
    trailing_pe: float | None,
    *,
    usd_rate: float | None = None,
) -> tuple[
    float | None,
    float | None,
    float | None,
    MetricPercentiles | None,
    float | None,
]:
    """Return (pct vs 3y TTM P/E median, current P/E, median_pe_3y, pe_percentiles, pe_rank)."""
    current_pe = forward_pe or trailing_pe
    if q_inc is None or q_inc.empty:
        return None, current_pe, None, None, None

    if current_pe is None and price:
        ttm0 = _ttm_eps_at(q_inc, 0, usd_rate=usd_rate)
        if ttm0 and ttm0 > 0:
            current_pe = price / ttm0

    pe_series = _pe_series_ttm(hist, q_inc, price, usd_rate=usd_rate)
    if len(pe_series) < 2:
        return None, current_pe, None, None, None

    if current_pe is None:
        return None, None, None, None, None

    pe_sorted = sorted(pe_series)
    median = pe_sorted[len(pe_sorted) // 2]
    if median <= 0:
        return None, current_pe, None, None, None
    pct = round((current_pe - median) / median * 100, 2)
    pe_pctiles = _build_metric_percentiles(pe_sorted)
    pe_rank = _percentile_rank(current_pe, pe_sorted)
    return pct, current_pe, round(median, 2), pe_pctiles, pe_rank


def _revenue_yoy_from_q_inc(q_inc, col_idx: int) -> float | None:
    rev = _row_value(q_inc, _REVENUE_ROWS, col_idx)
    prior_rev = _row_value(q_inc, _REVENUE_ROWS, col_idx + 4)
    if rev is None or prior_rev is None or prior_rev == 0:
        return None
    return round((rev - prior_rev) / abs(prior_rev) * 100, 2)


def _revenue_growth_acceleration(
    quarters: list[QuarterlyMetric],
    q_inc=None,
) -> float | None:
    yoys = [q.revenue_yoy_pct for q in quarters if q.revenue_yoy_pct is not None]
    if len(yoys) < 2 and q_inc is not None and not q_inc.empty and q_inc.shape[1] >= 5:
        yoys = []
        for i in range(min(4, q_inc.shape[1])):
            yoy = _revenue_yoy_from_q_inc(q_inc, i)
            if yoy is not None:
                yoys.append(yoy)
    if len(yoys) < 2:
        return None
    latest = yoys[0]
    prior_avg = sum(yoys[1:4]) / min(len(yoys[1:4]), 3) if len(yoys) > 1 else yoys[1]
    return round(latest - prior_avg, 2)


def _debt_trend(q_bal) -> Literal["improving", "stable", "worsening"] | None:
    if q_bal is None or q_bal.empty or q_bal.shape[1] < 2:
        return None
    def de(i):
        debt = _row_value(q_bal, ("Total Debt", "Long Term Debt"), i)
        equity = _row_value(q_bal, ("Stockholders Equity", "Total Equity Gross Minority Interest"), i)
        if debt is not None and equity and equity != 0:
            return debt / equity
        return None
    now = de(0)
    past = de(min(4, q_bal.shape[1] - 1))
    if now is None or past is None:
        return None
    if now < past * 0.95:
        return "improving"
    if now > past * 1.05:
        return "worsening"
    return "stable"


