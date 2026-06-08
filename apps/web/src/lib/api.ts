const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type Warning = {
  code: string;
  message: string;
  severity: "low" | "medium" | "high";
};

export type NewsItem = {
  title: string;
  url?: string | null;
  published_at?: string | null;
  source?: string | null;
  summary?: string | null;
  sentiment_label?: "bullish" | "bearish" | "neutral" | null;
  sentiment_score?: number | null;
  themes?: string[];
};

export type NewsDigest = {
  overall_sentiment?: "bullish" | "bearish" | "mixed" | "neutral" | null;
  summary_line?: string | null;
  top_themes?: string[];
  bullish_count?: number;
  bearish_count?: number;
  neutral_count?: number;
  data_available: boolean;
  message?: string | null;
};

export type VisualStance = "favorable" | "neutral" | "caution" | "unavailable";
export type MetricTone = "positive" | "neutral" | "negative" | "muted";

export type ContextSectionLabel = {
  stance: VisualStance;
  headline: string;
};

export type ContextVisualMetric = {
  label: string;
  value: string;
  tone?: MetricTone | null;
};

export type ContextVisualSparkPoint = {
  period: string;
  value: number;
};

export type ContextVisualSection = {
  id: string;
  title: string;
  stance: VisualStance;
  metrics: ContextVisualMetric[];
  sparkline: ContextVisualSparkPoint[];
};

export type ContextVisualPillar = {
  id: string;
  label: string;
  stance: VisualStance;
};

export type ContextVisualSnapshot = {
  pillars: ContextVisualPillar[];
  sections: ContextVisualSection[];
};

export type ContextSummary = {
  bullets: string[];
  section_bullets?: Record<string, string> | null;
  qualitative_analysis?: string | null;
  technical_interpretation?: string | null;
  fundamental_interpretation?: string | null;
  reality_check_narrative?: string | null;
  scenario_bullets?: string[];
  section_labels?: ContextSectionLabel[];
  model: string;
  cached_at?: string | null;
  data_gaps?: string[];
};

export type MacroSummary = {
  bullets: string[];
  model: string;
  cached_at?: string | null;
  data_gaps?: string[];
};

export type MacroEvent = {
  name: string;
  impact: string;
  sectors: string[];
  time_et?: string | null;
  actual?: number | null;
  estimate?: number | null;
  prior?: number | null;
  source?: string | null;
  date?: string | null;
  playbook?: string | null;
  surprise_pct?: number | null;
  beat_miss?: "beat" | "miss" | "inline" | "unavailable" | null;
};

export type MacroSignal = {
  symbol: string;
  label: string;
  level?: number | null;
  change_1d_pct?: number | null;
  change_5d_pct?: number | null;
};

export type FredObservation = {
  series_id: string;
  label: string;
  value?: number | null;
  observation_date?: string | null;
};

export type MacroSignalsSnapshot = {
  as_of: string;
  signals: MacroSignal[];
  yield_curve_10y_3m_bps?: number | null;
  risk_tone?: "elevated_vix" | "normal" | "unavailable";
  official?: FredObservation[];
  data_gaps?: string[];
};

export type MacroReleaseStats = {
  beats: number;
  misses: number;
  inline: number;
  unavailable: number;
  largest_surprises: {
    name: string;
    surprise_pct?: number;
    beat_miss?: string;
    actual?: number;
    estimate?: number;
  }[];
};

export type MacroContextOverlay = {
  trading_date: string;
  ticker?: string | null;
  ticker_sector?: string | null;
  has_content: boolean;
  market_weather?: string | null;
  signal_highlights?: string[];
  headline_events?: string[];
  relevant_events: MacroEvent[];
  impact_summary?: { high: number; moderate: number; noise: number };
  macro_signals?: MacroSignalsSnapshot | null;
  macro_news?: NewsItem[];
  release_stats?: MacroReleaseStats | null;
  data_gaps?: string[];
};

export type EarningsSnapshot = {
  next_report_date?: string | null;
  days_until?: number | null;
  last_eps_actual?: number | null;
  last_eps_estimate?: number | null;
  surprise_pct?: number | null;
  revenue_beat_miss?: string | null;
  last_revenue_actual?: number | null;
  last_revenue_estimate?: number | null;
  revenue_surprise_pct?: number | null;
  data_available: boolean;
  message?: string | null;
};

export type QuarterlyMetric = {
  period: string;
  revenue?: number | null;
  eps?: number | null;
  revenue_qoq_pct?: number | null;
  revenue_yoy_pct?: number | null;
};

export type BalanceSheetQuarter = {
  period: string;
  total_debt?: number | null;
  total_equity?: number | null;
  cash?: number | null;
  debt_to_equity?: number | null;
  net_debt?: number | null;
  current_ratio?: number | null;
};

export type IncomeStatementQuarter = {
  period: string;
  revenue?: number | null;
  gross_profit?: number | null;
  operating_income?: number | null;
  net_income?: number | null;
  gross_margin_pct?: number | null;
  operating_margin_pct?: number | null;
  net_margin_pct?: number | null;
};

export type CashFlowQuarter = {
  period: string;
  operating_cash_flow?: number | null;
  capital_expenditure?: number | null;
  free_cash_flow?: number | null;
  fcf_margin_pct?: number | null;
};

export type MetricPercentiles = {
  p10?: number | null;
  p25?: number | null;
  p50?: number | null;
  p75?: number | null;
  p90?: number | null;
};

export type FundamentalBenchmark = {
  revenue_cagr_3y?: number | null;
  eps_trend?: "up" | "flat" | "down" | null;
  margin_vs_3y_avg_pct?: number | null;
  pe_vs_3y_median_pct?: number | null;
  median_pe_3y?: number | null;
  pe_percentiles?: MetricPercentiles | null;
  pe_current_percentile?: number | null;
  margin_percentiles?: MetricPercentiles | null;
  margin_current_percentile?: number | null;
  revenue_growth_percentiles?: MetricPercentiles | null;
  revenue_growth_current_percentile?: number | null;
  fcf_margin_percentiles?: MetricPercentiles | null;
  fcf_margin_current_percentile?: number | null;
  historical_pe_reliable?: boolean;
  revenue_growth_acceleration?: number | null;
  debt_trend?: "improving" | "stable" | "worsening" | null;
  benchmark_bullets: string[];
  data_available: boolean;
  message?: string | null;
};

export type SectorContext = {
  sector?: string | null;
  industry?: string | null;
  universe?: string | null;
  sector_pe_prior?: number | null;
  pe_vs_sector_prior_pct?: number | null;
  pe_forward_sector_percentile?: number | null;
  mos_sector_percentile?: number | null;
  sector_headline?: string | null;
  sector_bullets: string[];
  peer_count: number;
  data_available: boolean;
  message?: string | null;
};

export type ValuationMethodResult = {
  method: string;
  fair_value?: number | null;
  detail?: string | null;
  data_available: boolean;
  reliable_for_composite?: boolean;
};

export type DcfSensitivityPoint = {
  label: string;
  fair_value?: number | null;
};

export type FundValuationSnapshot = {
  quote_type?: string | null;
  expense_ratio?: number | null;
  total_assets?: number | null;
  nav_price?: number | null;
  premium_discount_pct?: number | null;
  top_holdings_pct?: number | null;
  fair_value_low?: number | null;
  fair_value_mid?: number | null;
  fair_value_high?: number | null;
  message?: string | null;
  data_available: boolean;
};

export type ValuationAssessment = {
  current_price?: number | null;
  fair_value_low?: number | null;
  fair_value_mid?: number | null;
  fair_value_high?: number | null;
  fair_value_stress_low?: number | null;
  fair_value_stress_high?: number | null;
  mos_pct?: number | null;
  mos_label?: "undervalued" | "fair" | "overvalued" | null;
  method_spread_pct?: number | null;
  confidence?: "high" | "medium" | "low" | null;
  methods: ValuationMethodResult[];
  dcf_fair_value?: number | null;
  dcf_implied_growth_at_price?: number | null;
  dcf_assumptions?: Record<string, number | string> | null;
  dcf_sensitivity: DcfSensitivityPoint[];
  margin_of_safety_met?: boolean | null;
  mos_buy_threshold_pct?: number | null;
  fund?: FundValuationSnapshot | null;
  is_fund: boolean;
  reliability_notes?: string[];
  data_gaps: string[];
  composite_drivers?: string[];
  composite_mode?: string | null;
  data_available: boolean;
  message?: string | null;
};

export type TechnicalAssessment = {
  current_price?: number | null;
  trend_label?: "bullish" | "bearish" | "neutral" | "mixed" | null;
  trend_summary?: string | null;
  short_term_trend?: "bullish" | "bearish" | "neutral" | "mixed" | null;
  mid_term_trend?: "bullish" | "bearish" | "neutral" | "mixed" | null;
  long_term_trend?: "bullish" | "bearish" | "neutral" | "mixed" | null;
  horizon_summary?: string | null;
  rsi_14?: number | null;
  macd?: { macd?: number; signal?: number; histogram?: number } | null;
  atr_14?: number | null;
  atr_pct?: number | null;
  sma_20?: number | null;
  sma_50?: number | null;
  sma_200?: number | null;
  price_vs_sma_20_pct?: number | null;
  price_vs_sma_50_pct?: number | null;
  range_52w_low?: number | null;
  range_52w_high?: number | null;
  range_position_pct?: number | null;
  support_level?: number | null;
  resistance_level?: number | null;
  macd_divergence?: "bullish" | "bearish" | "none" | null;
  signals: string[];
  data_gaps: string[];
  data_available: boolean;
  message?: string | null;
};

export type FundamentalAssessment = {
  quality_label?: "strong" | "adequate" | "weak" | "unavailable" | null;
  growth_label?: "bullish" | "bearish" | "neutral" | "mixed" | null;
  balance_sheet_label?: "bullish" | "bearish" | "neutral" | "mixed" | null;
  valuation_context_label?: "rich" | "fair" | "cheap" | "unavailable" | null;
  overall_label?: "favorable" | "neutral" | "caution" | "unavailable" | null;
  summary?: string | null;
  signals?: string[];
  highlights?: string[];
  data_gaps?: string[];
  data_available: boolean;
  message?: string | null;
};

export type RealityCheck = {
  overall_bias?: "constructive" | "cautious" | "mixed" | "unavailable" | null;
  confidence?: "high" | "medium" | "low" | null;
  headline?: string | null;
  key_catalysts?: string[];
  key_risks?: string[];
  invalidation_triggers?: string[];
  tensions?: string[];
  data_available: boolean;
  message?: string | null;
};

export type FundamentalsSnapshot = {
  sector?: string | null;
  industry?: string | null;
  quote_type?: string | null;
  market_cap?: number | null;
  pe_trailing?: number | null;
  pe_forward?: number | null;
  price_to_sales?: number | null;
  price_to_book?: number | null;
  profit_margin?: number | null;
  operating_margin?: number | null;
  revenue_growth?: number | null;
  earnings_growth?: number | null;
  roe?: number | null;
  debt_to_equity?: number | null;
  current_ratio?: number | null;
  total_cash?: number | null;
  total_debt?: number | null;
  free_cash_flow?: number | null;
  recommendation?: string | null;
  analyst_buy?: number | null;
  analyst_sell?: number | null;
  target_price?: number | null;
  target_upside_pct?: number | null;
  fifty_two_week_high?: number | null;
  fifty_two_week_low?: number | null;
  quarterly_trends: QuarterlyMetric[];
  balance_sheet_trends?: BalanceSheetQuarter[];
  income_statement_trends?: IncomeStatementQuarter[];
  cash_flow_trends?: CashFlowQuarter[];
  benchmark?: FundamentalBenchmark | null;
  fundamental_flags: string[];
  valuation_label?: string | null;
  trading_currency?: string | null;
  financial_currency?: string | null;
  fx_rate_financial_to_trading?: number | null;
  amounts_currency?: string | null;
  monetary_values_normalized?: boolean;
  trailing_eps_quote?: number | null;
  forward_eps_quote?: number | null;
  data_available: boolean;
  message?: string | null;
};

export type SecFilingHighlight = {
  form: string;
  filing_date: string;
  title?: string | null;
  url?: string | null;
  accession?: string | null;
  excerpt?: string | null;
  excerpt_available?: boolean;
  excerpt_chars?: number | null;
  event_items?: string[] | null;
};

export type SecFilingsFeed = {
  ticker: string;
  filings: SecFilingHighlight[];
  data_available: boolean;
  message?: string | null;
};

export type NotableInsiderTransaction = {
  filing_date: string;
  insider_name: string;
  transaction_type: string;
  shares?: number | null;
  price?: number | null;
  notional?: number | null;
  filing_url?: string | null;
  excerpt?: string | null;
  excerpt_available?: boolean;
};

export type InsiderFilingHighlight = {
  filing_date: string;
  insider_name: string;
  transaction_type: string;
  excerpt?: string | null;
  excerpt_available?: boolean;
  filing_url?: string | null;
};

export type ForwardOutlook = {
  next_earnings_date?: string | null;
  days_until_earnings?: number | null;
  analyst_target?: number | null;
  target_upside_pct?: number | null;
  recommendation?: string | null;
  revenue_growth?: number | null;
  earnings_growth?: number | null;
  watch_items: string[];
  outlook_bullets: string[];
  data_available: boolean;
};

export type InsiderSummary = {
  net_shares_90d: number;
  buy_count: number;
  sell_count: number;
  open_market_buy_count?: number;
  open_market_sell_count?: number;
  excluded_count?: number;
  cluster_buying?: boolean;
  sentiment: "accumulation" | "distribution" | "neutral";
  notable_transactions: NotableInsiderTransaction[];
  analysis_bullets: string[];
  data_available: boolean;
};

export type OptionsExpiryBreakdown = {
  expiry: string;
  call_volume: number;
  put_volume: number;
  put_call_ratio?: number | null;
  call_oi: number;
  put_oi: number;
};

export type OptionsStrikeVolume = {
  strike: number;
  side: "call" | "put";
  volume: number;
  open_interest: number;
};

export type OptionsFlowFlag = {
  put_call_ratio?: number | null;
  unusual: boolean;
  high_conviction?: boolean;
  institutional_grade?: boolean;
  conviction_band?: "short" | "swing" | "macro" | null;
  premium_total_usd?: number | null;
  message?: string | null;
  call_volume?: number | null;
  put_volume?: number | null;
  expiry?: string | null;
  expiry_breakdown?: OptionsExpiryBreakdown[];
  top_strikes?: OptionsStrikeVolume[];
  total_open_interest?: number | null;
  unusual_reason?: string | null;
  max_vol_oi_ratio?: number | null;
  otm_premium_total?: number | null;
  short_dated_premium_pct?: number | null;
};

export type SmartMoneyLayerScore = {
  layer: string;
  label: string;
  score: number;
  max_score: number;
  stance?: string | null;
  detail?: string | null;
};

export type SmartMoneyAssessment = {
  ticker: string;
  conviction_pct?: number | null;
  headline?: string | null;
  layers: SmartMoneyLayerScore[];
  calendar_notes?: string[];
  data_available: boolean;
};

export type TickerContext = {
  ticker: string;
  as_of: string;
  price?: number | null;
  change_pct?: number | null;
  market_state?: string | null;
  price_source?: string | null;
  previous_close?: number | null;
  regular_market_price?: number | null;
  extended_price?: number | null;
  is_extended_hours?: boolean;
  quote_as_of?: string | null;
  volume?: number | null;
  volume_avg_30d?: number | null;
  volume_ratio?: number | null;
  rsi?: number | null;
  macd?: { macd?: number; signal?: number; histogram?: number } | null;
  news: NewsItem[];
  news_digest?: NewsDigest | null;
  warnings: Warning[];
  fundamental_warnings?: Warning[];
  summary?: ContextSummary | null;
  price_history: { date: string; close: number }[];
  fundamentals?: FundamentalsSnapshot | null;
  sec_filings?: SecFilingsFeed | null;
  insider?: InsiderTimeline | null;
  insider_summary?: InsiderSummary | null;
  insider_filings?: InsiderFilingHighlight[];
  forward_outlook?: ForwardOutlook | null;
  earnings?: EarningsSnapshot | null;
  options_flow?: OptionsFlowFlag | null;
  macro_overlay?: MacroContextOverlay | null;
  valuation?: ValuationAssessment | null;
  technical_assessment?: TechnicalAssessment | null;
  fundamental_assessment?: FundamentalAssessment | null;
  reality_check?: RealityCheck | null;
  sector_context?: SectorContext | null;
  context_visuals?: ContextVisualSnapshot | null;
  smart_money_assessment?: SmartMoneyAssessment | null;
  institutional_13f?: Institutional13FChanges | null;
  activist_filing?: ActivistFeedItem | null;
};

export type DigestTickerRow = {
  ticker: string;
  price?: number | null;
  change_pct?: number | null;
  mos_pct?: number | null;
  mos_label?: string | null;
  fair_value_low?: number | null;
  fair_value_mid?: number | null;
  fair_value_high?: number | null;
  valuation_label?: string | null;
  pe_forward?: number | null;
  sector?: string | null;
  pe_sector_percentile?: number | null;
  top_warning?: string | null;
  earnings_days?: number | null;
  insider_sentiment?: string | null;
  macro_headline?: string | null;
  valuation_confidence?: string | null;
  one_liner?: string | null;
};

export type DigestToday = {
  as_of: string;
  trading_date: string;
  watchlist_name: string;
  tickers: DigestTickerRow[];
  empty_message?: string | null;
  digest_max_tickers?: number | null;
};

export type ScreenerRow = DigestTickerRow & { rank_score?: number | null };

export type ScreenerResult = {
  as_of: string;
  universe?: "watchlist" | "sp100" | "sp500";
  preset?: string | null;
  scanned_count?: number;
  rows: ScreenerRow[];
  empty_message?: string | null;
  cached_at?: string | null;
  stale?: boolean;
};

export type BackgroundJobStatus = {
  name: string;
  status: "idle" | "running" | "ok" | "error";
  label?: string | null;
  phase?: string | null;
  progress_completed?: number | null;
  progress_total?: number | null;
  last_run_at?: string | null;
  last_duration_ms?: number | null;
  last_error?: string | null;
  next_run_at?: string | null;
};

export type BackgroundJobsStatusResponse = {
  as_of: string;
  jobs: BackgroundJobStatus[];
  market_screener_scanned_count: number;
  background_jobs_enabled: boolean;
  warming?: boolean;
  active_job?: string | null;
  batch_position?: number | null;
  batch_total?: number | null;
};

export type SmartMoneyFeedItem = {
  ticker?: string | null;
  company_name?: string | null;
  filing_date: string;
  insider_name?: string | null;
  title?: string | null;
  transaction_type?: string | null;
  transaction_code?: string | null;
  shares?: number | null;
  price?: number | null;
  notional?: number | null;
  side: "buy" | "sell" | "other";
  filing_url?: string | null;
  is_notable: boolean;
  excerpt_available: boolean;
  is_open_market?: boolean;
  cluster_buying?: boolean;
  source_form?: "3" | "4" | "5";
  signal_type?: "transaction" | "insider_appointment" | "annual_reconciliation";
};

export type SmartMoneyFeedStats = {
  buy_count: number;
  sell_count: number;
  other_count: number;
  total_notional?: number | null;
  top_tickers: string[];
};

export type SmartMoneyFeed = {
  as_of: string;
  items: SmartMoneyFeedItem[];
  stats: SmartMoneyFeedStats;
  data_available: boolean;
  message?: string | null;
  days_window: number;
  start_date?: string | null;
  end_date?: string | null;
  raw_entry_count?: number;
  enriched_count?: number;
  parse_failed_count?: number;
  xml_attempt_count?: number;
  filtered_count?: number;
  sec_rate_limited?: boolean;
};

export type WatchlistInsiderPulseRow = {
  ticker: string;
  sentiment: "accumulation" | "distribution" | "neutral";
  net_shares_90d: number;
  buy_count: number;
  sell_count: number;
  open_market_buy_count?: number;
  cluster_buying?: boolean;
  latest_notable?: string | null;
  recent_transactions?: InsiderTransaction[];
  data_available: boolean;
};

export type WatchlistInsiderPulse = {
  as_of: string;
  watchlist_name: string;
  rows: WatchlistInsiderPulseRow[];
  data_available: boolean;
  message?: string | null;
};

export type OptionsScanRow = {
  ticker: string;
  put_call_ratio?: number | null;
  unusual: boolean;
  unusual_reason?: string | null;
  call_volume?: number | null;
  put_volume?: number | null;
  top_strike_summary?: string | null;
  unusual_contract_count?: number;
  max_vol_oi_ratio?: number | null;
  sweep_count?: number;
  data_source?: string;
};

export type ScanUniverse = "watchlist" | "sp100" | "sp500";

export type VolumeScanRow = {
  ticker: string;
  stance: "accumulation" | "distribution" | "neutral";
  obv_divergence?: string | null;
  ad_divergence?: string | null;
  vwap_deviation_pct?: number | null;
  volume_ratio?: number | null;
  quiet_accumulation?: boolean;
};

export type VolumeScanResult = {
  as_of: string;
  universe: ScanUniverse;
  rows: VolumeScanRow[];
  scanned_count: number;
  fetched_count?: number;
  data_available: boolean;
  message?: string | null;
  partial?: boolean;
  provider_degraded?: boolean;
};

export type ActivistFeedItem = {
  ticker?: string | null;
  company_name?: string | null;
  filing_date: string;
  form_type: "13D" | "13G";
  filer_name?: string | null;
  percent_owned?: number | null;
  is_activist: boolean;
  filing_url?: string | null;
  signal?: string | null;
};

export type Institutional13FChange = {
  filer_name: string;
  filer_cik: string;
  ticker: string;
  shares?: number | null;
  value_usd?: number | null;
  change_type: "new" | "increased" | "decreased" | "exit" | "held";
  prior_shares?: number | null;
  pct_change?: number | null;
  quarter_end?: string | null;
  quarter_note?: string | null;
  is_notable_filer?: boolean;
};

export type Institutional13FChanges = {
  ticker: string;
  as_of: string;
  changes: Institutional13FChange[];
  conviction_buy: boolean;
  crowding_score?: number | null;
  crowding_risk?: "low" | "medium" | "high" | null;
  holder_count?: number | null;
  holder_count_delta?: number | null;
  data_scope?: "full_universe" | "tracked_filers_only";
  data_available: boolean;
  message?: string | null;
  disclaimer?: string;
};

export type ActivistFeed = {
  as_of: string;
  items: ActivistFeedItem[];
  data_available: boolean;
  message?: string | null;
  days_window: number;
};

export type InstitutionalConvictionRow = {
  ticker: string;
  filer_count: number;
  holder_count?: number | null;
  holder_count_delta?: number | null;
  conviction_buy: boolean;
  top_filers?: string[];
  strongest_change?: string | null;
  headline_filer?: string | null;
  headline_pct_change?: number | null;
  headline_value_usd?: number | null;
  quarter_end?: string | null;
  filer_previews?: Array<{
    filer_name?: string;
    change_type?: string;
    pct_change?: number | null;
    shares?: number | null;
    prior_shares?: number | null;
    value_usd?: number | null;
    quarter_end?: string | null;
    quarter_note?: string | null;
  }>;
  filer_changes?: Institutional13FChange[];
};

export type InstitutionalConvictionScan = {
  as_of: string;
  universe?: ScanUniverse;
  rows: InstitutionalConvictionRow[];
  data_available: boolean;
  message?: string | null;
  filers_refreshed?: number;
  tickers_mapped?: number;
  data_scope?: "full_universe" | "tracked_filers_only";
  disclaimer?: string;
};

export type InsiderScanRow = {
  ticker: string;
  sentiment: "accumulation" | "distribution" | "neutral";
  buy_count: number;
  sell_count: number;
  cluster_buying: boolean;
  notable_buy_count: number;
  net_shares_90d?: number;
  open_market_buy_count?: number;
  latest_notable?: string | null;
  recent_transactions?: InsiderTransaction[];
  data_available: boolean;
};

export type InsiderScanResult = {
  as_of: string;
  universe: ScanUniverse;
  rows: InsiderScanRow[];
  scanned_count: number;
  fetched_count?: number;
  data_available: boolean;
  message?: string | null;
  partial?: boolean;
  provider_degraded?: boolean;
};

export type CotPositionRow = {
  symbol: string;
  market_name?: string | null;
  report_date?: string | null;
  commercial_net?: number | null;
  signal?: string | null;
  reversal_zone?: boolean;
};

export type CotReport = {
  as_of: string;
  positions: CotPositionRow[];
  data_available: boolean;
  message?: string | null;
  disclaimer?: string;
};

export type OptionsScanResult = {
  as_of: string;
  universe: ScanUniverse;
  rows: OptionsScanRow[];
  scanned_count: number;
  fetched_count?: number;
  data_available: boolean;
  message?: string | null;
  partial?: boolean;
  provider_degraded?: boolean;
  disclaimer: string;
};

export type InsiderTransaction = {
  filing_date: string;
  insider_name: string;
  title?: string | null;
  transaction_type: string;
  shares?: number | null;
  price?: number | null;
  filing_url?: string | null;
};

export type InsiderTimeline = {
  ticker: string;
  transactions: InsiderTransaction[];
  data_available?: boolean;
  message?: string | null;
};

export type RiskEvaluateResponse = {
  ticker: string;
  position_value: number;
  portfolio_pct: number;
  exceeds_risk_limit: boolean;
  risk_limit_pct: number;
  suggested_stop_loss?: number | null;
  suggested_position_size?: number | null;
  atr?: number | null;
  warnings: Warning[];
  derivative_note?: string | null;
};

export type MacroBriefing = {
  as_of: string;
  market_weather?: string | null;
  events: MacroEvent[];
  headline_events?: string[];
  sector_watch?: string[];
  watchlist_exposure?: string[];
  impact_summary?: { high: number; moderate: number; noise: number };
  sector_impacts: string[];
  impact_levels: { event: string; level: string }[];
  summary?: MacroSummary | null;
  data_gaps?: string[];
  empty_message?: string | null;
  macro_signals?: MacroSignalsSnapshot | null;
  macro_news?: NewsItem[];
  signal_highlights?: string[];
  release_stats?: MacroReleaseStats | null;
  trading_date?: string | null;
};

export type TradeJournalEntry = {
  id?: string | null;
  ticker: string;
  direction: string;
  quantity: number;
  entry_price: number;
  account_size: number;
  instrument_type: string;
  ai_warnings: string[];
  created_at?: string | null;
};

export type Watchlist = {
  name: string;
  tickers: string[];
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `API error ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function fetchContext(
  ticker: string,
  opts?: { summarize?: boolean; includeInsider?: boolean; includeOptions?: boolean }
) {
  const params = new URLSearchParams();
  if (opts?.summarize) params.set("summarize", "true");
  if (opts?.includeInsider) params.set("include_insider", "true");
  if (opts?.includeOptions) params.set("include_options", "true");
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<TickerContext>(`/api/v1/context/${ticker}${q}`);
}

export function summarizeContext(ticker: string) {
  return apiFetch<TickerContext>(`/api/v1/context/${ticker}/summarize`, {
    method: "POST",
  });
}

export function evaluateRisk(body: Record<string, unknown>) {
  return apiFetch<RiskEvaluateResponse>("/api/v1/risk/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchMacroBriefing(opts?: { refresh?: boolean }) {
  const q = opts?.refresh ? "?refresh=true" : "";
  return apiFetch<MacroBriefing>(`/api/v1/macro/briefing${q}`);
}

export function fetchInsider(ticker: string) {
  return apiFetch<InsiderTimeline>(`/api/v1/institutional/${ticker}/insider`);
}

export function fetchJournal() {
  return apiFetch<TradeJournalEntry[]>("/api/v1/journal");
}

export function saveJournal(entry: Omit<TradeJournalEntry, "id" | "created_at">) {
  return apiFetch<TradeJournalEntry>("/api/v1/journal", {
    method: "POST",
    body: JSON.stringify(entry),
  });
}

export function fetchWatchlist(name = "default") {
  return apiFetch<Watchlist>(`/api/v1/watchlists/${name}`);
}

export function updateWatchlist(tickers: string[], name = "default") {
  return apiFetch<Watchlist>(`/api/v1/watchlists/${name}`, {
    method: "PUT",
    body: JSON.stringify({ tickers }),
  });
}

export function patchWatchlistTickers(
  patch: { add?: string[]; remove?: string[] },
  name = "default"
) {
  return apiFetch<Watchlist>(`/api/v1/watchlists/${name}/tickers`, {
    method: "PATCH",
    body: JSON.stringify({
      add: patch.add ?? [],
      remove: patch.remove ?? [],
    }),
  });
}

export function fetchDigestToday(opts?: {
  summarize?: boolean;
  watchlist?: string;
  refresh?: boolean;
}) {
  const params = new URLSearchParams();
  if (opts?.summarize) params.set("summarize", "true");
  if (opts?.watchlist) params.set("watchlist", opts.watchlist);
  if (opts?.refresh) params.set("refresh", "true");
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<DigestToday>(`/api/v1/digest/today${q}`);
}

export function fetchScreenerWatchlist(opts?: {
  refresh?: boolean;
  preset?: string;
  mos_min?: number;
  mos_max?: number;
  pe_max?: number;
  valuation_label?: string;
  has_earnings_within_days?: number;
  insider_sentiment?: string;
  warning_any?: string;
}) {
  const params = new URLSearchParams();
  if (opts?.refresh) params.set("refresh", "true");
  if (opts?.preset) params.set("preset", opts.preset);
  if (opts?.mos_min != null) params.set("mos_min", String(opts.mos_min));
  if (opts?.mos_max != null) params.set("mos_max", String(opts.mos_max));
  if (opts?.pe_max != null) params.set("pe_max", String(opts.pe_max));
  if (opts?.valuation_label) params.set("valuation_label", opts.valuation_label);
  if (opts?.has_earnings_within_days != null) {
    params.set("has_earnings_within_days", String(opts.has_earnings_within_days));
  }
  if (opts?.insider_sentiment) params.set("insider_sentiment", opts.insider_sentiment);
  if (opts?.warning_any) params.set("warning_any", opts.warning_any);
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<ScreenerResult>(`/api/v1/screener/watchlist${q}`);
}

function screenerParams(opts?: {
  refresh?: boolean;
  preset?: string;
  mos_min?: number;
  mos_max?: number;
  pe_max?: number;
  valuation_label?: string;
  has_earnings_within_days?: number;
  insider_sentiment?: string;
  warning_any?: string;
}) {
  const params = new URLSearchParams();
  if (opts?.refresh) params.set("refresh", "true");
  if (opts?.preset) params.set("preset", opts.preset);
  if (opts?.mos_min != null) params.set("mos_min", String(opts.mos_min));
  if (opts?.mos_max != null) params.set("mos_max", String(opts.mos_max));
  if (opts?.pe_max != null) params.set("pe_max", String(opts.pe_max));
  if (opts?.valuation_label) params.set("valuation_label", opts.valuation_label);
  if (opts?.has_earnings_within_days != null) {
    params.set("has_earnings_within_days", String(opts.has_earnings_within_days));
  }
  if (opts?.insider_sentiment) params.set("insider_sentiment", opts.insider_sentiment);
  if (opts?.warning_any) params.set("warning_any", opts.warning_any);
  return params;
}

export function fetchScreenerMarket(opts?: {
  universe?: "sp100" | "sp500";
  refresh?: boolean;
  preset?: string;
  mos_min?: number;
  mos_max?: number;
  pe_max?: number;
  valuation_label?: string;
  has_earnings_within_days?: number;
  insider_sentiment?: string;
  warning_any?: string;
}) {
  const params = screenerParams(opts);
  if (opts?.universe) params.set("universe", opts.universe);
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<ScreenerResult>(`/api/v1/screener/market${q}`);
}

export function fetchJobStatus() {
  return apiFetch<BackgroundJobsStatusResponse>("/api/v1/jobs/status");
}

export function triggerJobsRefresh(scope: "all" | "digest" | "market" | "smart_money" | "watchlist" = "all") {
  const params = new URLSearchParams({ scope });
  return apiFetch<BackgroundJobsStatusResponse>(`/api/v1/jobs/refresh?${params}`, {
    method: "POST",
  });
}

export function fetchSmartMoneyFeed(opts?: {
  days?: number;
  start_date?: string;
  end_date?: string;
  side?: "all" | "buy" | "sell";
  notable_only?: boolean;
  min_notional?: number;
  open_market_only?: boolean;
  cluster_only?: boolean;
  form_type?: "4" | "3" | "5" | "all";
  refresh?: boolean;
}) {
  const params = new URLSearchParams();
  if (opts?.days != null) params.set("days", String(opts.days));
  if (opts?.start_date) params.set("start_date", opts.start_date);
  if (opts?.end_date) params.set("end_date", opts.end_date);
  if (opts?.side) params.set("side", opts.side);
  if (opts?.notable_only) params.set("notable_only", "true");
  if (opts?.min_notional != null) params.set("min_notional", String(opts.min_notional));
  if (opts?.open_market_only != null) params.set("open_market_only", String(opts.open_market_only));
  if (opts?.cluster_only) params.set("cluster_only", "true");
  if (opts?.form_type) params.set("form_type", opts.form_type);
  if (opts?.refresh) params.set("refresh", "true");
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<SmartMoneyFeed>(`/api/v1/smart-money/feed${q}`);
}

export function fetchWatchlistInsiderPulse(watchlist = "default") {
  const params = new URLSearchParams({ watchlist });
  return apiFetch<WatchlistInsiderPulse>(
    `/api/v1/smart-money/watchlist-pulse?${params}`
  );
}

export function fetchOptionsActivityScan(opts?: {
  universe?: ScanUniverse;
  watchlist?: string;
  signalsOnly?: boolean;
}) {
  const params = new URLSearchParams();
  if (opts?.universe) params.set("universe", opts.universe);
  if (opts?.watchlist) params.set("watchlist", opts.watchlist);
  if (opts?.signalsOnly === false) params.set("signals_only", "false");
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<OptionsScanResult>(`/api/v1/smart-money/options-scan${q}`);
}

export function fetchVolumeScan(opts?: {
  universe?: ScanUniverse;
  watchlist?: string;
  signalsOnly?: boolean;
}) {
  const params = new URLSearchParams();
  if (opts?.universe) params.set("universe", opts.universe);
  if (opts?.watchlist) params.set("watchlist", opts.watchlist);
  if (opts?.signalsOnly === false) params.set("signals_only", "false");
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<VolumeScanResult>(`/api/v1/smart-money/volume-scan${q}`);
}

export function fetchInsiderScan(opts?: { universe?: ScanUniverse }) {
  const params = new URLSearchParams();
  if (opts?.universe) params.set("universe", opts.universe);
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<InsiderScanResult>(`/api/v1/smart-money/insider-scan${q}`);
}

export function fetchActivistFeed(opts?: {
  days?: number;
  type?: "all" | "13d" | "13g";
  refresh?: boolean;
}) {
  const params = new URLSearchParams();
  if (opts?.days != null) params.set("days", String(opts.days));
  if (opts?.type) params.set("type", opts.type);
  if (opts?.refresh) params.set("refresh", "true");
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<ActivistFeed>(`/api/v1/smart-money/activist-feed${q}`);
}

export function fetchInstitutionalConviction(opts?: { universe?: ScanUniverse }) {
  const params = new URLSearchParams();
  if (opts?.universe) params.set("universe", opts.universe);
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<InstitutionalConvictionScan>(`/api/v1/smart-money/13f/conviction${q}`);
}

export function fetchCotReport(symbols = "ES,CL,GC,ZN") {
  const params = new URLSearchParams({ symbols });
  return apiFetch<CotReport>(`/api/v1/smart-money/cot?${params}`);
}

export type MicrostructureSnapshot = {
  as_of: string;
  gex?: {
    symbol: string;
    net_gex_usd?: number | null;
    regime?: string | null;
    data_source?: string;
    data_available?: boolean;
    message?: string | null;
  } | null;
  dix?: {
    ticker: string;
    short_volume_ratio?: number | null;
    elevated_dark_accumulation?: boolean;
    data_source?: string;
    data_available?: boolean;
    message?: string | null;
  } | null;
  conviction_multiplier?: number;
  notes?: string[];
};

export type CongressionalTrade = {
  politician: string;
  chamber?: string;
  ticker?: string | null;
  transaction_date?: string | null;
  disclosure_date?: string | null;
  transaction_type?: string | null;
  amount_range?: string | null;
  source_url?: string | null;
};

export type CongressionalFeed = {
  as_of: string;
  trades: CongressionalTrade[];
  days_window: number;
  data_source: string;
  data_available: boolean;
  message?: string | null;
};

export function fetchMicrostructure(symbol = "SPY") {
  const params = new URLSearchParams({ symbol });
  return apiFetch<MicrostructureSnapshot>(`/api/v1/smart-money/microstructure/gex?${params}`);
}

export function fetchCongressionalFeed(opts?: { days?: number; refresh?: boolean }) {
  const params = new URLSearchParams();
  if (opts?.days != null) params.set("days", String(opts.days));
  if (opts?.refresh) params.set("refresh", "true");
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<CongressionalFeed>(`/api/v1/smart-money/congressional-feed${q}`);
}

export type FundHoldingRow = {
  ticker?: string | null;
  cusip?: string | null;
  asset_category?: string | null;
  fair_value_usd?: number | null;
  pct_of_nav?: number | null;
};

export type FundHoldingsSnapshot = {
  fund_ticker: string;
  fund_cik?: string | null;
  fund_name?: string | null;
  report_date?: string | null;
  holdings: FundHoldingRow[];
  equity_pct?: number | null;
  fixed_income_pct?: number | null;
  derivatives_pct?: number | null;
  data_available: boolean;
  message?: string | null;
};

export function fetchFundHoldings(ticker: string) {
  return apiFetch<FundHoldingsSnapshot>(`/api/v1/smart-money/nport/${encodeURIComponent(ticker)}`);
}

export function fetchSmartMoneyAssessment(ticker: string) {
  return apiFetch<SmartMoneyAssessment>(`/api/v1/smart-money/assessment/${ticker}`);
}

export type StreamContextMessage = {
  status: string;
  step?: string;
  context?: TickerContext;
  message?: string;
};

export function streamContext(
  ticker: string,
  onMessage: (data: StreamContextMessage) => void,
  onError?: (message: string) => void
) {
  const params = new URLSearchParams({
    include_insider: "true",
    include_options: "true",
  });
  const es = new EventSource(
    `${API_BASE}/api/v1/context/${encodeURIComponent(ticker)}/stream?${params}`
  );
  es.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data) as StreamContextMessage);
    } catch {
      /* ignore malformed chunks */
    }
  };
  es.onerror = () => {
    onError?.("Stream connection failed");
    es.close();
  };
  return () => es.close();
}
