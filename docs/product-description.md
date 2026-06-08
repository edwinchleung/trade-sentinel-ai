# TradeSentinel AI
**Institutional-Grade Clarity for the Retail Investor.**

### The Product Vision
In modern financial markets, the gap between retail traders and Wall Street institutions isn't just about access to data — it's about the ability to process it. Retail investors face massive information overload, complex macroeconomic shifts, and hidden institutional footprints, often leading to emotional decision-making, FOMO (Fear Of Missing Out), and inadequate risk management.

**TradeSentinel AI** is not a high-frequency trading algorithm or an automated execution bot. It is your **Rationality Co-Pilot** — an advanced, AI-driven analytical suite designed to level the playing field. By synthesizing real-time data points into actionable, emotionless insights, TradeSentinel AI empowers retail investors to trade with the discipline, context, and risk management of a quantitative hedge fund.

---

### Core Modules & Features

#### 1. Market Context Engine (`/context`)
Deep single-ticker due diligence. Visiting `/context?ticker=…` auto-runs analysis unless `?auto=0`.

*   **Real-Time Data Synthesis:** Fetches breaking news (Finnhub or yfinance), SEC Form 4 filings, earnings dates/surprises, deep fundamentals, recent 8-K/10-Q/10-K filings (with excerpts for the latest 8-K and quarterly report), and options chain metrics.
*   **Deep Fundamental Analysis:** Valuation grid (P/E, P/S, P/B), margins, growth, balance sheet, 4-quarter revenue/EPS trends, and **historical self-benchmark** (vs the company's own 3-year history — not sector peers).
*   **Fair-Value Assessment:** Model-based fair band (analyst target, FCF yield, Graham-lite, 3Y P/E median) with margin-of-safety % vs price; optional simplified DCF when FCF is positive; ETF/fund path shows expense ratio and NAV premium (no bogus equity DCF).
*   **Earnings Snapshot:** Next report date, days until earnings, last EPS vs estimate, surprise %, and revenue actual/estimate when available.
*   **Insider Signal Analysis:** 90-day net buy/sell flow, accumulation/distribution sentiment, and notable Form 4 transactions (not just raw filing links).
*   **Options Flow Deep Dive:** Multi-expiry put/call ratios, open interest, top strikes by volume, and unusual-activity flags beyond a single bar chart.
*   **The "Why" Summary:** Powered by facts-grounded LLMs, delivers fundamental-first bullet points (valuation vs own history, growth, balance sheet, catalysts) with insider/options and technical overlay subordinate.
*   **Fundamental & Technical Warnings:** Separate fundamental flags (elevated debt, valuation vs history, margin contraction) from technical RSI/MACD/volume alerts; technicals live in a collapsible panel below fundamentals.
*   **Reality Check:** Deterministic synthesis of valuation, technical horizons, news digest, and warnings into bull/base/bear scenario bullets.

#### 2. Smart Money Hub (`/smart-money`)
Follow institutional and insider activity across the market — not limited to a single ticker.

*   **Market-Wide Insider Feed:** SEC EDGAR Form 4 Atom index with XML parsing, filterable by days, side, notability, and minimum notional.
*   **13F Institutional Holdings:** Quarter-over-quarter changes, top holders, and conviction scans from bulk-ingested 13F data.
*   **Activist Filings:** 13D/G alerts for significant ownership changes.
*   **N-PORT Fund Holdings:** Mutual fund / ETF holdings from SEC N-PORT bulk data.
*   **Options & Volume Scans:** Bounded put/call scans across watchlist or S&P 100 universe.
*   **GEX / DIX Proxy:** Gamma exposure and dark-index estimates from options open interest.
*   **Dark Pool Summary:** Off-exchange volume proxy per ticker.
*   **COT Report:** Commitments of Traders positioning data.
*   **Congressional Trades:** Feed of disclosed congressional stock transactions.
*   **Per-Ticker Assessment:** Combined insider, 13F, activist, dark pool, and microstructure view for a single symbol.

#### 3. Watchlist Digest (`/digest`)
Proactive daily intelligence for every ticker you track.

*   **Auto-Loaded Table:** Price, margin of safety, earnings countdown, insider sentiment, and top warning for each watchlist ticker.
*   **Daily Cache:** Built by the background scheduler; refreshes without manual per-ticker clicks.
*   **Home Strip:** Top digest rows surface on the dashboard for at-a-glance morning review.

#### 4. Anti-FOMO Screener (`/screener`)
Filter your watchlist or market presets to find actionable setups.

*   **Filter Presets:** Undervalued, earnings week, insider accumulation, above fair band, high risk.
*   **Custom Filters:** MOS, P/E, valuation label, earnings window, insider sentiment, warning codes.
*   **Market Presets:** S&P 100 and S&P 500 universe scans in addition to watchlist.

#### 5. Macro-Signal Synthesizer (`/briefing`)
Stop drowning in a sea of economic calendars. TradeSentinel AI cuts through the noise of global macroeconomics.

*   **Market Weather Lead:** A one-sentence headline describing the day's macro tone (e.g. "Data-heavy session led by ISM Services PMI").
*   **Impact Summary:** Counts of high / moderate / noise events so you know how busy the day is at a glance.
*   **Per-Event Sector Playbooks:** Each high/moderate release mapped to affected sectors (Energy, Financials, Industrials, etc.) with a plain-English "why it matters."
*   **Headline Events:** Top 3 actionable catalysts highlighted separately from noise-level releases.
*   **Watchlist Exposure:** Maps your saved watchlist tickers to sectors most affected by today's macro calendar.
*   **Noise Filtration:** Filter the event table to High only, High+Moderate, or All — with release times and data source badges.
*   **Macro Market Indicators:** VIX, yields, dollar, oil, gold, major indices with 1d/5d changes and yield-curve spread.

#### 6. Pre-Trade Risk & Reality Check (`/risk`)
Institutions have Chief Risk Officers; you have TradeSentinel AI. Before executing a trade on your brokerage, run it through the Reality Check protocol.

*   **Derivative & Leverage Warning:** Planning to buy a 3x Leveraged ETF or short-term options? The system calculates and explains hidden risks in plain English, visualizing Theta decay, implied volatility crush, and beta slippage.
*   **Position Sizing & Stop-Loss Architect:** Based on your overall portfolio size and historical volatility (ATR) of the asset, the system recommends mathematically sound position sizing and logical stop-loss levels to ensure one bad trade doesn't ruin your portfolio.
*   **Journal Integration:** Completed risk checks can be saved to the trade journal for later review.

#### 7. Trade Journal (`/journal`)
Persisted history of pre-trade risk evaluations. Review past decisions, compare sizing recommendations, and build discipline over time.

#### 8. Watchlist Manager (`/watchlist`)
CRUD for saved tickers. The default watchlist drives digest, screener, macro exposure mapping, and smart-money watchlist pulse.

---

### Why Choose TradeSentinel AI?

*   **Eradicate Emotional Trading:** By forcing a "pause" to consult the AI, you replace FOMO and panic with data-driven logic.
*   **Save Thousands of Hours:** No need to read dense SEC filings or cross-reference dozens of news articles. Get structured analysis in under 10 seconds.
*   **Avoid Hidden Traps:** Safely navigate complex financial instruments (options, futures, leveraged products) with a tool that calculates the exact downside risk *before* your capital is deployed.
*   **Affordable Power:** Built using modern LLMs and free financial APIs (yfinance, EDGAR, optional Finnhub), offering enterprise-grade analytics without the Bloomberg Terminal price tag.
*   **Privacy-First:** Runs locally on your machine. No accounts, no cloud hosting required.

---

### Under the Hood (Technical Architecture)
TradeSentinel AI is built for speed, accuracy, and robust data processing:

*   **Deployment:** Runs on **your machine via Docker Compose** (Next.js + FastAPI + PostgreSQL) — not a hosted cloud service. No login required for personal use.
*   **Intelligence:** Facts-grounded LLM prompts with dedicated macro and context templates; structured JSON in-context (not vector RAG).
*   **Data Ingestion:** SEC EDGAR (Form 4, 8-K/10-Q/10-K, 13F, 13D/G, N-PORT), yfinance (price, options, earnings), optional Finnhub (news, economic calendar), optional FRED (official macro series).
*   **Background Scheduler:** Warms digest, screener, and smart-money caches on interval; pushes progress to the UI via WebSocket.
*   **Modular Services:** Domain-split FastAPI packages (`context/`, `valuation/`, `sec/`, `smart_money/`, `macro/`, `scheduler/`, `storage/`) with 67+ pytest modules and GitHub Actions CI.
*   **Interface:** A clean, zero-clutter dashboard built for focus. No flashing lights, no gamification — just pure, distilled financial intelligence.

See [architecture.md](architecture.md) for the full engineering walkthrough.

### The Bottom Line
In the modern market, whoever has the clearest context wins. Let the algorithms fight over microseconds. **TradeSentinel AI** equips you with the ultimate retail advantage: Patience, Context, and Unbreakable Risk Management.

*Trade Smart. Trade Safe. Trade with Sentinel.*
