import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from trade_sentinel_api.models.schemas import TickerContext
from trade_sentinel_api.services.context import build_ticker_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context", tags=["context"])


@router.get("/{ticker}", response_model=TickerContext)
async def get_context(
    ticker: str,
    summarize: bool = Query(False, description="Include AI summary (uses LLM)"),
    include_insider: bool = Query(False),
    include_options: bool = Query(False),
) -> TickerContext:
    try:
        return await build_ticker_context(
            ticker,
            summarize=summarize,
            include_insider=include_insider,
            include_options=include_options,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Context build failed for %s", ticker)
        raise HTTPException(status_code=500, detail="Failed to build market context") from exc


@router.post("/{ticker}/summarize", response_model=TickerContext)
async def summarize_ticker(ticker: str) -> TickerContext:
    try:
        return await build_ticker_context(
            ticker,
            summarize=True,
            include_insider=True,
            include_options=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Context summarize failed for %s", ticker)
        raise HTTPException(status_code=500, detail="Failed to summarize context") from exc


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


@router.get("/{ticker}/stream")
async def stream_context_summary(
    ticker: str,
    include_insider: bool = Query(True),
    include_options: bool = Query(True),
) -> StreamingResponse:
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            yield _sse_event({"status": "fetching", "step": "market"})
            ctx = await build_ticker_context(
                ticker,
                summarize=True,
                include_insider=include_insider,
                include_options=include_options,
            )
            payload = ctx.model_dump(mode="json")
            yield _sse_event({"status": "complete", "context": payload})
        except Exception:
            logger.exception("Context stream failed for %s", ticker)
            yield _sse_event(
                {"status": "error", "message": "Failed to build market context"}
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
