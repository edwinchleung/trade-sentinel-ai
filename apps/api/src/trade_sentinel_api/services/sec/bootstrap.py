"""One-time EdgarTools SEC identity and access-mode configuration."""

from __future__ import annotations

import logging
import os

from trade_sentinel_api.config import get_settings

logger = logging.getLogger(__name__)
_bootstrapped = False


def bootstrap_edgartools() -> None:
    global _bootstrapped
    if _bootstrapped:
        return

    settings = get_settings()
    if settings.edgar_access_mode:
        os.environ.setdefault("EDGAR_ACCESS_MODE", settings.edgar_access_mode.upper())

    try:
        from edgar import set_identity

        set_identity(settings.sec_user_agent)
        _bootstrapped = True
        logger.debug("EdgarTools identity configured")
    except ImportError:
        logger.warning("edgartools not installed — SEC adapter unavailable")
    except Exception as exc:
        logger.warning("EdgarTools bootstrap failed: %s", exc)
