"""PostgreSQL access with SQLite fallback — thin facade over storage/."""

from __future__ import annotations

from trade_sentinel_api.storage import (
    cache_delete,
    cache_delete_like,
    cache_get,
    cache_set,
    decode_cache_payload,
    ensure_pg_sec_index_schema,
    ensure_sec_index_schema,
    ensure_sqlite_cache_schema,
    ensure_sqlite_journal_schema,
    ensure_sqlite_watchlist_schema,
    journal_insert,
    journal_list,
    json_safe,
    log_storage_backend_once,
    pg_connection,
    sec_index_connection,
    sec_index_execute,
    sec_index_executemany,
    sqlite_connection,
    use_postgres,
    watchlist_get,
    watchlist_set,
)

# Backward-compatible private aliases used by tests
_json_safe = json_safe
_decode_cache_payload = decode_cache_payload

__all__ = [
    "_decode_cache_payload",
    "_json_safe",
    "cache_delete",
    "cache_delete_like",
    "cache_get",
    "cache_set",
    "ensure_pg_sec_index_schema",
    "ensure_sec_index_schema",
    "ensure_sqlite_cache_schema",
    "ensure_sqlite_journal_schema",
    "ensure_sqlite_watchlist_schema",
    "journal_insert",
    "journal_list",
    "log_storage_backend_once",
    "pg_connection",
    "sec_index_connection",
    "sec_index_execute",
    "sec_index_executemany",
    "sqlite_connection",
    "use_postgres",
    "watchlist_get",
    "watchlist_set",
]
