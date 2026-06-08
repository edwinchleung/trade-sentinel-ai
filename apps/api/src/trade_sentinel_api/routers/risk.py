from fastapi import APIRouter

from trade_sentinel_api.models.schemas import RiskEvaluateRequest, RiskEvaluateResponse
from trade_sentinel_api.services.risk import evaluate_risk

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/evaluate", response_model=RiskEvaluateResponse)
async def risk_evaluate(body: RiskEvaluateRequest) -> RiskEvaluateResponse:
    return await evaluate_risk(body)
