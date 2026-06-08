"""Tests for congressional trades provider."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from trade_sentinel_api.services.providers.congressional import CapitolTradesProvider


@patch("trade_sentinel_api.services.providers.congressional.httpx.Client")
def test_capitol_trades_parses_response(mock_client_cls):
    recent = date.today() - timedelta(days=5)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {
                "politician": "Sen. Example",
                "ticker": "AAPL",
                "transactionDate": (recent - timedelta(days=2)).isoformat(),
                "disclosureDate": recent.isoformat(),
                "transactionType": "Purchase",
                "amount": "$1,001 - $15,000",
            }
        ]
    }
    mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
    provider = CapitolTradesProvider()
    result = provider.fetch_trades(days=30)
    assert result.data_available is True
    assert result.payload[0].ticker == "AAPL"
