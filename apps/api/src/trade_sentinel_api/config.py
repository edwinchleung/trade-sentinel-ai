from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class LlmSettings(BaseModel):
    provider: str = "openrouter"
    model: str = "openai/gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    dashscope_api_key: str = ""


class ValuationSettings(BaseModel):
    composite_mode: str = "iqr"
    include_dcf: bool = True
    mos_tech_over: float = 15.0
    mos_tech_under: float = -15.0
    mos_defensive_over: float = 8.0
    mos_defensive_under: float = -8.0
    mos_default_over: float = 10.0
    mos_default_under: float = -10.0
    mos_buy_threshold_pct: float = 25.0


class SmartMoneySettings(BaseModel):
    feed_cache_minutes: int = 30
    feed_default_days: int = 1
    feed_max_range_days: int = 30
    scan_concurrency: int = 3
    options_cache_minutes: int = 60
    open_market_only: bool = True
    f13_cache_hours: int = 24
    cot_cache_hours: int = 168
    volume_cache_minutes: int = 60
    proactive_universe: str = "sp500"
    sp500_cache_minutes: int = 120


class SecSettings(BaseModel):
    bulk_13f_enabled: bool = True
    bulk_nport_enabled: bool = True
    bulk_nport_background_enabled: bool = False
    bulk_nport_fund_ciks: str = ""
    bulk_data_dir: str = "data/sec_bulk"
    retry_max: int = 3
    retry_base_seconds: int = 2
    cik_failure_ttl_seconds: int = 120
    requests_per_second: float = 8.0
    request_min_interval_ms: int = 120
    job_gap_seconds: int = 5
    submissions_cache_seconds: int = 3600
    failure_cache_seconds: int = 120
    user_name: str = "TradeSentinelAI"
    user_email: str = "tradesentinel@example.com"
    access_mode: str = "CAUTION"
    current_page_size: int = 100
    feed_max_entries: int = 200
    generic_text_cap: int = 4000
    registry_cache_minutes: int = 30
    registry_warm_enabled: bool = False
    enabled_forms: str = ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    ollama_base_url: str = "http://localhost:11434"
    dashscope_api_key: str = ""
    finnhub_api_key: str = ""
    fred_api_key: str = ""
    newsapi_key: str = ""
    macro_news_limit: int = 12
    macro_trading_timezone: str = "America/New_York"
    macro_vix_elevated_threshold: float = 20.0
    llm_provider: str = "openrouter"
    llm_model: str = "openai/gpt-4o-mini"
    cache_ttl_seconds: int = 900
    digest_max_tickers: int = 20
    digest_concurrency: int = 3
    valuation_composite_mode: str = "iqr"
    valuation_include_dcf: bool = True
    valuation_mos_tech_over: float = 15.0
    valuation_mos_tech_under: float = -15.0
    valuation_mos_defensive_over: float = 8.0
    valuation_mos_defensive_under: float = -8.0
    valuation_mos_default_over: float = 10.0
    valuation_mos_default_under: float = -10.0
    valuation_mos_buy_threshold_pct: float = 25.0
    smart_money_feed_cache_minutes: int = 30
    smart_money_feed_default_days: int = 1
    smart_money_feed_max_range_days: int = 30
    smart_money_scan_concurrency: int = 3
    smart_money_options_cache_minutes: int = 60
    smart_money_open_market_only: bool = True
    smart_money_13f_cache_hours: int = 24
    smart_money_cot_cache_hours: int = 168
    smart_money_volume_cache_minutes: int = 60
    smart_money_proactive_universe: str = "sp500"
    smart_money_sp500_cache_minutes: int = 120
    options_pc_bullish_max: float = 0.70
    options_pc_fear_min: float = 0.90
    options_vol_oi_unusual: float = 3.0
    options_vol_oi_high: float = 5.0
    options_min_premium_usd: float = 500_000.0
    polygon_api_key: str = ""
    sec_bulk_13f_enabled: bool = True
    sec_bulk_nport_enabled: bool = True
    sec_bulk_nport_background_enabled: bool = False
    sec_bulk_nport_fund_ciks: str = ""
    sec_bulk_data_dir: str = "data/sec_bulk"
    squeezemetrics_api_key: str = ""
    unusual_whales_api_key: str = ""
    congressional_trades_api_key: str = ""
    congressional_trades_provider: str = "capitol_trades"
    polygon_options_ticks_enabled: bool = True
    gex_compute_enabled: bool = True
    dix_finra_proxy_enabled: bool = True
    market_screener_cache_minutes: int = 60
    market_screener_universe: str = "sp500"
    background_jobs_enabled: bool = True
    background_startup_warm: bool = True
    websocket_enabled: bool = True
    background_refresh_interval_minutes: int = 30
    background_scan_workers: int = 4
    background_watchlist_debounce_seconds: int = 15
    yfinance_batch_chunk_size: int = 25
    yfinance_chunk_delay_seconds: float = 1.0
    yfinance_job_cooldown_seconds: float = 15.0
    scan_failure_cache_seconds: int = 120
    yfinance_quiet_logs: bool = True
    sec_retry_max: int = 3
    sec_retry_base_seconds: int = 2
    sec_cik_failure_ttl_seconds: int = 120
    sec_requests_per_second: float = 8.0
    sec_request_min_interval_ms: int = 120
    sec_job_gap_seconds: int = 5
    sec_submissions_cache_seconds: int = 3600
    sec_failure_cache_seconds: int = 120
    cors_origins: str = "http://localhost:3000"
    database_url: str = ""
    postgres_user: str = "tradesentinel"
    postgres_password: str = "tradesentinel"
    postgres_db: str = "tradesentinel"
    sec_user_name: str = "TradeSentinelAI"
    sec_user_email: str = "tradesentinel@example.com"
    edgar_access_mode: str = "CAUTION"
    edgar_current_page_size: int = 100
    edgar_feed_max_entries: int = 200
    edgar_generic_text_cap: int = 4000
    edgar_registry_cache_minutes: int = 30
    edgar_registry_warm_enabled: bool = False
    edgar_enabled_forms: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sec_user_agent(self) -> str:
        return f"{self.sec_user_name} {self.sec_user_email}"

    @property
    def llm_provider_normalized(self) -> str:
        return self.llm_provider.strip().lower()

    def resolved_llm_api_key(self) -> str:
        return self.llm_api_key or self.openai_api_key

    def effective_base_url(self, provider: str | None = None) -> str:
        p = (provider or self.llm_provider_normalized).lower()
        if self.llm_base_url:
            return self.llm_base_url
        if p in ("openrouter", "openai_compatible"):
            return "https://openrouter.ai/api/v1"
        if p == "dashscope":
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"
        return ""

    @property
    def llm(self) -> LlmSettings:
        return LlmSettings(
            provider=self.llm_provider,
            model=self.llm_model,
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            ollama_base_url=self.ollama_base_url,
            openai_api_key=self.openai_api_key,
            anthropic_api_key=self.anthropic_api_key,
            dashscope_api_key=self.dashscope_api_key,
        )

    @property
    def valuation(self) -> ValuationSettings:
        return ValuationSettings(
            composite_mode=self.valuation_composite_mode,
            include_dcf=self.valuation_include_dcf,
            mos_tech_over=self.valuation_mos_tech_over,
            mos_tech_under=self.valuation_mos_tech_under,
            mos_defensive_over=self.valuation_mos_defensive_over,
            mos_defensive_under=self.valuation_mos_defensive_under,
            mos_default_over=self.valuation_mos_default_over,
            mos_default_under=self.valuation_mos_default_under,
            mos_buy_threshold_pct=self.valuation_mos_buy_threshold_pct,
        )

    @property
    def smart_money(self) -> SmartMoneySettings:
        return SmartMoneySettings(
            feed_cache_minutes=self.smart_money_feed_cache_minutes,
            feed_default_days=self.smart_money_feed_default_days,
            feed_max_range_days=self.smart_money_feed_max_range_days,
            scan_concurrency=self.smart_money_scan_concurrency,
            options_cache_minutes=self.smart_money_options_cache_minutes,
            open_market_only=self.smart_money_open_market_only,
            f13_cache_hours=self.smart_money_13f_cache_hours,
            cot_cache_hours=self.smart_money_cot_cache_hours,
            volume_cache_minutes=self.smart_money_volume_cache_minutes,
            proactive_universe=self.smart_money_proactive_universe,
            sp500_cache_minutes=self.smart_money_sp500_cache_minutes,
        )

    @property
    def sec(self) -> SecSettings:
        return SecSettings(
            bulk_13f_enabled=self.sec_bulk_13f_enabled,
            bulk_nport_enabled=self.sec_bulk_nport_enabled,
            bulk_nport_background_enabled=self.sec_bulk_nport_background_enabled,
            bulk_nport_fund_ciks=self.sec_bulk_nport_fund_ciks,
            bulk_data_dir=self.sec_bulk_data_dir,
            retry_max=self.sec_retry_max,
            retry_base_seconds=self.sec_retry_base_seconds,
            cik_failure_ttl_seconds=self.sec_cik_failure_ttl_seconds,
            requests_per_second=self.sec_requests_per_second,
            request_min_interval_ms=self.sec_request_min_interval_ms,
            job_gap_seconds=self.sec_job_gap_seconds,
            submissions_cache_seconds=self.sec_submissions_cache_seconds,
            failure_cache_seconds=self.sec_failure_cache_seconds,
            user_name=self.sec_user_name,
            user_email=self.sec_user_email,
            access_mode=self.edgar_access_mode,
            current_page_size=self.edgar_current_page_size,
            feed_max_entries=self.edgar_feed_max_entries,
            generic_text_cap=self.edgar_generic_text_cap,
            registry_cache_minutes=self.edgar_registry_cache_minutes,
            registry_warm_enabled=self.edgar_registry_warm_enabled,
            enabled_forms=self.edgar_enabled_forms,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
