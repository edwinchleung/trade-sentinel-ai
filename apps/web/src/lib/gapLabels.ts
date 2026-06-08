/** User-facing labels for API data_gaps codes (keep in sync with data_gaps.py). */
const GAP_LABELS: Record<string, string> = {
  fred_auth_failed: "FRED API key invalid or expired — check FRED_API_KEY in .env",
  fred_api_key_missing: "FRED API key not configured (optional official macro stats)",
  fred_cpi_yoy_unavailable: "CPI year-over-year unavailable from FRED",
  insider_feed_empty: "No insider Form 4 filings found for this ticker",
  insider_partial_parse: "Some insider filings lack share/price details in parsed excerpts",
  fundamentals_unavailable: "Fundamental snapshot unavailable",
  earnings_unavailable: "Earnings snapshot unavailable",
  valuation_few_methods: "Fair-value band uses fewer than two methods — treat as indicative",
  valuation_limited_history: "Limited issuer history — fair-value band may be less reliable",
  valuation_currency_mismatch:
    "Reporting currency differs from quote currency and FX conversion failed — fair-value band restricted",
  dcf_fcf_unavailable: "DCF skipped — free cash flow missing or negative",
  dcf_invalid_assumptions: "DCF could not be computed with current assumptions",
  yfinance_signals_unavailable: "Market indicator data temporarily unavailable",
  macro_news_all_sources_empty: "No macro news headlines available from any source",
  yfinance_macro_news_empty: "SPY/S&P macro headlines unavailable (yfinance)",
  llm_bad_request: "LLM bad request (400) — check model name and provider settings",
  llm_auth_error: "LLM authentication failed (401) — check LLM_API_KEY",
  llm_insufficient_credits: "LLM insufficient credits (402) — add credits at your provider",
  llm_forbidden: "LLM forbidden (403) — permissions or moderation block",
  llm_timeout: "LLM request timed out (408/504)",
  llm_rate_limited: "LLM rate limited (429) — retry after a short wait",
  llm_provider_down: "LLM provider error (502) — model down or invalid upstream response",
  llm_no_provider: "No LLM provider matched routing (503)",
  llm_api_error: "LLM request failed — see API logs for details",
  llm_parse_error: "AI summary could not be parsed from model output",
  llm_unconfigured: "LLM not configured — set provider credentials in .env",
};

export function gapDisplayLabel(code: string): string {
  return GAP_LABELS[code] ?? code.replace(/_/g, " ");
}
