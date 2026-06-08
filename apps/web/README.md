# TradeSentinel AI — Web Frontend

Next.js 15 (App Router) frontend for [TradeSentinel AI](../../README.md). Dark-mode-first UI built with TypeScript and Tailwind CSS 4.

## Routes

| Route | Module |
|-------|--------|
| `/` | Dashboard — watchlist digest highlights, quick links |
| `/context` | Market Context Engine — deep single-ticker analysis |
| `/smart-money` | Smart Money Hub — insider feed, 13F, scans |
| `/digest` | Watchlist Digest — daily snapshot table |
| `/screener` | Anti-FOMO Screener — filter presets |
| `/briefing` | Macro Briefing — economic calendar and sector playbooks |
| `/risk` | Pre-Trade Risk Check — position sizing and stop-loss |
| `/journal` | Trade Journal — persisted risk-check history |
| `/watchlist` | Watchlist Manager — ticker CRUD |

## Development

Requires the API running at http://localhost:8000 (see root README for Docker or native setup).

```bash
npm install
npm run dev
```

Open http://localhost:3000.

## Key directories

```
src/app/           App Router pages (one folder per route above)
src/components/    Domain UI cards (ValuationCard, SecFilingsPanel, etc.)
src/lib/api.ts     Typed API client for /api/v1 endpoints
src/hooks/         WebSocket job updates (useJobUpdates)
```

## Documentation

- [Root README](../../README.md) — product overview and quick start
- [docs/architecture.md](../../docs/architecture.md) — engineering architecture
- [docs/runbook.md](../../docs/runbook.md) — operations guide
