import time
from typing import Any

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.db import cache_delete, cache_get, cache_set

_memory: dict[str, tuple[float, Any]] = {}


def cache_ttl_seconds() -> int:
    """Default in-memory/DB cache TTL from settings."""
    return get_settings().cache_ttl_seconds


def default_cache_ttl_seconds() -> int:
    return cache_ttl_seconds()


def _cache_key(prefix: str, key: str) -> str:
    return f"{prefix}:{key.upper()}"


def get_cached(prefix: str, key: str) -> Any | None:
    ck = _cache_key(prefix, key)
    now = time.time()

    if ck in _memory:
        expires, payload = _memory[ck]
        if expires > now:
            return payload
        del _memory[ck]

    payload = cache_get(ck)
    if payload is not None:
        _memory[ck] = (now + default_cache_ttl_seconds(), payload)
    return payload


def set_cached(prefix: str, key: str, payload: Any) -> None:
    ck = _cache_key(prefix, key)
    expires = time.time() + default_cache_ttl_seconds()

    _memory[ck] = (expires, payload)
    cache_set(ck, payload, expires)


def set_cached_ttl(prefix: str, key: str, payload: Any, ttl_seconds: int) -> None:
    ck = _cache_key(prefix, key)
    expires = time.time() + ttl_seconds
    _memory[ck] = (expires, payload)
    cache_set(ck, payload, expires)


def clear_cached(prefix: str, key: str) -> None:
    ck = _cache_key(prefix, key)
    _memory.pop(ck, None)
    cache_delete(ck)


def clear_cached_by_prefix(prefix: str, key_contains: str = "") -> None:
    """Clear in-memory and DB cache entries for prefix, optionally filtering by substring."""
    from trade_sentinel_api.db import cache_delete_like

    p = prefix.upper()
    needle = key_contains.upper()
    to_drop = [
        k
        for k in list(_memory)
        if k.startswith(f"{p}:") and (not needle or needle in k)
    ]
    for k in to_drop:
        _memory.pop(k, None)
    like_pattern = f"{p}:%{needle}%" if needle else f"{p}:%"
    cache_delete_like(like_pattern)
