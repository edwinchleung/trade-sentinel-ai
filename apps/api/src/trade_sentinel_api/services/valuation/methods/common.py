"""Shared valuation utilities and sector priors."""

from __future__ import annotations

import json
import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yfinance as yf

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    DcfSensitivityPoint,
    FundamentalsSnapshot,
    ValuationAssessment,
    ValuationMethodResult,
)
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.currency import currencies_differ

logger = logging.getLogger(__name__)

_FUND_QUOTE_TYPES = frozenset({"ETF", "MUTUALFUND", "INDEX"})

_EQUITY_RISK_PREMIUM = 0.055
_DEFAULT_RISK_FREE = 0.045
_DISCOUNT_MIN = 0.08
_DISCOUNT_MAX = 0.14
_TERMINAL_GROWTH_MIN = 0.015
_TERMINAL_GROWTH_MAX = 0.03
_GROWTH_CAP_FLOOR = 0.06
_GROWTH_CAP_CEILING = 0.20
_METHOD_SPREAD_LOW_CONFIDENCE = 3.0
_METHOD_SPREAD_HIGH_CONFIDENCE = 2.5
_ANALYST_STALE_UPSIDE = 80.0
_ANALYST_STALE_DOWNSIDE = -50.0
_SECTOR_PRIORS_PATH = Path(__file__).resolve().parents[5] / "data" / "sector_pe_priors.json"
_SECTOR_MULTIPLES_PATH = Path(__file__).resolve().parents[5] / "data" / "sector_multiples.json"
_DCF_PROJECTION_YEARS = 5
_METHOD_WEIGHTS = {
    "analyst_target": 0.35,
    "dcf": 0.35,
    "graham_eps": 0.15,
    "historical_pe": 0.15,
    "peg": 0.12,
    "price_to_sales": 0.10,
    "price_to_book": 0.12,
    "sector_pe_prior": 0.10,
    "ev_ebitda": 0.12,
}


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


def _latest_ttm_eps(fundamentals: FundamentalsSnapshot) -> float | None:
    eps_vals = [q.eps for q in fundamentals.quarterly_trends[:4] if q.eps is not None]
    if len(eps_vals) < 4:
        return None
    total = sum(eps_vals)
    return total if total > 0 else None


def _currency_mismatch_unresolved(fundamentals: FundamentalsSnapshot) -> bool:
    return "currency_mismatch_unresolved" in fundamentals.fundamental_flags


def _monetary_ok_for_valuation(fundamentals: FundamentalsSnapshot) -> bool:
    if _currency_mismatch_unresolved(fundamentals):
        return False
    if currencies_differ(fundamentals.trading_currency, fundamentals.financial_currency):
        return fundamentals.monetary_values_normalized
    return True


def _eps_for_valuation(fundamentals: FundamentalsSnapshot) -> float | None:
    if currencies_differ(fundamentals.trading_currency, fundamentals.financial_currency):
        eps = fundamentals.trailing_eps_quote
        return eps if eps is not None and eps > 0 else None
    return _latest_ttm_eps(fundamentals)


def _latest_ttm_fcf(fundamentals: FundamentalsSnapshot) -> tuple[float | None, list[str]]:
    """Return TTM FCF (prefer steadier capex-adjusted series when available)."""
    gaps: list[str] = []
    cf = fundamentals.cash_flow_trends
    if len(cf) >= 4:
        fcf_vals = [q.free_cash_flow for q in cf[:4] if q.free_cash_flow is not None]
        adj_vals = []
        for q in cf[:4]:
            if q.operating_cash_flow is not None and q.capital_expenditure is not None:
                capex = abs(q.capital_expenditure)
                adj_vals.append(q.operating_cash_flow - capex)
        if len(fcf_vals) == 4:
            total_fcf = sum(fcf_vals)
            if len(adj_vals) == 4:
                total_adj = sum(adj_vals)
                if total_adj > 0 and _series_cv(adj_vals) < _series_cv(fcf_vals):
                    return total_adj, gaps
            if total_fcf > 0:
                return total_fcf, gaps
            gaps.append("dcf_fcf_unavailable")
            return None, gaps
    fcf = fundamentals.free_cash_flow
    if fcf is not None and fcf > 0:
        gaps.append("dcf_fcf_single_quarter")
        return fcf, gaps
    gaps.append("dcf_fcf_unavailable")
    return None, gaps


def _series_cv(vals: list[float]) -> float:
    if len(vals) < 2:
        return 999.0
    mean = sum(vals) / len(vals)
    if mean <= 0:
        return 999.0
    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    return math.sqrt(variance) / mean


def _fcf_cv_excludes_composite(fundamentals: FundamentalsSnapshot) -> bool:
    cf = fundamentals.cash_flow_trends
    vals = [q.free_cash_flow for q in cf[:4] if q.free_cash_flow is not None and q.free_cash_flow > 0]
    if len(vals) < 2:
        return True
    mean = sum(vals) / len(vals)
    if mean <= 0:
        return True
    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    cv = math.sqrt(variance) / mean
    return cv > 0.75


def _mos_thresholds(sector: str | None) -> tuple[float, float]:
    settings = get_settings()
    s = (sector or "").lower()
    if any(x in s for x in ("technology", "communication", "semiconductor", "software")):
        return settings.valuation_mos_tech_over, settings.valuation_mos_tech_under
    if any(x in s for x in ("utilities", "consumer defensive", "staples")):
        return settings.valuation_mos_defensive_over, settings.valuation_mos_defensive_under
    return settings.valuation_mos_default_over, settings.valuation_mos_default_under


@lru_cache(maxsize=1)
def _load_sector_pe_priors() -> dict[str, float]:
    multiples = _load_sector_multiples()
    if multiples:
        return {k: float(v["pe"]) for k, v in multiples.items() if "pe" in v}
    try:
        with open(_SECTOR_PRIORS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: float(v) for k, v in data.items()}
    except (OSError, ValueError, TypeError):
        return {}


@lru_cache(maxsize=1)
def _load_sector_multiples() -> dict[str, dict[str, float]]:
    try:
        with open(_SECTOR_MULTIPLES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {
            k: {mk: float(mv) for mk, mv in v.items()}
            for k, v in data.items()
            if isinstance(v, dict)
        }
    except (OSError, ValueError, TypeError):
        return {}


def _sector_multiple(sector: str, key: str) -> float | None:
    entry = _load_sector_multiples().get(sector, {})
    val = entry.get(key)
    return float(val) if val is not None else None


def _fade_growth_year(start_growth: float, terminal_growth: float, year: int, years: int) -> float:
    if years <= 1:
        return start_growth
    t = (year - 1) / (years - 1)
    return start_growth + (terminal_growth - start_growth) * t


def _is_bank_or_reit(fundamentals: FundamentalsSnapshot) -> bool:
    sector = (fundamentals.sector or "").lower()
    industry = (fundamentals.industry or "").lower()
    return any(
        k in sector or k in industry
        for k in ("bank", "reit", "insurance", "financial", "mortgage")
    )


def _analyst_target_stale(upside: float | None) -> bool:
    if upside is None:
        return False
    return upside > _ANALYST_STALE_UPSIDE or upside < _ANALYST_STALE_DOWNSIDE


def _normalize_growth_pct(val: float | None) -> float | None:
    if val is None:
        return None
    g = val / 100 if abs(val) > 1.5 else val
    return g if g > 0 else None


def _median_pe_3y(fundamentals: FundamentalsSnapshot) -> float | None:
    bench = fundamentals.benchmark
    if bench and bench.median_pe_3y is not None:
        return bench.median_pe_3y
    return None


