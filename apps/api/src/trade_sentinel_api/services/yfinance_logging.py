"""yfinance log noise control and batch failure summaries."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

logger = logging.getLogger(__name__)

_batch_label: ContextVar[str | None] = ContextVar("yfinance_batch_label", default=None)
_batch_total: ContextVar[int] = ContextVar("yfinance_batch_total", default=0)
_batch_failures: ContextVar[int] = ContextVar("yfinance_batch_failures", default=0)


def configure_yfinance_logging(*, quiet: bool = True) -> None:
    """Reduce yfinance/HTTP log spam; enable library retries."""
    if quiet:
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("curl_cffi").setLevel(logging.WARNING)
    try:
        from yfinance.config import YfConfig

        YfConfig.network.retries = 2
        YfConfig.debug.hide_exceptions = True
    except Exception:
        pass


def record_yfinance_batch_failure() -> None:
    if _batch_label.get() is not None:
        _batch_failures.set(_batch_failures.get() + 1)


@contextmanager
def yfinance_batch_context(*, label: str, total: int) -> Iterator[None]:
    token_label = _batch_label.set(label)
    token_total = _batch_total.set(total)
    token_fail = _batch_failures.set(0)
    try:
        yield
    finally:
        failures = _batch_failures.get()
        ok = max(total - failures, 0)
        if failures:
            logger.warning(
                "%s batch: %s/%s ok, %s yfinance failures",
                label,
                ok,
                total,
                failures,
            )
        else:
            logger.info("%s batch: %s/%s ok", label, ok, total)
        _batch_label.reset(token_label)
        _batch_total.reset(token_total)
        _batch_failures.reset(token_fail)
