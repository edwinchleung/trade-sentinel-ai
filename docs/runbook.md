# TradeSentinel AI — Local Runbook

Operational guide for running TradeSentinel on your PC via Docker Compose.

For a product overview and feature list, see the [README](../README.md). For engineering architecture, see [architecture.md](architecture.md). This document is for operators — start/stop, backup, API surface, and troubleshooting.

---

## Prerequisites

- Docker and Docker Compose
- Copy [`.env.example`](../.env.example) to `.env` and configure:
  - **LLM provider** — required for AI summaries (default: **OpenRouter** via `LLM_API_KEY`; also Ollama, DashScope, or legacy OpenAI/Anthropic). See [llm-providers.md](llm-providers.md)
  - **`FINNHUB_API_KEY`** — optional; improves news headlines
  - **`SEC_USER_NAME`** / **`SEC_USER_EMAIL`** — SEC EDGAR User-Agent (defaults provided)

---

## Start / stop

```bash
# Start full stack (postgres + api + web)
docker compose up --build

# Detached
docker compose up --build -d

# Stop
docker compose down

# Stop and remove DB volume (destructive)
docker compose down -v
```

**URLs**

| Service | URL |
|---------|-----|
| Web | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Postgres (host) | `localhost:5433` (default `POSTGRES_PORT`) |

---

## API surface (canonical paths)

Some data is available from multiple endpoints for backward compatibility. Prefer the canonical paths below; legacy routes remain supported.

| Data | Canonical | Legacy (still supported) |
|------|-----------|--------------------------|
| Insider activity | `/api/v1/smart-money/feed`, `/api/v1/context/{ticker}?include_insider=true` | `/api/v1/institutional/{ticker}/insider` |
| Options flow | `/api/v1/context/{ticker}?include_options=true`, `/api/v1/smart-money/options/*` | `/api/v1/institutional/{ticker}/options-flow` |
| SEC filings feed | `/api/v1/context/{ticker}` (embedded), `/api/v1/filings/current` | — |

---

## Smoke test (Phase 1 sign-off)

With the stack running:

```bash
chmod +x scripts/smoke_test.sh
./scripts/smoke_test.sh
```

Optional env vars:

- `API_URL` — default `http://localhost:8000`
- `SMOKE_TICKER` — default `AAPL`
- `SMOKE_MAX_SECONDS` — default `10`

Pytest smoke (mocked, CI-safe — `live` tests excluded by default via `pyproject.toml`):

```bash
cd apps/api && uv run pytest tests/context/test_endpoint.py -q
```

Live smoke against running API:

```bash
cd apps/api && API_URL=http://localhost:8000 uv run pytest tests/context/test_endpoint.py -q -m live
```

Full API unit suite (Docker with mounted tests):

```bash
docker compose run --rm \
  -v "$(pwd)/apps/api/tests:/app/tests:ro" \
  -v "$(pwd)/apps/api/src:/app/src" \
  -v "$(pwd)/apps/api/pyproject.toml:/app/pyproject.toml:ro" \
  api sh -c 'uv sync --extra dev -q && uv run pytest tests/ -q'
```

Test layout (domain folders under `apps/api/tests/`): `llm/`, `context/`, `filings/`, `smart_money/`, `macro/`, `valuation/`, `fundamentals/`, `market/`, `earnings/`, `infra/`, `api/`. Shared context endpoint mocks live in `tests/fixtures/context_mocks.py`.

---

## Native dev (optional)

Run Postgres in Docker; API and web on the host:

```bash
docker compose up postgres -d
export DATABASE_URL=postgresql://tradesentinel:tradesentinel@localhost:5433/tradesentinel

# Terminal 1 — API
cd apps/api && uv sync --all-extras && uv run uvicorn trade_sentinel_api.main:app --reload --port 8000

# Terminal 2 — web
cd apps/web && npm install && npm run dev
```

Without `DATABASE_URL`, the API uses SQLite under `apps/api/.cache/`.

---

## Backup and restore (Postgres)

**Backup**

```bash
docker compose exec postgres pg_dump -U tradesentinel tradesentinel > backup.sql
```

**Restore**

```bash
cat backup.sql | docker compose exec -T postgres psql -U tradesentinel -d tradesentinel
```

Data persists in the `postgres_data` Docker volume across restarts.

---

## Troubleshooting

### Port 8000 already in use

A native `uvicorn` on the host can bind before Docker maps the API port. Symptoms: API returns empty market data or stale SQLite cache.

```bash
# Find process on 8000
ss -tlnp | grep 8000

# Stop native API or use Docker-only workflow
docker compose up --build
```

Verify you hit the Docker API:

```bash
docker compose exec api uv run python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/health').json())"
```

### Postgres port conflict (5432)

Set `POSTGRES_PORT=5433` in `.env` and use that port in `DATABASE_URL` for native dev.

### Context page: CORS error or "Failed to fetch"

Often the API returned **500** without CORS headers (browser shows a CORS error). Check logs:

```bash
docker compose logs api --tail 50
curl -s http://localhost:8000/health
```

Confirm `llm_configured` is `true` when your provider keys are set. Rebuild after dependency changes (bind mount no longer overwrites container `.venv`):

```bash
docker compose down
docker compose up --build -d
```

Ensure nothing else is bound to port **8000**. If `docker ps` shows `8000/tcp` without `0.0.0.0:8000->8000`, a **host uvicorn** is blocking the publish (you will hit stale code and get watchlist 404 / old `/health`):

```bash
ss -tlnp | grep 8000
# stop the host process, then:
docker compose up -d --force-recreate api
curl -s http://localhost:8000/health
```

`/health` should include `llm_provider` and `llm_configured`.

One-command fix (stops stale host API, rebuilds container, verifies health):

```bash
./scripts/restart-api-stack.sh
```

If port 8000 stays occupied, set `API_PORT=8001` in `.env`, then `docker compose up -d --force-recreate api web` and use `http://localhost:8001` for the API.

### Watchlist returns 404

`GET /api/v1/watchlists/default` should return **200** with an empty `tickers` list. A 404 means the process on `:8000` is an old API build:

```bash
curl -s http://localhost:8000/api/v1/watchlists/default
docker compose up --build -d
```

### AI summaries show placeholder bullets (or old OpenAI/Anthropic message)

Summaries are **cached** for 15 minutes. After changing `.env`, restart and refresh:

```bash
docker compose restart api
curl -s "http://localhost:8000/api/v1/macro/briefing?refresh=true"
```

Configure the provider block in `.env` (see [llm-providers.md](llm-providers.md)).

**OpenRouter:** `LLM_PROVIDER=openrouter`, `LLM_API_KEY`, `LLM_MODEL=openai/gpt-4o-mini`

**Ollama:** `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://host.docker.internal:11434`, model pulled locally

**DashScope:** `LLM_PROVIDER=dashscope`, `DASHSCOPE_API_KEY`, `LLM_MODEL=qwen-plus`

### No news headlines

Add `FINNHUB_API_KEY` to `.env` (free tier at finnhub.io).

### FRED API key (official macro stats)

Optional `FRED_API_KEY` in `.env` powers 10Y–2Y spread and CPI YoY on the macro briefing and context overlay. The API container loads `.env` via `env_file` in `docker-compose.yml`.

Verify the key:

```bash
curl -s "https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&api_key=YOUR_KEY&file_type=json&limit=1" | head
```

After updating `.env`:

```bash
docker compose restart api
```

If FRED fails but yfinance yields are present, context **data_gaps** should not list `fred_T10Y2Y_fetch_failed` (spread fallback). Actionable gaps use friendly labels; `fred_auth_failed` means renew the key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).

### Macro news (no Finnhub)

Macro briefing also pulls headlines from **yfinance (SPY)**, **public RSS** (Fed, BLS, NPR), and optional **NewsAPI** without Finnhub:

```
NEWSAPI_KEY=          # optional — newsapi.org
MACRO_NEWS_LIMIT=12
```

Refresh: `curl -s "http://localhost:8000/api/v1/macro/briefing?refresh=true" | jq '.macro_news | length'`

### Macro signals or FRED data missing

Market indicators (VIX, yields, SPY, oil, etc.) come from **yfinance** automatically.

Optional official series (unemployment, Fed funds, CPI YoY, 10Y–2Y spread) need a free key:

```
FRED_API_KEY=         # https://fred.stlouisfed.org/docs/api/api_key.html
```

Briefing uses **US Eastern** trading day by default (`MACRO_TRADING_TIMEZONE=America/New_York`).

### Context page slower on first Analyze of the day

The Market Context Engine loads the same **daily macro bundle** (signals, calendar, news) once per ET date (`macro:bundle:YYYY-MM-DD` cache). The first ticker analyzed that day may take longer; subsequent tickers reuse the bundle. If you already ran Macro Briefing today, context reuses its cached `market_weather` / `signal_highlights` when available.

### Insider feed shows “Data Unavailable”

SEC EDGAR requires a descriptive User-Agent. Set in `.env`:

```
SEC_USER_NAME=YourName
SEC_USER_EMAIL=you@example.com
```

Some issuers have no recent Form 4 filings — that is expected.

**Log: `SEC company ticker list unavailable after retries: HTTP 429`:** SEC rate-limited `company_tickers.json`. The API now falls back automatically to (1) a local disk cache (`apps/api/data/company_tickers_cache.json` after a successful fetch) or (2) the bundled seed (`apps/api/data/company_tickers_seed.json`, ~9.7k tickers). Insider/13F features keep working on fallback; logs will say `using bundled CIK seed` or `using stale disk cache`. To reduce 429s: use a **real** `SEC_USER_EMAIL` (not `example.com`), avoid restarting the API repeatedly, and let the background scheduler warm the CIK map once at startup. After SEC recovers, the next successful fetch refreshes the disk cache.

### Smart Money filing tabs empty but API is up

Run the filing verification script (API must be running):

```bash
chmod +x scripts/verify_filing_features.sh
./scripts/verify_filing_features.sh
```

**Form 4 market feed empty with default filters:** The hub defaults to open-market buys/sells only. If the message says filings were parsed but none matched, that can be a quiet week — not a broken pipeline. Check `enriched_count` / `raw_entry_count` in the feed JSON. If both are zero or the message contains “unavailable”, fix `SEC_USER_NAME` / `SEC_USER_EMAIL` and restart the API (cache keys are versioned `v2:` — restart clears stale empty results).

**13F conviction empty for mega-caps (e.g. AAPL shows no tracked filers):** Usually means 13F holdings XML was not resolved (should not happen after the `form13fInfoTable.xml` fix). Confirm `filers_refreshed` > 0 on `GET /api/v1/smart-money/13f/conviction?universe=sp500`. Per-ticker holdings: `GET /api/v1/smart-money/13f/changes?ticker=AAPL` should return multiple filers when healthy.

**Institutional tab shows no rows but per-ticker 13F works:** Expected — the tab lists **conviction buys** (QoQ new/increased + multi-filer), not all holdings. Use the stock context page for full 13F detail.

**Activist 13D/G sparse:** Normal on quiet weeks; background job `activist_feed` warms the feed every refresh interval.

### Macro briefing shows no events

Phase 5 removes fake CPI/FOMC fallback events on quiet days. An empty **calendar** is correct when Finnhub and `macro_schedule.json` have no US releases for that ET date. The briefing may still show **macro signals**, **headlines**, and an LLM summary on quiet days.

Add dated entries to `apps/api/data/macro_schedule.json` or configure `FINNHUB_API_KEY` for live calendar data with actual/estimate/prior fields.

Use the **Refresh** button on the Briefing page or:

```bash
curl -s "http://localhost:8000/api/v1/macro/briefing?refresh=true" | jq '.market_weather, .impact_summary'
```

### Context page missing earnings / insider / options panels

Ensure you click **Analyze** with default options (insider + options enabled). SSE stream now includes insider and options by default. Earnings merges Finnhub historical `stock/earnings` with **`/calendar/earnings`** (next 90 days) for next report date; yfinance `earnings_dates` / calendar fills gaps. Revenue actual may come from quarterly income stmt when Finnhub omits revenue fields. Partial earnings (EPS without next date) shows a helper message in the UI.

### Context Smart Money section empty or LLM ignores 13F / activist

The context engine requires `include_insider=true` and/or `include_options=true` (default on **Analyze** and SSE stream). Without those flags, 13F holdings, activist 13D, and composite smart-money assessment are not fetched.

**Insider excerpts show “transaction details unavailable”:** Form 4 URLs from SEC submissions may point to `-index.htm` pages. The API resolves these to XML via `resolve_edgar_xml_url` before parsing. Confirm `SEC_USER_NAME` / `SEC_USER_EMAIL` in `.env` and restart the API. Context cache key is **`:v22`** — restart clears stale summaries missing smart-money facts.

**Context shows only 3 LLM bullets (Valuation / Macro / Growth):** Usually a new `context_vN.txt` was added without registering it in `context_prompt_registry.py`. Post-processing then falls back to v1 caps (3 bullets, no extended narratives). Check API logs for `Unknown context prompt version`. Run `pytest apps/api/tests/llm/test_prompt_registry.py` — it fails if any prompt file on disk lacks a registry entry.

**Adding a new context prompt version (e.g. v10):**

1. Create `apps/api/prompts/context_v10.txt`
2. Register in `apps/api/src/trade_sentinel_api/services/context_prompt_registry.py` (prefer `extends="v9"` if only prompt text changed)
3. Add selection logic in `context.py` (`use_v10` + priority in `prompt_version` chain)
4. Bump context cache key (`v22` → `v23`)
5. Run `pytest apps/api/tests/llm/test_prompt_registry.py` before merge

**13F table empty on context page but Smart Money hub works:** Call `GET /api/v1/context/AAPL?include_insider=true` and check `institutional_13f.data_available` and `changes.length`. Mega-caps should show multiple tracked filers when healthy. LLM summaries use `context_v9.txt` when smart-money data is present (cites filer names, activist %, conviction layers).

**Verify context filing integration:**

```bash
curl -s "http://localhost:8000/api/v1/context/AAPL?include_insider=true&include_options=true" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('13f', d.get('institutional_13f',{}).get('data_available'), len(d.get('institutional_13f',{}).get('changes',[]))); print('activist', d.get('activist_filing')); print('layers', len(d.get('smart_money_assessment',{}).get('layers',[])))"
```

### Fair-value assessment tuning

Optional `.env` keys: `VALUATION_COMPOSITE_MODE` (`iqr` or `weighted`), `VALUATION_INCLUDE_DCF`, sector MOS thresholds (`VALUATION_MOS_*`). Finnhub `FINNHUB_API_KEY` enriches analyst target mean/low/high. Sector P/E priors live in `apps/api/data/sector_pe_priors.json`. Banks/REITs skip DCF and prefer P/B; pre-profit names may use P/S when TTM EPS is negative.

Digest and screener MOS / fair mid / confidence are hydrated from the same per-ticker valuation cache as the context engine (`ticker_valuation.resolve_ticker_valuation`, TTL `cache_ttl_seconds`). Digest table **Band** = model `mos_label`; **MOS %** = premium vs fair mid; `valuation_label` (forward P/E bucket) is only used for screener filters.

**ADR / mixed reporting currency:** yfinance `financialCurrency` may differ from quote `currency` (e.g. TSM: TWD statements, USD ADR price). The API converts all statement amounts (revenue, cash flow, balance sheet, quarterly EPS) to **USD** via Yahoo FX (`currency.py`) before DCF/Graham/P/S and historical P/E benchmarks. EPS-based valuation uses `trailingEps` from quote currency when financial ≠ trading. If FX fails, `valuation_currency_mismatch` restricts the fair-value band. Snapshots expose `amounts_currency`, `financial_currency`, and `fx_rate_financial_to_trading` (financial→USD rate).

### Fundamentals slow or empty

Fundamentals use yfinance `Ticker.info`, quarterly income/balance/cashflow, and 3Y price history for self-benchmark P/E reconstruction. Historical P/E uses **TTM EPS** (rolling four quarters) with winsorized P/E points (cap ~80×); `median_pe_3y` is stored on the benchmark and reused by valuation. If median P/E is unreliable (e.g. >2× forward or >60×), `historical_pe` is shown but **excluded** from the headline fair band. Headline low/mid/high uses trimmed composite anchors (analyst, Graham, reliable historical P/E, DCF) with IQR (P25–P75); FCF yield is **diagnostic only**. Valuation v2 uses **TTM FCF** for DCF, conservative growth blend, sector-aware MOS thresholds, and `reliability_notes[]` when methods are excluded. Premium vs fair mid is `(price − mid) / mid × 100`. Summarized context uses `context_v7.txt` when valuation, `technical_assessment`, `fundamental_assessment`, and `news_digest` are all available (else v6 → v5 chain). v7 adds `fundamental_interpretation`, `reality_check_narrative`, and `scenario_bullets`. Context cache key is **`:v18`**.

**Session-aware quotes:** Price and `change_pct` use yfinance `marketState` (pre/regular/post/closed) with `preMarketPrice` / `postMarketPrice` / `regularMarketPrice` vs `previousClose`. UI shows session badge and regular close when extended hours differ.

**News digest:** Merges Finnhub + yfinance (up to 12 headlines), optional bounded article summaries, rule-based sentiment/themes, aggregate `NewsDigest`.

**Reality check:** Deterministic `RealityCheck` card plus LLM scenario framing (non-advisory). UI: `RealityCheckCard`, `FundamentalAssessmentCard`, horizon strip on `TechnicalAssessmentCard`.

**Smart Money hub:** `/smart-money` defaults to **proactive S&P 500** scans. Endpoints: market-wide Form 4 feed (`GET /api/v1/smart-money/feed`), S&P 500 insider accumulation (`GET /api/v1/smart-money/insider-scan?universe=sp500`), watchlist insider pulse (opt-in), filer-driven 13F conviction (`GET /api/v1/smart-money/13f/conviction?universe=sp500`), activist 13D/G feed, volume footprint scan (`universe=watchlist|sp100|sp500`), macro COT, and options scan (`universe=watchlist|sp100|sp500`). Requires `SEC_USER_NAME` / `SEC_USER_EMAIL` for SEC feeds. Config: `SMART_MONEY_PROACTIVE_UNIVERSE` (default `sp500`), `SMART_MONEY_SP500_CACHE_MINUTES` (120), `SMART_MONEY_FEED_CACHE_MINUTES` (30), `SMART_MONEY_OPTIONS_CACHE_MINUTES` (60), `SMART_MONEY_13F_CACHE_HOURS` (24), `SMART_MONEY_VOLUME_CACHE_MINUTES` (60), `SMART_MONEY_SCAN_CONCURRENCY` (3). Universe files: `apps/api/data/sp500_universe.json` (~503 names) and `sp100_universe.json` — curated snapshots, not live index membership. SP500 options/volume scans run chunked in background with `scan_progress` WebSocket events; expect ~10–20 min for a full SP500 options refresh at concurrency 3. Watchlist scans remain available as secondary toggles (capped at `DIGEST_MAX_TICKERS`). Context page groups per-ticker insider + options + composite assessment under **Smart Money** with link to hub.

**Smart Money methodology (signal layers):**

| Layer | Source | Latency | Notes |
|-------|--------|---------|-------|
| Form 4 insiders | SEC EDGAR XML | ~2 business days | Open-market P/S only; cluster buys; $1M notable |
| Options flow | yfinance (Polygon if `POLYGON_API_KEY` set) | Daily aggregates | P/C bands 0.70/0.90; Vol/OI ≥3 unusual, ≥5 high-conviction; $500k premium filter |
| Volume footprint | yfinance OHLCV (Polygon OHLCV optional) | End of day | OBV/A-D slope divergence, VWAP deviation, quiet accumulation |
| Form 13F | SEC EDGAR (20 tracked filers) | Quarterly + 45d | CUSIP match; QoQ new/increased/decreased/exit; HHI crowding |
| Schedule 13D/G | SEC EDGAR atom + XML enrich | 5 business days (13D) | Activist vs passive stake signals |
| COT macro | CFTC CSV | Weekly | Commercial net positioning for ES/CL/GC/ZN |

**Not available without vendor keys:** Official SqueezeMetrics DIX, Unusual Whales dark-pool prints — use computed GEX + FINRA short-volume proxy when keys unset. Options sweeps require Polygon tick plan (`POLYGON_OPTIONS_TICKS_ENABLED`).

**Bulk 13F / N-PORT:** Hybrid storage under `apps/api/data/sec_bulk/` with SQLite index at `apps/api/.cache/sec_index.db` (or Postgres when `DATABASE_URL` set). Ingest: `uv run python apps/api/scripts/ingest_sec_13f_bulk.py --quarter 2024q4` and `ingest_sec_nport_bulk.py`. Manual job: `POST /api/v1/jobs/refresh?scope=sec_bulk_13f`. Per-ticker holder census: `GET /api/v1/smart-money/13f/holders?ticker=AAPL`.

**New endpoints:** `GET /smart-money/13f/holders`, `GET /smart-money/nport/{ticker}`, `GET /smart-money/microstructure/gex`, `GET /smart-money/dark-pool/{ticker}`, `GET /smart-money/congressional-feed`. Forms 3/5 supported on insider feed via `form_type=3|5|all`.

**Calendar normalization** down-weights conviction during quarter-end window dressing and late-December tax-loss season. GEX negative regime applies an additional 0.9 multiplier on composite assessment.

**Technical assessment:** Built from 1y daily OHLCV (≥50 bars). Includes short/mid/long horizon trend labels, Wilder RSI, MACD, SMAs, ATR, 52W range, support/resistance, MACD divergence.

**Fair-value assessment:** Deterministic band from analyst target, FCF yield, Graham-lite EPS×P/E, and 3Y historical P/E median. Optional 5-year DCF when FCF is positive — discount rate = live 10Y yield (^TNX) + 5.5% equity risk premium (clamped 8–14%); terminal growth and growth cap derived from revenue CAGR / growth fields (no `.env` tuning). ETFs/funds use expense ratio and NAV premium — not equity DCF.

**Watchlist digest / screener:** `GET /api/v1/digest/today` and `GET /api/v1/screener/watchlist` batch lite snapshots (no LLM by default). Cached per ET day (`digest:YYYY-MM-DD:default`, 4h TTL). Use `DIGEST_MAX_TICKERS` and `DIGEST_CONCURRENCY` to limit yfinance load. Pages `/digest` and `/screener` auto-load on visit.

**Market valuation screener:** `GET /api/v1/screener/market?universe=sp500` (default) or `sp100` scans curated presets with the same fair-value pipeline as context (`resolve_ticker_valuation`). Filter by `preset=undervalued` (requires `mos_label=undervalued` from the composite fair band — not raw P/E alone), plus optional `mos_min`/`mos_max`, `pe_max`, etc. Full universe cached per ET day (`market_screener`, TTL `MARKET_SCREENER_CACHE_MINUTES`, default 60). `/screener` UI toggles **Watchlist | S&P 500 | S&P 100**. Use **Force refresh** or `?refresh=true` to rebuild synchronously.

**Background jobs:** When `BACKGROUND_JOBS_ENABLED=true` (default), the API pre-warms digest, S&P 500 screener cache, smart-money feed, **SP500 options/volume/insider scans**, filer-driven 13F conviction, watchlist pulse, and watchlist options **in the background after HTTP is up** (`BACKGROUND_STARTUP_WARM=true`, default) and every `BACKGROUND_REFRESH_INTERVAL_MINUTES` (default 30). The API accepts requests within seconds of start; `GET /health` returns `ready: true` and `warming: true` while caches build. Set `BACKGROUND_STARTUP_WARM=false` to skip the initial warm (use interval or `POST /jobs/refresh` instead). Watchlist edits trigger a debounced refresh (`BACKGROUND_WATCHLIST_DEBOUNCE_SECONDS`, default 15). S&P 500 scan uses a shared yfinance bundle per ticker, chunked batches (`YFINANCE_BATCH_CHUNK_SIZE`, default 25) with optional batched OHLCV prefetch, `ThreadPoolExecutor` with `BACKGROUND_SCAN_WORKERS` (default **4**) parallel workers, and `YFINANCE_CHUNK_DELAY_SECONDS` (default 1s) between chunks — expect ~5–15 min for ~500 names on first run. yfinance HTTP errors are suppressed in logs when `YFINANCE_QUIET_LOGS=true` (default); check batch summary lines or `GET /api/v1/jobs/status` instead of per-ticker 401 spam. SEC CIK map is pre-warmed on startup with retry/backoff (`SEC_RETRY_MAX`, `SEC_RETRY_BASE_SECONDS`, `SEC_CIK_FAILURE_TTL_SECONDS`); set real `SEC_USER_NAME` / `SEC_USER_EMAIL`. Status: `GET /api/v1/jobs/status`; manual trigger: `POST /api/v1/jobs/refresh?scope=all|digest|market|smart_money|watchlist`. Pages read cache only unless you force refresh. Regenerate `sp500_universe.json` manually: `uv run python scripts/generate_sp500_universe.py`. **Dev note:** `uvicorn --reload` retriggers startup warm on code saves; widespread browser **Failed to fetch** usually means the API is not listening yet — verify `curl -s http://localhost:8000/health` returns within a few seconds.

**WebSocket live updates:** When `WEBSOCKET_ENABLED=true` (default), connect to `ws://localhost:8000/api/v1/ws` (or `wss://` in production). After connect, send `{"action":"subscribe","channels":["jobs","screener:sp500","digest:default"]}`. Event types: `jobs_snapshot`, `job_started`, `job_finished`, `scan_progress` (progress bar: `completed` / `total` / `percent`), `screener_rows` (chunk of new market rows), `digest_rows` (chunk of watchlist digest rows). Screener and digest pages subscribe automatically; rows append as each yfinance batch finishes without waiting for the full job. Disable with `WEBSOCKET_ENABLED=false`.

Undervalued preset ranks by ascending MOS % (largest discount vs fair mid first). Finnhub `/stock/metric` and `/stock/recommendation` enrich analyst/ROE data when `FINNHUB_API_KEY` is set; `analyst_buy` / `analyst_sell` also fall back to yfinance `recommendations` when Finnhub has no row. Quarterly **revenue YoY %** in the UI needs at least five quarters in yfinance income stmt (YoY compares to the column four quarters back). **`revenue_growth_acceleration`** uses the same YoY series when metrics lack YoY, as long as five+ revenue columns exist.

**Earnings next date:** Finnhub calendar + yfinance `info.earningsDate`, DataFrame `calendar`, and **dict** `calendar` (e.g. ADRs like TSM with `Earnings Date` key) are merged. Partial snapshot (EPS without date) shows a helper in the UI.

**SEC filing excerpts:** Domestic issuers use **8-K / 10-Q / 10-K**; foreign private issuers (e.g. TSM) use **6-K** (current) and **20-F** (annual). The recent-filings list always includes the latest periodic filing (**10-Q, 10-K, or 20-F**) even when the first five rows are all current reports. Excerpt fetch reserves one slot for that filing, then up to four 8-K/6-K rows (cached per accession, 7 days). Thin HTML uses plain-text fallback (40+ chars). Requires `SEC_USER_AGENT` in `.env`.

**Insider Form 4 excerpts:** Up to five notable/recent filings fetch XML when possible; excerpts include buy/sell, shares, and price when parseable, or an explicit “transaction details unavailable” suffix when not (7-day cache per URL; HTTP failures only are negative-cached).

**Options open interest:** Summed across up to 12 expiries; omitted from LLM facts when yfinance returns no positive OI (not reported as `0.0`). Per-strike OI on `top_strikes` is omitted when unknown.

**Forward outlook:** Built deterministically from earnings, fundamentals, news, SEC, insider, and technical warnings — no extra API calls.

### Watchlist tickers missing or different after restart

The API stores watchlists in **one** backend only:

- **Postgres** when `DATABASE_URL` starts with `postgresql` (Docker Compose default).
- **SQLite** at `apps/api/.cache/watchlists.db` when `DATABASE_URL` is unset or non-Postgres.

Switching between Docker API + host API, or changing `DATABASE_URL`, shows a different (often empty) list. Use a single `DATABASE_URL` and one process on port **8000**.

After editing the watchlist, digest/screener invalidate caches automatically and schedule a debounced background rebuild. Use **Force refresh** on `/digest` or `/screener`, or `?refresh=true` on the API. Only the first `DIGEST_MAX_TICKERS` symbols (default 20, alphabetical) appear in watchlist digest/screener/smart-money scan. The S&P 500 market screener scans the full curated list (~503 names) in the background.

Prefer **PATCH** `/api/v1/watchlists/default/tickers` with `{ "add": ["NVDA"], "remove": ["META"] }` for add/remove to avoid full-list overwrite races.

### Watchlist unique constraint (existing DB volumes)

If watchlist PUT fails after upgrade, run once:

```sql
ALTER TABLE watchlists ADD CONSTRAINT watchlists_name_key UNIQUE (name);
```

---

## CI

GitHub Actions runs:

- API unit tests (SQLite) + ruff
- Postgres integration tests (journal, cache, watchlists)
- Web lint + build

Local parity:

```bash
cd apps/api && uv run pytest tests/ -q
```

---

**End of runbook**
