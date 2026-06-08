from fastapi import APIRouter

from trade_sentinel_api.models.schemas import InsiderTimeline, OptionsFlowFlag
from trade_sentinel_api.services.sec.edgar import fetch_insider_timeline
from trade_sentinel_api.services.options import analyze_options_flow

router = APIRouter(prefix="/institutional", tags=["institutional"])


@router.get("/{ticker}/insider", response_model=InsiderTimeline)
async def insider_timeline(ticker: str) -> InsiderTimeline:
    return await fetch_insider_timeline(ticker)


@router.get("/{ticker}/options-flow", response_model=OptionsFlowFlag)
async def options_flow(ticker: str) -> OptionsFlowFlag:
    flag, _ = await analyze_options_flow(ticker)
    return flag
