"""Mutable scheduler lifecycle state shared across modules."""

from __future__ import annotations

import asyncio

_interval_task: asyncio.Task | None = None
_pending_watchlist: set[str] = set()
_running: bool = False
