"""Sanitize and label data_gaps for user-facing API responses."""

import re

_MAX_BRIEFING_GAPS = 5
_MAX_CONTEXT_GAPS = 3

_GAP_LABELS: dict[str, str] = {
    "fred_auth_failed": "FRED API key invalid or expired — check FRED_API_KEY in .env",
    "fred_api_key_missing": "FRED API key not configured (optional official macro stats)",
    "fred_cpi_yoy_unavailable": "CPI year-over-year unavailable from FRED",
    "insider_feed_empty": "No insider Form 4 filings found for this ticker",
    "insider_partial_parse": "Some insider filings lack share/price details in parsed excerpts",
    "fundamentals_unavailable": "Fundamental snapshot unavailable",
    "valuation_limited_history": "Limited issuer history — fair-value band may be less reliable",
    "valuation_few_methods": "Few valuation methods available for headline band",
    "valuation_currency_mismatch": "Reporting currency differs from quote currency and FX conversion failed — fair-value band restricted",
    "earnings_unavailable": "Earnings snapshot unavailable",
    "yfinance_signals_unavailable": "Market indicator data temporarily unavailable",
    "macro_news_all_sources_empty": "No macro news headlines available from any source",
    "yfinance_macro_news_empty": "SPY/S&P macro headlines unavailable (yfinance)",
    "llm_bad_request": "LLM bad request (400) — check model name and provider settings",
    "llm_auth_error": "LLM authentication failed (401) — check LLM_API_KEY",
    "llm_insufficient_credits": "LLM insufficient credits (402) — add credits at your provider",
    "llm_forbidden": "LLM forbidden (403) — permissions or moderation block",
    "llm_timeout": "LLM request timed out (408/504)",
    "llm_rate_limited": "LLM rate limited (429) — retry after a short wait",
    "llm_provider_down": "LLM provider error (502) — model down or invalid upstream response",
    "llm_no_provider": "No LLM provider matched routing (503)",
    "llm_api_error": "LLM request failed — see API logs for details",
    "llm_parse_error": "AI summary could not be parsed from model output",
    "llm_unconfigured": "LLM not configured — set provider credentials in .env",
}

_CONTEXT_ACTIONABLE = frozenset(
    {
        "fred_auth_failed",
        "fred_api_key_missing",
        "insider_feed_empty",
        "fundamentals_unavailable",
        "earnings_unavailable",
        "llm_unconfigured",
        "llm_parse_error",
    }
)

_CPI_RAW_GAPS = frozenset(
    {
        "fred_CPIAUCSL_fetch_failed",
        "fred_CPIAUCSL_empty",
        "fred_CPI_YOY_compute_failed",
    }
)

_LLM_BLOCKLIST_PATTERNS = [
    re.compile(r"insider_transaction_details_unavailable", re.I),
    re.compile(r"_actual_not_yet_released$", re.I),
    re.compile(r"^ISM_.*_actual", re.I),
]

_INFRA_GAPS_WHEN_CURVE_OK = frozenset(
    {
        "fred_T10Y2Y_fetch_failed",
        "fred_T10Y2Y_empty",
    }
)

_INFRA_GAPS_WHEN_CPI_OPTIONAL = frozenset(
    {
        "fred_CPIAUCSL_fetch_failed",
        "fred_CPIAUCSL_empty",
        "fred_CPI_YOY_compute_failed",
        "fred_cpi_yoy_unavailable",
    }
)


def gap_display_label(code: str) -> str:
    return _GAP_LABELS.get(code, code.replace("_", " "))


def collapse_cpi_gaps(gaps: list[str]) -> list[str]:
    """Replace raw CPIAUCSL failure codes with a single canonical gap."""
    had_cpi = any(g in _CPI_RAW_GAPS or g == "fred_cpi_yoy_unavailable" for g in gaps)
    out = [g for g in gaps if g not in _CPI_RAW_GAPS]
    if had_cpi and "fred_cpi_yoy_unavailable" not in out:
        out.append("fred_cpi_yoy_unavailable")
    return list(dict.fromkeys(out))


def macro_facts_data_gaps(overlay_gaps: list[str] | None) -> list[str]:
    """Only actionable FRED gaps belong in LLM facts."""
    if not overlay_gaps:
        return []
    return [g for g in overlay_gaps if g in ("fred_auth_failed", "fred_api_key_missing")]


def _is_blocked_llm_gap(gap: str) -> bool:
    return any(p.search(gap) for p in _LLM_BLOCKLIST_PATTERNS)


def _merge_and_filter_gaps(
    llm_gaps: list[str],
    macro_gaps: list[str],
    *,
    yield_curve_available: bool,
    cpi_yoy_available: bool,
    insider_quality: dict | None,
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for g in list(macro_gaps) + list(llm_gaps):
        code = (g or "").strip()
        if not code or code in seen:
            continue
        if _is_blocked_llm_gap(code):
            continue
        if yield_curve_available and code in _INFRA_GAPS_WHEN_CURVE_OK:
            continue
        if cpi_yoy_available and code in _INFRA_GAPS_WHEN_CPI_OPTIONAL:
            continue
        if code.startswith("fred_") and code.endswith("_fetch_failed"):
            if yield_curve_available and "T10Y2Y" in code:
                continue
        seen.add(code)
        merged.append(code)

    if insider_quality:
        if insider_quality.get("feed_unavailable") and insider_quality.get("insider_requested"):
            if "insider_feed_empty" not in seen:
                merged.append("insider_feed_empty")

    deduped: list[str] = []
    seen2: set[str] = set()
    for code in merged:
        if code not in seen2:
            seen2.add(code)
            deduped.append(code)
    return deduped


def _apply_context_allowlist(gaps: list[str]) -> list[str]:
    return [g for g in gaps if g in _CONTEXT_ACTIONABLE]


def sanitize_context_data_gaps(
    llm_gaps: list[str],
    macro_gaps: list[str],
    *,
    yield_curve_available: bool,
    cpi_yoy_available: bool = False,
    insider_quality: dict | None = None,
) -> list[str]:
    """Ticker context: only user-actionable gaps, max 3."""
    merged = _merge_and_filter_gaps(
        llm_gaps,
        macro_gaps,
        yield_curve_available=yield_curve_available,
        cpi_yoy_available=cpi_yoy_available,
        insider_quality=insider_quality,
    )
    return _apply_context_allowlist(merged)[:_MAX_CONTEXT_GAPS]


def sanitize_briefing_data_gaps(
    gaps: list[str],
    *,
    yield_curve_available: bool,
    cpi_yoy_available: bool = False,
) -> list[str]:
    """Macro briefing: keep infra gaps (FRED/news) after noise filtering."""
    merged = _merge_and_filter_gaps(
        [],
        gaps,
        yield_curve_available=yield_curve_available,
        cpi_yoy_available=cpi_yoy_available,
        insider_quality=None,
    )
    return merged[:_MAX_BRIEFING_GAPS]
