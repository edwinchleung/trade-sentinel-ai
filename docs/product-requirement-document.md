# Product Requirements Document (PRD)
**Product Name:** TradeSentinel AI  
**Document Version:** 1.2  
**Target Platform:** Local web application (runs on your PC via Docker)  
**Product Owner / Lead Engineer:** kklmfao  
**Date:** June 2026

---

## 1. Executive Summary
### 1.1 Product Vision
TradeSentinel AI is an AI-driven "Rationality Co-Pilot" for personal use. It bridges the information gap between retail trading and institutional analysis by synthesizing macro data, technical indicators, institutional footprints, and risk metrics into digestible, emotionless insights.

### 1.2 Deployment Model
**Personal local tool** — single operator on your own machine. Not multi-tenant SaaS. No user accounts or authentication. All services run via **Docker Compose** on localhost.

### 1.3 Problem Statement
Retail traders suffer from systemic disadvantages:
1. **Information Overload:** Inability to filter actionable news from market noise.
2. **Emotional Trading:** Vulnerability to FOMO, leading to buying at the top or panic-selling at the bottom.
3. **Lack of Risk Management:** Misunderstanding of complex derivatives (options, leveraged ETFs) and poor position sizing.
4. **Institutional Blind Spots:** Unawareness of "Smart Money" movements until the market has already reacted.

---

## 2. Goals & Objectives
* **Primary Goal:** Reduce impulsive trades by mandating an AI-assisted "Pre-Trade Reality Check" before you act.
* **Secondary Goal:** Provide institutional-grade macro and micro context within 10 seconds of querying a ticker.
* **Technical Goal:** Local-first architecture — infrastructure cost **$0 on your PC**; only external LLM API usage is billed.

---

## 3. Scope & Out-of-Scope
### In-Scope (V1.0–V1.3)
* AI-driven fundamental and news summarization (Finnhub when configured; **yfinance headlines fallback** otherwise).
* Technical indicator calculations (**RSI, MACD with UI + warning flags**, volume anomalies).
* Macroeconomic event aggregation with structured briefing output and sector mapping.
* SEC Form 4 insider tracking with **90-day signal aggregation**.
* Earnings snapshot (next report date, last surprise %) via yfinance/Finnhub.
* Options flow depth (multi-expiry P/C, OI, top strikes) via yfinance.
* Trade journal persisted in local PostgreSQL (Docker).
* **Smart Money Hub** — market-wide insider feed, 13F changes/holders, activist 13D/G, N-PORT fund holdings, options/volume scans, GEX proxy, dark pool, COT, congressional trades.
* **Watchlist digest and screener** — daily digest rows and filter presets for saved tickers and market universes.
* **Fair-value assessment** — composite fair band, margin of safety, optional DCF, ETF/fund path.

### Out-of-Scope
* **User authentication / login** — not required for personal use.
* **Multi-tenant accounts** — single user only.
* **Cloud production hosting** — optional; not part of core workflow.
* **Automated Trade Execution** — no brokerage connections.
* **Social sentiment scraping** — not planned.
* **Earnings call transcript RAG** — not planned.
* **Paid unusual-options flow APIs** — not planned (yfinance and bounded scans only).

---

## 4. Target Persona
**Primary: Personal power user (you)**
* Runs TradeSentinel on localhost during market hours.
* Uses Context Engine before FOMO trades and Risk Calculator before entries.
* Comfortable with Docker, `.env` API keys, and optional native dev (`uv` + `npm`).

---

## 5. Core Functional Requirements

### Epic 1: The Market Context Engine ("Anti-FOMO" Screener)
* **FR 1.1 Ticker Query Input:** User can input any US Equity ticker symbol.
* **FR 1.2 Real-Time Data Ingestion:** System fetches news, price, volume vs. 30-day average, RSI, MACD.
* **FR 1.3 AI Context Summarization:** LLM generates facts-grounded summary explaining current price action.
* **FR 1.4 Technical Warning Flags:** Alerts if RSI > 70 or < 30, volume irregular, MACD divergence (bullish/bearish via `TechnicalAssessment`), MACD cross, SMA50 distance, 52-week range extremes, or unusual options.
* **FR 1.5 Earnings Snapshot:** Next report date (Finnhub `/calendar/earnings` + yfinance calendar merge), days until, last EPS/revenue actual vs estimate, surprise %; partial data allowed with helper message when next date missing; optional fields show "—" in UI.
* **FR 1.6 Insider Signal Summary:** 90-day net buy/sell shares, buy/sell counts, sentiment (accumulation/distribution/neutral), notable transactions (>$1M notional) with optional Form 4 excerpt and filing link.
* **FR 1.7 Options Flow Depth:** Multi-expiry (up to 3) P/C ratios, open interest totals, top 5 strikes by volume, unusual-activity reason.
* **FR 1.8 LLM Facts Enrichment:** When available, earnings, insider_summary, insider_filings (excerpts), forward_outlook, and options_summary are included in LLM facts JSON.
* **FR 1.9 Expanded Summary:** 4–5 bullets covering primary driver, news/earnings, insider, options, and technicals (facts-grounded via `context_v2.txt`).
* **FR 1.10 Fundamentals Snapshot:** Valuation (P/E, P/S, P/B), margins, growth, balance sheet, analyst target, 4-quarter revenue/EPS trends; explicit "Data Unavailable" when missing.
* **FR 1.11 Historical Self-Benchmark:** Issuer-relative comparison vs own 3Y history — revenue CAGR, margin vs 3Y avg, P/E vs 3Y median (timezone-safe price alignment; forward/trailing PE fallbacks; ≥2 valid quarters), EPS trend, debt trend; `benchmark.message` when P/E history insufficient.
* **FR 1.12 SEC Filing Highlights:** Last 5 recent 8-K / 10-Q / 10-K filings with title, date, and SEC link; **bounded text excerpts** for the latest 8-K and latest 10-Q/10-K (cached 7 days) passed to the LLM catalyst bullet.
* **FR 1.13 Fundamental-First Summary:** When fundamentals available, LLM uses `context_v3.txt` (6–7 bullets: valuation, growth vs history, balance sheet, catalysts, insider/options with Form 4 excerpts, technical overlay, forward outlook); separate `fundamental_warnings` from technical warnings.
* **FR 1.14 Forward Outlook & Watchlist:** Deterministic `forward_outlook` (next earnings, analyst target/upside, growth, `watch_items`, `outlook_bullets`) from existing facts; UI "Outlook & watchlist" card; LLM bullet grounded in `forward_outlook` JSON only.
* **FR 1.15 Insider Form 4 Excerpts:** Top notable/recent Form 4 transactions get deterministic plain-English excerpts (cached 7 days); `insider_filings` in LLM facts; "Read excerpt" in UI (mirror SEC panel).
* **FR 1.16 Macro-Integrated Context:** Daily macro bundle (cached per ET date) merged into ticker context; sector-filtered `macro_overlay` on `TickerContext`; `macro_context` in LLM facts; `context_v4.txt` macro environment bullet; forward outlook macro watch items; Macro backdrop card on Context page with link to Briefing.
* **FR 1.17 Fair-Value Assessment:** Deterministic `ValuationAssessment` on `TickerContext` — headline fair band from composite-eligible methods only (analyst target, Graham-lite TTM EPS×capped P/E, 3Y **TTM** median P/E when reliable, optional 5-year DCF); FCF yield shown as diagnostic with dynamic required yield; distorted historical P/E excluded when median >2× forward or >60×; band uses trimmed median + IQR; premium vs fair mid `(price−mid)/mid`; `method_spread_pct` and confidence gated on spread; ETF/fund uses expense ratio and NAV premium (no equity DCF); `context_v5.txt` when valuation available; LLM returns `qualitative_analysis` paragraph, `section_labels` (stance + headline per bullet), and 6–8 sectional bullets; deterministic `context_visuals` (pillar strip + section cards with metric chips and sparklines); cache suffix `:v17` when v6 active (see FR 1.20).
* **FR 1.20 Technical Assessment:** Deterministic `TechnicalAssessment` on `TickerContext` from 1y daily OHLCV — Wilder RSI(14), MACD, SMA20/50/200, ATR, 52-week range position, 20-bar support/resistance, MACD divergence detection, composite and **short/mid/long horizon** trend labels; extended warnings (`MACD_*_DIVERGENCE`, `BELOW_SMA50`, `NEAR_52W_*`); `context_v6.txt` when valuation and technical assessment both available — LLM returns `technical_interpretation`; UI `TechnicalAssessmentCard`, price chart SMA overlays, technical vs options warning split.
* **FR 1.21 Session-Aware Quotes:** `market_data` resolves live price from yfinance `marketState` (PRE/REGULAR/POST/CLOSED) using `preMarketPrice`, `postMarketPrice`, or `regularMarketPrice`; `change_pct` vs `previousClose`; `TickerContext` exposes `market_state`, `price_source`, `is_extended_hours`, and session badge on Context page.
* **FR 1.22 News Digest & Sentiment:** Merge Finnhub + yfinance headlines (up to 12, deduped); optional article summaries (bounded fetch); deterministic rule-based `sentiment_label`/`themes` per item and aggregate `NewsDigest` on `TickerContext`; passed to LLM as `news_digest`.
* **FR 1.23 Pre-Trade Reality Check:** Deterministic `RealityCheck` synthesizes valuation, technical horizons, fundamental assessment, news digest, and warnings; `context_v7.txt` adds `scenario_bullets` (bull/base/bear) and `reality_check_narrative`; UI `RealityCheckCard` above valuation cards.
* **FR 1.24 Valuation v2 Reliability:** TTM FCF for DCF; conservative growth blend; analyst/DCF excluded from composite when spread or divergence is extreme; sector-aware MOS thresholds; `reliability_notes[]` on `ValuationAssessment`.
* **FR 1.25 Multi-Horizon Technical Trends:** `short_term_trend`, `mid_term_trend`, `long_term_trend`, and `horizon_summary` on `TechnicalAssessment`; shown on card and context visuals.
* **FR 1.26 FundamentalAssessment:** Deterministic quality/growth/balance/valuation-context labels, highlights, and signals from `FundamentalsSnapshot`; `fundamental_interpretation` in v7 LLM output; UI `FundamentalAssessmentCard`.
* **FR 1.27 Smart Money Hub (Market Feed):** `GET /api/v1/smart-money/feed` ingests SEC EDGAR Form 4 Atom index (market-wide recent filings), enriches with XML parse, filters by days/side/notable/min notional; `/smart-money` page **Market feed** tab; cache `SMART_MONEY_FEED_CACHE_MINUTES` (default 30).
* **FR 1.28 Smart Money Scan (Watchlist + Options):** `GET /api/v1/smart-money/watchlist-pulse` ranks watchlist insider sentiment; `GET /api/v1/smart-money/options-scan?universe=watchlist|sp100` runs bounded yfinance P/C scan; curated `sp100_universe.json`; Context page **Smart Money** section groups per-ticker insider + options with link to hub.
* **FR 1.18 Watchlist Digest:** `GET /api/v1/digest/today` builds lite rows for default watchlist (price, MOS, earnings days, insider sentiment, top warning) with daily cache and concurrency limits; `/digest` page auto-loads; home “Today” strip shows top rows.
* **FR 1.19 Watchlist Screener:** `GET /api/v1/screener/watchlist` filters watchlist by MOS, P/E, valuation label, earnings window, insider sentiment, warning code, and presets (`undervalued`, `earnings_week`, `insider_accumulation`, `high_risk`); `/screener` page with preset chips. Context page auto-analyzes when `?ticker=` is set (`?auto=0` to disable).

### Epic 2: Macro-Signal Synthesizer
* **FR 2.1 Economic Calendar Integration:** Daily macro events from Finnhub + `macro_schedule.json`.
* **FR 2.2 LLM Translation:** Plain-English sector impact summary via dedicated macro prompt.
* **FR 2.3 Noise Filtration:** High / Moderate / Noise impact levels with counts.
* **FR 2.4 Dedicated Macro LLM Prompt:** `macro_v1.txt` — no ticker/news language; macro-only rules.
* **FR 2.5 Event Enrichment:** Release time, prior/estimate/actual (Finnhub when available), keyword-based sector mapping.
* **FR 2.6 Structured Briefing Output:** `market_weather`, `headline_events[]`, `sector_watch[]`, optional `watchlist_exposure[]`, `impact_summary`.
* **FR 2.7 Briefing UI:** Impact filter tabs, event time column, source badge, refresh button, empty state (no fake fallback events).
* **FR 2.8 Watchlist-Aware Portfolio Impact:** Reads `/api/v1/watchlists/default`; maps tickers to sectors for exposure bullets.
* **FR 2.9 Macro Market Indicators:** yfinance snapshot (VIX, yields, dollar, oil, gold, SPY/QQQ/IWM, credit proxies) with 1d/5d changes, yield-curve spread, risk tone; optional FRED official series when `FRED_API_KEY` set.
* **FR 2.10 Multi-Source Macro News:** Aggregates Finnhub general news, yfinance SPY headlines, public RSS (Fed/BLS/NPR), optional NewsAPI; deduped `macro_news` on briefing and in LLM facts.
* **FR 2.11 Release Statistics:** Per-event `surprise_pct` and `beat_miss` when actual/estimate present; day-level `release_stats` aggregate.
* **FR 2.12 Briefing UI (signals):** Macro signals grid, market headlines, signal highlights, release columns (actual/estimate/prior/surprise), collapsible data gaps.

### Epic 3: Smart Money Hub & Institutional Footprint
* **FR 3.1 Insider Trading Feed (Form 4):** SEC EDGAR with XML parsing; market-wide feed at `/api/v1/smart-money/feed`.
* **FR 3.2 Options Flow Anomalies:** Extended yfinance analysis in Context Engine (Epic 1 FR 1.7) and universe scans at `/api/v1/smart-money/options-scan`.
* **FR 3.3 Insider Aggregation:** Deterministic 90-day summary surfaced in Context Engine and passed to LLM.
* **FR 3.4 13F Institutional Holdings:** Quarter-over-quarter changes and top holders from bulk-ingested 13F data (`/api/v1/smart-money/13f/*`).
* **FR 3.5 Activist Filings:** 13D/G alerts for significant ownership changes.
* **FR 3.6 N-PORT Fund Holdings:** Mutual fund / ETF holdings from SEC N-PORT bulk ingest.
* **FR 3.7 GEX / Dark Pool / COT:** Gamma exposure proxy, dark pool summary, and Commitments of Traders data.
* **FR 3.8 Congressional Trades:** Feed of disclosed congressional stock transactions (`/api/v1/smart-money/congressional-feed`).
* **FR 3.9 Per-Ticker Assessment:** Combined insider, 13F, activist, dark pool, and microstructure view (`/api/v1/smart-money/assessment/{ticker}`).

### Epic 4: Pre-Trade Risk Calculator (Trade Ticket)
* **FR 4.1 Trade Input Form:** Ticker, direction, quantity, price, account size.
* **FR 4.2 Position Sizing Logic:** Flags if position exceeds 2% of account equity.
* **FR 4.3 Derivative Risk Warning:** Theta decay / beta slippage for options and leveraged ETFs.
* **FR 4.4 Stop-Loss Generator:** ATR-based suggested stop-loss.

---

## 6. Non-Functional Requirements (NFRs)
* **Performance:** AI summaries within 5–10 seconds.
* **Accuracy (Zero Hallucination):** Facts-grounded prompts; "Data Unavailable" when facts are missing.
* **Reliability:** API fallbacks; Postgres cache for repeated queries (15 min TTL).
* **UX/UI:** Dark mode default, minimalist Bloomberg-inspired layout.

---

## 7. System Architecture & Tech Stack

### 7.1 Frontend
* **Framework:** Next.js 15 (App Router), TypeScript, Tailwind.
* **Charting:** Recharts for price history and options flow.

### 7.2 Backend
* **API Framework:** FastAPI (Python 3.11+).
* **LLM Orchestration:** LangChain chat with facts-grounded prompts (`context_v2.txt`, `macro_v1.txt`).
* **Runtime:** Docker container or local `uvicorn` for development.

### 7.3 Database & Data Sources
* **Database:** PostgreSQL 16 (Docker) — trade journal, context cache, watchlists.
* **Market Data APIs:** yfinance (primary), Finnhub (optional), SEC EDGAR (Form 4).

### 7.4 Local Infrastructure
* **Orchestration:** Docker Compose (`postgres`, `api`, `web`).
* **URLs:** http://localhost:3000 (web), http://localhost:8000 (API).

---

## 8. User Flow / Journey
1. **Morning:** Open Macro Briefing → read market weather, filter high-impact events, check watchlist exposure.
2. **FOMO trigger:** Enter ticker in Context Engine → earnings + insider + options + AI summary in ~10s.
3. **Risk check:** Use Risk Calculator → adjust size / stop-loss → optionally save to Trade Journal.

---

## 9. Development Roadmap

### Phase 1: MVP (Complete)
* FastAPI + Next.js, yfinance, Finnhub (optional), facts-grounded LLM summaries, context cache.

### Phase 2: Risk & Persistence (Complete)
* Pre-Trade Risk Calculator, trade journal in local PostgreSQL.

### Phase 3: Institutional & Macro (Complete)
* Macro briefing, EDGAR Form 4, options put/call chart on Context page.

### Phase 4: Local polish (Complete)
* Docker Compose, SSE streaming, runbook, CI pytest.

### Phase 5: Professional Context & Macro (Complete)
* Dedicated `macro_v1.txt` + structured MacroBriefing schema.
* Event sector mapping, watchlist exposure, briefing UI filters/refresh.
* Earnings service, insider aggregation, multi-expiry options depth.
* `context_v2.txt` with earnings/insider/options in LLM facts.
* EarningsCard, InsiderSignalPanel, enhanced OptionsFlowChart UI.

### Phase 6: Valuation, Screener & Smart Money Hub (Complete)
* Fair-value band, DCF, ETF/fund valuation path (`services/valuation/`).
* Watchlist digest and screener API/UI (`services/digest/`, `/digest`, `/screener`).
* Smart Money Hub with 13F, N-PORT, activist filings, GEX, dark pool, COT, congressional feed.
* Background scheduler with WebSocket progress updates.

---
**End of Document**
