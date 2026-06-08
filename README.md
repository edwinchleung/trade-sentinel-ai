# TradeSentinel AI

**Institutional-grade clarity for the retail investor.**

TradeSentinel AI is a personal investing tool that runs on your own machine. It pulls together price data, fundamentals, SEC filings, insider and institutional activity, macroeconomic events, and basic risk math into one place — so you can understand a ticker or your watchlist before you trade.

It is **not** a trading bot. It does not connect to brokerages, place orders, or tell you to buy or sell. When you are thinking about a trade, it helps you slow down, read the context, and check position size and downside.

An LLM is used only to **summarize facts the app has already fetched** (news headlines, filing excerpts, valuation metrics, insider flow). It does not invent prices or fabricate data — missing fields show as unavailable in the UI and in prompts.

Runs entirely on **your PC** via Docker. Single-user, no login, privacy-first.

---

## What is TradeSentinel?

Most retail investors juggle too many tabs: a chart, a news feed, an earnings calendar, maybe a Form 4 alert, and a spreadsheet for position size. TradeSentinel combines that workflow into a local web app with eight focused pages, each aimed at a specific question:

- *What is going on with this stock right now?* → Context Engine
- *What are institutions and insiders doing?* → Smart Money Hub
- *How does my watchlist look today?* → Digest and Screener
- *What macro events matter today?* → Macro Briefing
- *Is this trade sized safely?* → Pre-Trade Risk Check

Data comes from free or low-cost sources (yfinance, SEC EDGAR, optional Finnhub/FRED). You pay only for LLM API usage if you use a cloud model — local infrastructure is free on your machine.

For a longer walkthrough of each module, see [docs/product-description.md](docs/product-description.md).

---

## What it is not

- **Not a broker or execution system** — no order placement, no account linking
- **Not multi-user SaaS** — one operator on localhost; no accounts or authentication
- **Not financial advice** — analytical information to support your own decisions
- **Not a substitute for primary sources** — for large positions, still read filings and verify numbers yourself

---

## A typical session

1. **Morning** — Open the home page or **Macro Briefing** (`/briefing`) for a one-line “market weather” summary and which economic releases affect which sectors.
2. **Watchlist check** — Open **Watchlist Digest** (`/digest`) to see margin of safety, days until earnings, insider sentiment, and warnings for every ticker you track — without clicking into each one.
3. **Before a trade idea** — Go to **Context Engine** (`/context?ticker=AAPL`) for fair-value band, fundamentals vs the company’s own 3-year history, SEC filing excerpts, and an AI summary grounded in those facts.
4. **Before you size the trade** — Use **Pre-Trade Risk Check** (`/risk`) for the 2% position rule, an ATR-based stop-loss suggestion, and warnings on leveraged ETFs or short-dated options.
5. **Optional** — Browse **Smart Money Hub** (`/smart-money`) for market-wide insider filings and 13F changes; save the risk check to **Trade Journal** (`/journal`) for later review.

Manage tickers on **Watchlist** (`/watchlist`); digest and screener read from that list automatically.

---

## Problem → Solution

| Problem | How TradeSentinel helps |
|---------|-------------------------|
| Information overload | One ticker query returns fundamentals, news, filings, insider/options activity, and an AI summary in seconds |
| Emotional trading (FOMO, panic) | Pre-trade risk check and reality-check cards encourage a deliberate pause |
| Poor position sizing | 2% rule, ATR-based stop-loss, and derivative warnings before you trade |
| Institutional blind spots | Smart Money Hub surfaces Form 4, 13F, activist filings, and market-wide scans |

---

## Features

Quick reference — open http://localhost:3000 after starting the stack (API docs at http://localhost:8000/docs).

| Module | Route | Summary |
|--------|-------|---------|
| **Market Context Engine** | `/context` | Deep single-ticker due diligence |
| **Smart Money Hub** | `/smart-money` | Market-wide insider, 13F, and scan tools |
| **Watchlist Digest** | `/digest` | Daily snapshot of saved tickers |
| **Anti-FOMO Screener** | `/screener` | Filter watchlist or S&P presets |
| **Macro Briefing** | `/briefing` | Daily macro tone and sector impact |
| **Pre-Trade Risk Check** | `/risk` | Position sizing and stop-loss |
| **Trade Journal** | `/journal` | History of risk checks |
| **Watchlist Manager** | `/watchlist` | Ticker list for digest and screener |

### Market Context Engine (`/context`)

When you open `/context?ticker=…`, analysis runs automatically (add `?auto=0` to disable).

- **Fair-value band** — composite estimate from analyst target, historical P/E, Graham-style metrics, and optional DCF when free cash flow is positive; shows premium or discount vs current price
- **Fundamentals vs own history** — revenue growth, margins, and valuation compared to the company’s 3-year track record, not generic sector peers
- **SEC filings** — recent 8-K, 10-Q, and 10-K metadata; text excerpts from the latest 8-K and quarterly report feed into the AI summary
- **Insider activity** — 90-day net buy/sell, accumulation/distribution label, notable Form 4 trades
- **Options** — multi-expiry put/call ratios, open interest, top strikes by volume
- **AI summary** — fundamental-first bullets with technical and options context subordinate; streams via SSE when summarizing

### Smart Money Hub (`/smart-money`)

Market-wide view of “smart money” signals, not tied to one ticker.

- **Insider feed** — recent Form 4 filings across the market, filterable by side and size
- **13F holdings** — quarter-over-quarter institutional changes and top holders (from bulk-ingested SEC data)
- **Activist filings** — 13D/G alerts for large ownership stakes
- **Scans** — options put/call and volume scans on your watchlist or S&P 100
- **Also available** — N-PORT fund holdings, GEX proxy, dark pool summary, COT report, congressional trade feed, and a combined per-ticker assessment

### Watchlist Digest (`/digest`) and Screener (`/screener`)

- **Digest** — table of every watchlist ticker: price, margin of safety, earnings countdown, insider sentiment, top warning; refreshed by the background scheduler
- **Screener** — filter the same universe with presets such as undervalued, earnings this week, insider accumulation, or above fair band; supports S&P 100/500 presets in addition to your watchlist

### Macro Briefing (`/briefing`)

- **Market weather** — one-sentence headline for the day’s macro tone
- **Economic calendar** — events with impact level (high / moderate / noise), release times, and sector playbooks (“why it matters”)
- **Watchlist exposure** — which of your saved tickers sit in sectors most affected by today’s releases
- **Macro indicators** — VIX, yields, major indices; optional FRED series when configured

### Pre-Trade Risk Check (`/risk`) and Trade Journal (`/journal`)

- **Risk check** — enter ticker, direction, size, and account equity; get flags if position exceeds 2% of account, ATR-based stop suggestion, and plain-English warnings for leveraged ETFs or options
- **Journal** — save risk checks to PostgreSQL and review them later on `/journal`

### Watchlist Manager (`/watchlist`)

Add or remove tickers on your default list. Digest, screener, macro exposure, and smart-money watchlist pulse all use this list.

---

## How the AI fits in

TradeSentinel does **not** use vector RAG or open-ended “ask anything” chat. Instead:

1. Python services fetch and compute structured facts (JSON).
2. A versioned prompt template (`apps/api/prompts/context_v*.txt`, `macro_v*.txt`) instructs the model to cite only those facts.
3. Separate prompts exist for ticker context vs macro briefing — macro output never drifts into stock-picking language.
4. If a field is missing (e.g. no insider filings), the UI and LLM see explicit gaps rather than hallucinated numbers.

Configure your provider in `.env` — OpenRouter (default), Ollama (local), DashScope, OpenAI, or Anthropic. See [docs/llm-providers.md](docs/llm-providers.md).

---

## How it works

```mermaid
flowchart LR
  subgraph ui [Next.js UI]
    Context[Context Engine]
    SmartMoney[Smart Money Hub]
    Digest[Digest and Screener]
    Risk[Risk Check]
    Macro[Macro Briefing]
  end
  subgraph api [FastAPI]
    Routers[routers]
    Services[services]
    Scheduler[Background scheduler]
  end
  subgraph data [Data layer]
    YF[yfinance]
    SEC[SEC EDGAR]
    LLM[LangChain LLM]
    PG[(PostgreSQL)]
  end
  ui --> Routers --> Services
  Services --> YF
  Services --> SEC
  Services --> LLM
  Services --> PG
  Scheduler --> Services
  Scheduler -->|WebSocket| ui
```

1. You query a ticker or open a page in the Next.js UI.
2. FastAPI routers call domain services (`context`, `valuation`, `sec`, `smart_money`, `macro`, etc.).
3. Services fetch from yfinance, SEC EDGAR, and optional APIs, then cache in PostgreSQL.
4. LangChain generates summaries from structured JSON — versioned prompts, not vector RAG.
5. A background scheduler warms digest, screener, and smart-money caches and reports progress over WebSocket.

See [docs/architecture.md](docs/architecture.md) for monorepo layout, caching, scheduler details, and testing.

---

## Technical overview

- **Facts-grounded LLM pipeline** — structured data in-context via versioned prompts; missing facts stay explicit
- **Modular FastAPI backend** — `context/`, `valuation/`, `sec/`, `smart_money/`, `scheduler/`, `storage/`
- **Background scheduler** — pre-warms digest, screener, and smart-money data; WebSocket updates in the UI
- **Multi-source SEC ingestion** — Form 4, 8-K/10-Q/10-K, 13F, 13D/G, N-PORT via edgartools and bulk ingest scripts

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS 4, Recharts |
| Backend | FastAPI, Python 3.11+, Pydantic v2, LangChain |
| Database | PostgreSQL 16 (Docker); SQLite fallback when `DATABASE_URL` is unset |
| Data | yfinance, SEC EDGAR, optional Finnhub / FRED / NewsAPI |
| LLM | OpenRouter (default), Ollama, DashScope, OpenAI, Anthropic |
| DevOps | Docker Compose, pnpm workspace, uv (Python), GitHub Actions CI |

---

## Data sources

| Source | Used for |
|--------|----------|
| **yfinance** | Price, fundamentals, options chains, earnings, headlines |
| **SEC EDGAR** | Form 4 insider trades, 8-K/10-Q/10-K filings, 13F institutional holdings, 13D/G activist filings, N-PORT fund holdings |
| **Finnhub** (optional) | News, economic calendar, earnings enrichment |
| **FRED** (optional) | Official macro series (CPI, yield curve) |
| **NewsAPI** (optional) | Macro news enrichment |
| **LLM providers** | Facts-grounded ticker and macro summaries |

---

## Quick start

### Prerequisites

- Docker and Docker Compose
- Copy `.env.example` to `.env` and set `LLM_API_KEY` (see [docs/llm-providers.md](docs/llm-providers.md))

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| Web | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

Data persists in the `postgres_data` Docker volume. Postgres is exposed on host port **5433** by default (`POSTGRES_PORT` in `.env`) to avoid clashing with a local PostgreSQL on 5432.

### Smoke test

```bash
./scripts/smoke_test.sh
```

### Native dev (optional)

```bash
docker compose up postgres -d
export DATABASE_URL=postgresql://tradesentinel:tradesentinel@localhost:5433/tradesentinel

# Terminal 1
cd apps/api && uv sync --all-extras && uv run uvicorn trade_sentinel_api.main:app --reload --port 8000

# Terminal 2
cd apps/web && npm install && npm run dev
```

Without `DATABASE_URL`, the API uses SQLite files under `apps/api/.cache/`.

For backup, port conflicts, troubleshooting, and full API surface, see [docs/runbook.md](docs/runbook.md).

---

## Project layout

```
apps/api/              FastAPI backend (routers, services, prompts, tests)
apps/web/              Next.js frontend (App Router pages and components)
docker/postgres/       DB init SQL
docs/                  Product docs, architecture, runbook, LLM guide
scripts/               smoke_test.sh
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/product-description.md](docs/product-description.md) | Full feature walkthrough |
| [docs/architecture.md](docs/architecture.md) | How the system is built |
| [docs/runbook.md](docs/runbook.md) | Operations: start/stop, backup, troubleshooting |
| [docs/llm-providers.md](docs/llm-providers.md) | LLM provider setup (OpenRouter, Ollama, etc.) |
| [docs/product-requirement-document.md](docs/product-requirement-document.md) | Functional requirements (PRD) |
| [docs/product-development-plan.md](docs/product-development-plan.md) | Development phases and roadmap |

---

## Disclaimer

TradeSentinel AI provides analytical information only. It is not financial advice. Always do your own research before making investment decisions.

*Trade Smart. Trade Safe. Trade with Sentinel.*
