# Product Development Plan (PDP)
**Product Name:** TradeSentinel AI  
**Development Methodology:** Agile (personal project)  
**Deployment:** Local PC via Docker Compose  
**Target Cost:** LLM API usage only (~$5–15/month); **$0 local infrastructure**

---

## 1. Executive Summary
This plan covers building and maintaining TradeSentinel AI as a **personal productivity tool** on your own computer. The stack is **Next.js + FastAPI + PostgreSQL in Docker**. There is no commercial launch timeline, no user authentication, and no required cloud hosting.

---

## 2. Technology Stack & Infrastructure

* **Frontend:** Next.js 15 (App Router), TypeScript, Tailwind — dark mode default.
* **Backend:** FastAPI (Python) — async data fetching, LangChain facts-grounded prompts.
* **Database:** PostgreSQL 16 in Docker — journal, LLM context cache, watchlists.
* **Cache:** Postgres `context_cache` table + in-memory L1 (15 min TTL).
* **LLM:** OpenRouter (default), Ollama, DashScope, OpenAI / Anthropic via `.env` (see [llm-providers.md](llm-providers.md)).
* **Data:** `yfinance` (primary), SEC EDGAR, Finnhub (optional — news, calendar, earnings).
* **DevOps:** Docker Compose only; Git optional for version control.

### Local setup (primary workflow)

```bash
cp .env.example .env   # add LLM_API_KEY; optional FINNHUB_API_KEY
docker compose up --build
```

* Web: http://localhost:3000  
* API: http://localhost:8000 (docs at `/docs`)

---

## 3. Development Roadmap

### Phase 1: Foundation & Market Context Engine (Complete)
* FastAPI + Next.js monorepo, yfinance + Finnhub news, RSI/MACD warnings, facts-grounded LLM.

### Phase 2: Risk & Trade Journal (Complete)
* Pre-Trade Risk Calculator, journal in Postgres.

### Phase 3: Macro & Institutional Data (Complete)
* Macro briefing page, Form 4 XML parsing, options P/C chart.

### Phase 4: Local polish & reliability (Complete)
* Docker Compose stack, SSE streaming, runbook, CI pytest.

### Phase 5: Professional Context & Macro (Complete)

### Phase 6: Valuation, Screener & Proactive Delivery (Complete)

**Goal:** Intrinsic-style fair-value bands, less manual clicking, in-app digest and watchlist screener.

#### Milestone 6A — Fair-value Lite + automation
| Task | Files |
|------|-------|
| Valuation service | `services/valuation/`, `models/schemas/valuation.py` |
| Context builder + prompt v5+ | `services/context/builder.py`, `prompts/context_v5.txt`, `warnings.py` (TTM P/E, trimmed fair band) |
| ValuationCard + auto-analyze | `ValuationCard.tsx`, `context/page.tsx` |
| Digest + screener API/UI | `services/digest/`, `routers/digest.py`, `digest/page.tsx`, `screener/page.tsx` |
| Home today strip | `page.tsx`, `Nav.tsx` |

**Acceptance:** Valuation card on context; `/context?ticker=X` auto-runs; digest/screener pages load watchlist without per-ticker Analyze.

#### Milestone 6B — DCF + ETF
| Task | Files |
|------|-------|
| Optional DCF + sensitivity | `services/valuation/assessment.py` (assumptions derived from fundamentals + ^TNX) |
| ETF/fund card variant | `services/valuation/`, `services/fundamentals.py`, `ValuationCard.tsx` |

**Acceptance:** DCF only when FCF > 0; ETFs show fund metrics without equity DCF.

#### Milestone 6C — Smart Money Hub expansion
| Task | Files |
|------|-------|
| 13F / N-PORT bulk ingest | `scripts/ingest_sec_13f_bulk.py`, `scripts/ingest_sec_nport_bulk.py`, `services/sec/` |
| Hub endpoints + UI | `routers/smart_money.py`, `services/smart_money/`, `smart-money/page.tsx` |
| Congressional / COT / GEX | `services/congressional_trades.py`, `services/smart_money/` |

**Acceptance:** `/smart-money` page loads market feed, 13F, scans, and per-ticker assessment; background scheduler warms caches.

---

### Phase 5: Professional Context & Macro (reference)

**Goal:** Transform generic summaries into structured, professional analysis using dedicated prompts and enriched data layers.

#### Milestone 5A — Macro Signal Briefing
| Task | Files |
|------|-------|
| Dedicated macro prompt | `apps/api/prompts/macro_v1.txt` |
| `summarize_macro()` | `services/llm.py`, `services/macro.py` |
| Event sector map | `apps/api/data/event_sector_map.json`, `services/macro_calendar.py` |
| Structured schema | `models/schemas.py` (MacroEvent, MacroBriefing) |
| Watchlist exposure | `services/macro.py` + watchlist service |
| Briefing UI overhaul | `apps/web/src/app/briefing/page.tsx`, `lib/api.ts` |

**Acceptance:** Briefing names top 3 actionable events, shows impact counts, maps watchlist sectors — no "news unavailable" or ticker language.

#### Milestone 5B — Market Context Engine
| Task | Files |
|------|-------|
| Earnings snapshot | `services/earnings.py`, schemas |
| Insider aggregation | `services/edgar.py` (summarize_insider_activity) |
| Options depth | `services/options_flow.py` (multi-expiry, OI, strikes) |
| Context v2 prompt + facts | `prompts/context_v2.txt`, `services/context/builder.py`, `routers/context.py` |
| UI components | `EarningsCard.tsx`, `InsiderSignalPanel.tsx`, `OptionsFlowChart.tsx`, `context/page.tsx` |

**Acceptance:** Context page shows earnings card, insider sentiment panel, enhanced options section; LLM bullets reference earnings/insider/options when data present.

#### Milestone 5.5 — Fundamental Analysis Enhancement
| Task | Files |
|------|-------|
| Fundamentals service + self-benchmark | `services/fundamentals.py` |
| SEC filing highlights | `services/sec_filings.py`, `services/edgar.py` (CIK export) |
| Schemas + context v3 | `models/schemas/context.py`, `services/context/builder.py`, cache `:v3` |
| Fundamental warnings + prompt | `services/warnings.py`, `prompts/context_v3.txt`, `services/llm.py` |
| UI restructure | `FundamentalsCard.tsx`, `SecFilingsPanel.tsx`, `context/page.tsx` |
| Tests + docs | `test_fundamentals.py`, `test_fundamental_benchmark.py`, `test_sec_filings.py`, PRD FR 1.10–1.13 |

**Acceptance:** Fundamentals card with 4Q trends and "Vs own history" panel above collapsible technicals; AI summary leads with valuation/growth vs history when data available.

#### Milestone 5C — Tests & polish
* Extend `test_macro.py`, add `test_earnings.py`, context smoke tests.
* Update `docs/runbook.md` for macro refresh and empty calendar.
* Context cache key bump to `v3` suffix (fundamentals + SEC filings).

**Data-source constraints:** yfinance primary (free); Finnhub optional enrichment for calendar actuals/estimates and earnings history.

---

## 4. Resource Allocation & Budget

| Resource | Purpose | Cost |
| :--- | :--- | :--- |
| **Docker / PostgreSQL** | Local DB + app runtime | Free |
| **OpenRouter / Ollama / DashScope** | LLM API | Usage-based or $0 |
| **yfinance, SEC EDGAR** | Market data | Free |
| **Finnhub** | News, calendar, earnings (optional) | Free tier |
| **Total local infra** | | **$0** |

---

## 5. Risk Management & Mitigation

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **LLM Hallucinations** | High | Facts-grounded prompts; raw data panels alongside AI bullets |
| **API Rate Limiting** | Medium | Postgres cache + in-memory L1; graceful empty states |
| **High Latency** | Medium | `asyncio.gather`; optional SSE stream |
| **Scope Creep** | High | Out-of-scope items documented in PRD (sentiment, transcripts, paid flow APIs) |

---

## 6. Success Metrics (Personal Use)
1. **Latency:** Complete context summary in under 10 seconds.
2. **Macro quality:** Briefing identifies top 3 actionable events with sector playbooks.
3. **Context depth:** Earnings + insider + options panels visible on every analyzed ticker.
4. **Behavioral:** Tool surfaces warnings before impulsive trades.
5. **Cost:** Only LLM API billed; no paid hosting.

---
**End of Document**
