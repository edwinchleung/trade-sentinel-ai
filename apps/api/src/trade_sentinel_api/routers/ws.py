"""WebSocket endpoint for live job status and progressive scan updates."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.job_events import (
    get_connection_manager,
    send_jobs_snapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


def _parse_subscribe_message(text: str) -> set[str] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if data.get("action") != "subscribe":
        return None
    channels = data.get("channels")
    if not isinstance(channels, list):
        return None
    return {str(c).strip() for c in channels if str(c).strip()}


@router.websocket("/ws")
async def jobs_websocket(websocket: WebSocket) -> None:
    settings = get_settings()
    if not settings.websocket_enabled:
        await websocket.close(code=1008, reason="WebSocket disabled")
        return

    manager = get_connection_manager()
    await manager.connect(websocket, {"jobs"})
    subscribed = False

    async def default_jobs_only() -> None:
        await asyncio.sleep(2.0)
        if not subscribed:
            await manager.set_channels(websocket, {"jobs"})

    default_task = asyncio.create_task(default_jobs_only())

    try:
        await send_jobs_snapshot(websocket)
        while True:
            text = await websocket.receive_text()
            channels = _parse_subscribe_message(text)
            if channels is not None:
                subscribed = True
                default_task.cancel()
                await manager.set_channels(websocket, channels)
                await send_jobs_snapshot(websocket)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        default_task.cancel()
        manager.disconnect(websocket)
