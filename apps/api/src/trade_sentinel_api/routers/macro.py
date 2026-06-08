from fastapi import APIRouter, Query

from trade_sentinel_api.models.schemas import MacroBriefing
from trade_sentinel_api.services.macro import get_macro_briefing

router = APIRouter(prefix="/macro", tags=["macro"])


@router.get("/briefing", response_model=MacroBriefing)
async def macro_briefing(
    refresh: bool = Query(False, description="Bypass cache and regenerate briefing"),
) -> MacroBriefing:
    return await get_macro_briefing(refresh=refresh)
