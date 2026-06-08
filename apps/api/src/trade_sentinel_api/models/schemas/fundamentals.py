from typing import Literal

from pydantic import BaseModel, Field

from trade_sentinel_api.models.schemas.valuation import FundValuationSnapshot


class EarningsSnapshot(BaseModel):
    next_report_date: str | None = None
    days_until: int | None = None
    last_eps_actual: float | None = None
    last_eps_estimate: float | None = None
    surprise_pct: float | None = None
    revenue_beat_miss: str | None = None
    last_revenue_actual: float | None = None
    last_revenue_estimate: float | None = None
    revenue_surprise_pct: float | None = None
    data_available: bool = False
    message: str | None = None


class QuarterlyMetric(BaseModel):
    period: str
    revenue: float | None = None
    eps: float | None = None
    revenue_qoq_pct: float | None = None
    revenue_yoy_pct: float | None = None


class BalanceSheetQuarter(BaseModel):
    period: str
    total_debt: float | None = None
    total_equity: float | None = None
    cash: float | None = None
    debt_to_equity: float | None = None
    net_debt: float | None = None
    current_ratio: float | None = None


class IncomeStatementQuarter(BaseModel):
    period: str
    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    gross_margin_pct: float | None = None
    operating_margin_pct: float | None = None
    net_margin_pct: float | None = None


class CashFlowQuarter(BaseModel):
    period: str
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    free_cash_flow: float | None = None
    fcf_margin_pct: float | None = None


class MetricPercentiles(BaseModel):
    p10: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p90: float | None = None


class FundamentalBenchmark(BaseModel):
    revenue_cagr_3y: float | None = None
    eps_trend: Literal["up", "flat", "down"] | None = None
    margin_vs_3y_avg_pct: float | None = None
    pe_vs_3y_median_pct: float | None = None
    median_pe_3y: float | None = None
    pe_percentiles: MetricPercentiles | None = None
    pe_current_percentile: float | None = None
    margin_percentiles: MetricPercentiles | None = None
    margin_current_percentile: float | None = None
    revenue_growth_percentiles: MetricPercentiles | None = None
    revenue_growth_current_percentile: float | None = None
    fcf_margin_percentiles: MetricPercentiles | None = None
    fcf_margin_current_percentile: float | None = None
    historical_pe_reliable: bool = True
    revenue_growth_acceleration: float | None = None
    debt_trend: Literal["improving", "stable", "worsening"] | None = None
    benchmark_bullets: list[str] = Field(default_factory=list)
    data_available: bool = False
    message: str | None = None


class FundamentalsSnapshot(BaseModel):
    sector: str | None = None
    industry: str | None = None
    quote_type: str | None = None
    market_cap: float | None = None
    pe_trailing: float | None = None
    pe_forward: float | None = None
    price_to_sales: float | None = None
    price_to_book: float | None = None
    profit_margin: float | None = None
    operating_margin: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    total_cash: float | None = None
    total_debt: float | None = None
    free_cash_flow: float | None = None
    ebitda: float | None = None
    enterprise_value: float | None = None
    payout_ratio: float | None = None
    recommendation: str | None = None
    analyst_buy: int | None = None
    analyst_sell: int | None = None
    target_price: float | None = None
    target_price_low: float | None = None
    target_price_high: float | None = None
    target_source: str | None = None
    target_upside_pct: float | None = None
    shares_outstanding: float | None = None
    ttm_revenue: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    quarterly_trends: list[QuarterlyMetric] = Field(default_factory=list)
    balance_sheet_trends: list[BalanceSheetQuarter] = Field(default_factory=list)
    income_statement_trends: list[IncomeStatementQuarter] = Field(default_factory=list)
    cash_flow_trends: list[CashFlowQuarter] = Field(default_factory=list)
    benchmark: FundamentalBenchmark | None = None
    fundamental_flags: list[str] = Field(default_factory=list)
    valuation_label: str | None = None
    fund_valuation: FundValuationSnapshot | None = None
    trading_currency: str | None = None
    financial_currency: str | None = None
    fx_rate_financial_to_trading: float | None = None
    amounts_currency: str | None = None
    monetary_values_normalized: bool = False
    trailing_eps_quote: float | None = None
    forward_eps_quote: float | None = None
    data_available: bool = False
    message: str | None = None

