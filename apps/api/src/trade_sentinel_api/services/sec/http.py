"""Thread-safe SEC EDGAR HTTP gateway with global throttle and unified retries."""

from __future__ import annotations

import logging
import random
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

from trade_sentinel_api.config import get_settings

SEC_HEADERS_BASE = {
    "Accept-Encoding": "gzip, deflate",
}


def sec_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        **SEC_HEADERS_BASE,
        "User-Agent": settings.sec_user_agent,
    }


if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

_THROTTLE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


class SecRateLimitError(Exception):
    """Raised when SEC returns 429 after all retries are exhausted."""

    def __init__(self, url: str, status_code: int = 429) -> None:
        self.url = url
        self.status_code = status_code
        parsed = urlparse(url)
        path = parsed.path or url
        super().__init__(f"SEC rate limited ({status_code}) for {parsed.netloc}{path}")


def _propagate_rate_limit(url: str, status_code: int, *, raise_on_rate_limit: bool) -> None:
    if status_code == 429 and raise_on_rate_limit:
        raise SecRateLimitError(url, status_code)


def _retryable_status(code: int) -> bool:
    return code in (429, 502, 503, 504)


def _throttle_wait() -> None:
    settings = get_settings()
    min_interval = max(
        1.0 / max(settings.sec_requests_per_second, 1),
        settings.sec_request_min_interval_ms / 1000.0,
    )
    global _LAST_REQUEST_AT
    with _THROTTLE_LOCK:
        now = time.monotonic()
        elapsed = now - _LAST_REQUEST_AT
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _LAST_REQUEST_AT = time.monotonic()


def _retry_delay(attempt: int, status_code: int, resp: httpx.Response | None) -> float:
    settings = get_settings()
    delay = settings.sec_retry_base_seconds * (2**attempt)
    if status_code == 429:
        delay = max(delay, 5.0 * (attempt + 1))
    if resp is not None:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
    return delay + random.uniform(0, 0.5)


def sec_get(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 20.0,
    follow_redirects: bool = False,
    raise_on_rate_limit: bool = False,
) -> httpx.Response:
    """GET with global throttle and retry for 429/5xx. Returns the final response."""
    settings = get_settings()
    last_status: int | None = None
    last_resp: httpx.Response | None = None

    for attempt in range(settings.sec_retry_max + 1):
        _throttle_wait()
        try:
            if client is not None:
                resp = client.get(url)
            else:
                with httpx.Client(
                    timeout=timeout,
                    headers=sec_headers(),
                    follow_redirects=follow_redirects,
                ) as owned:
                    resp = owned.get(url)
            last_resp = resp
            last_status = resp.status_code
            if resp.status_code < 400:
                return resp
            if resp.status_code == 429 and raise_on_rate_limit:
                parsed = urlparse(url)
                logger.warning(
                    "SEC rate limit for %s%s (status=%s, attempts=%d)",
                    parsed.netloc,
                    parsed.path,
                    resp.status_code,
                    attempt + 1,
                )
                raise SecRateLimitError(url, resp.status_code)
            if _retryable_status(resp.status_code) and attempt < settings.sec_retry_max:
                time.sleep(_retry_delay(attempt, resp.status_code, resp))
                continue
            if resp.status_code == 429:
                parsed = urlparse(url)
                logger.warning(
                    "SEC rate limit exhausted for %s%s (status=%s, attempts=%d)",
                    parsed.netloc,
                    parsed.path,
                    resp.status_code,
                    attempt + 1,
                )
            _propagate_rate_limit(url, resp.status_code, raise_on_rate_limit=raise_on_rate_limit)
            return resp
        except SecRateLimitError:
            raise
        except httpx.HTTPError:
            if attempt < settings.sec_retry_max:
                time.sleep(_retry_delay(attempt, last_status or 0, last_resp))
                continue
            raise

    if last_resp is not None:
        _propagate_rate_limit(url, last_resp.status_code, raise_on_rate_limit=raise_on_rate_limit)
        return last_resp
    raise httpx.HTTPError(f"SEC request failed for {url}")


class SecClient:
    """Context-managed SEC client; all .get() calls share throttle + retry."""

    def __init__(self, *, timeout: float = 20.0, follow_redirects: bool = False) -> None:
        self._timeout = timeout
        self._follow_redirects = follow_redirects
        self._client: httpx.Client | None = None

    def __enter__(self) -> SecClient:
        self._client = httpx.Client(
            timeout=self._timeout,
            headers=sec_headers(),
            follow_redirects=self._follow_redirects,
        )
        return self

    def __exit__(self, *args: object) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def get(
        self,
        url: str,
        *,
        raise_on_rate_limit: bool = False,
    ) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("SecClient used outside context manager")
        return sec_get(
            url,
            client=self._client,
            timeout=self._timeout,
            follow_redirects=self._follow_redirects,
            raise_on_rate_limit=raise_on_rate_limit,
        )


@contextmanager
def sec_client(
    *,
    timeout: float = 20.0,
    follow_redirects: bool = False,
) -> Iterator[SecClient]:
    with SecClient(timeout=timeout, follow_redirects=follow_redirects) as client:
        yield client


def clear_sec_http_state() -> None:
    """Reset throttle clock (for tests)."""
    global _LAST_REQUEST_AT
    with _THROTTLE_LOCK:
        _LAST_REQUEST_AT = 0.0
