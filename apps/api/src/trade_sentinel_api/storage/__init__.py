"""Storage layer — Postgres with SQLite fallback."""

from trade_sentinel_api.storage.cache_repo import (
    cache_delete,
    cache_delete_like,
    cache_get,
    cache_set,
    decode_cache_payload,
    ensure_sqlite_cache_schema,
    json_safe,
)
from trade_sentinel_api.storage.connection import (
    log_storage_backend_once,
    pg_connection,
    sqlite_connection,
    use_postgres,
)
from trade_sentinel_api.storage.journal_repo import (
    ensure_sqlite_journal_schema,
    journal_insert,
    journal_list,
)
from trade_sentinel_api.storage.sec_index_repo import (
    ensure_pg_sec_index_schema,
    ensure_sec_index_schema,
    sec_index_connection,
    sec_index_execute,
    sec_index_executemany,
)
from trade_sentinel_api.storage.watchlist_repo import (
    ensure_sqlite_watchlist_schema,
    watchlist_get,
    watchlist_set,
)

__all__ = [
    "cache_delete",
    "cache_delete_like",
    "cache_get",
    "cache_set",
    "decode_cache_payload",
    "ensure_pg_sec_index_schema",
    "ensure_sec_index_schema",
    "ensure_sqlite_cache_schema",
    "ensure_sqlite_journal_schema",
    "ensure_sqlite_watchlist_schema",
    "journal_insert",
    "journal_list",
    "json_safe",
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
