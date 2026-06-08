from unittest.mock import AsyncMock, patch

import pytest

from trade_sentinel_api.models.schemas import RiskEvaluateRequest
from trade_sentinel_api.services.risk import _detect_leveraged_etf, evaluate_risk


@pytest.mark.asyncio
@patch("trade_sentinel_api.services.risk._fetch_atr", new_callable=AsyncMock, return_value=None)
async def test_position_size_exceeds_limit(_mock_atr):
    req = RiskEvaluateRequest(
        ticker="AAPL",
        quantity=100,
        entry_price=200,
        account_size=10000,
    )
    result = await evaluate_risk(req)
    assert result.portfolio_pct == 200.0
    assert result.exceeds_risk_limit is True
    assert result.suggested_position_size is not None


def test_leveraged_etf_detection():
    assert _detect_leveraged_etf("TQQQ") is True
    assert _detect_leveraged_etf("AAPL") is False
