-- TradeSentinel AI — local PostgreSQL schema (single user, no auth)

CREATE TABLE IF NOT EXISTS context_cache (
    cache_key TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_context_cache_expires ON context_cache (expires_at);

CREATE TABLE IF NOT EXISTS trade_journal (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    account_size DOUBLE PRECISION NOT NULL,
    instrument_type TEXT NOT NULL,
    ai_warnings JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_journal_created ON trade_journal (created_at DESC);

CREATE TABLE IF NOT EXISTS watchlists (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE DEFAULT 'default',
    tickers TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
