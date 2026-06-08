# TradeSentinel AI — Documentation

TradeSentinel AI is a local web app for personal investing: it combines market data, SEC filings, insider and institutional activity, macro events, and pre-trade risk checks in one place. It runs on your machine via Docker Compose (Next.js + FastAPI + PostgreSQL) and does not execute trades or require a login.

Use the [README](../README.md) for a product overview and quick start. Use [product-description.md](product-description.md) for a full walkthrough of each module.

## By intent

| I want to… | Read |
|------------|------|
| Understand what the app does and run it quickly | [README.md](../README.md) |
| Learn the product vision and feature details | [product-description.md](product-description.md) |
| Understand how the system is built | [architecture.md](architecture.md) |
| Operate the stack (start, stop, backup, troubleshoot) | [runbook.md](runbook.md) |
| Configure an LLM provider | [llm-providers.md](llm-providers.md) |
| See full functional requirements | [product-requirement-document.md](product-requirement-document.md) |
| See development phases and history | [product-development-plan.md](product-development-plan.md) |

## Quick links

- **Web UI:** http://localhost:3000 (after `docker compose up`)
- **API docs:** http://localhost:8000/docs
- **Environment template:** [`.env.example`](../.env.example)
- **Frontend routes:** [apps/web/README.md](../apps/web/README.md)
