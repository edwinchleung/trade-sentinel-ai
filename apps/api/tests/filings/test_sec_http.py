import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from trade_sentinel_api.services.sec.http import (
    SecRateLimitError,
    clear_sec_http_state,
    sec_get,
)


@pytest.fixture(autouse=True)
def reset_throttle():
    clear_sec_http_state()
    yield
    clear_sec_http_state()


def _mock_response(status: int, *, headers: dict | None = None, json_data: dict | None = None):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status}",
            request=MagicMock(),
            response=resp,
        )
    return resp


@patch("trade_sentinel_api.services.sec.http.httpx.Client")
def test_sec_get_retries_on_429(mock_client_cls):
    mock_resp_fail = _mock_response(429)
    mock_resp_ok = _mock_response(200, json_data={"ok": True})

    client = MagicMock()
    client.__enter__.return_value = client
    client.get.side_effect = [mock_resp_fail, mock_resp_ok]
    mock_client_cls.return_value = client

    with patch("trade_sentinel_api.services.sec.http.time.sleep"):
        resp = sec_get("https://www.sec.gov/files/company_tickers.json")

    assert resp.status_code == 200
    assert client.get.call_count == 2


@patch("trade_sentinel_api.services.sec.http.httpx.Client")
def test_sec_get_honors_retry_after(mock_client_cls):
    mock_resp_fail = _mock_response(429, headers={"Retry-After": "10"})
    mock_resp_ok = _mock_response(200)

    client = MagicMock()
    client.__enter__.return_value = client
    client.get.side_effect = [mock_resp_fail, mock_resp_ok]
    mock_client_cls.return_value = client

    with patch("trade_sentinel_api.services.sec.http.time.sleep") as mock_sleep:
        sec_get("https://data.sec.gov/submissions/CIK0000320193.json")

    assert mock_sleep.call_count >= 1
    assert mock_sleep.call_args_list[0].args[0] >= 10.0


@patch("trade_sentinel_api.services.sec.http.httpx.Client")
def test_sec_get_raises_on_rate_limit_when_requested(mock_client_cls):
    mock_resp_fail = _mock_response(429)
    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value = mock_resp_fail
    mock_client_cls.return_value = client

    with (
        patch("trade_sentinel_api.services.sec.http.time.sleep"),
        patch("trade_sentinel_api.services.sec.http.get_settings") as mock_settings,
    ):
        settings = MagicMock()
        settings.sec_retry_max = 0
        settings.sec_retry_base_seconds = 1
        settings.sec_requests_per_second = 100
        settings.sec_request_min_interval_ms = 0
        mock_settings.return_value = settings
        with pytest.raises(SecRateLimitError):
            sec_get(
                "https://www.sec.gov/cgi-bin/browse-edgar",
                raise_on_rate_limit=True,
            )


@patch("trade_sentinel_api.services.sec.http.httpx.Client")
def test_sec_get_throttles_requests(mock_client_cls):
    mock_resp = _mock_response(200)
    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value = mock_resp
    mock_client_cls.return_value = client

    with patch("trade_sentinel_api.services.sec.http.get_settings") as mock_settings:
        settings = MagicMock()
        settings.sec_retry_max = 0
        settings.sec_retry_base_seconds = 1
        settings.sec_requests_per_second = 2
        settings.sec_request_min_interval_ms = 200
        mock_settings.return_value = settings

        start = time.monotonic()
        sec_get("https://www.sec.gov/a")
        sec_get("https://www.sec.gov/b")
        elapsed = time.monotonic() - start

    assert elapsed >= 0.2
    assert client.get.call_count == 2


@patch("trade_sentinel_api.services.sec.http.httpx.Client")
def test_sec_rate_limit_error_not_retried_as_http_error(mock_client_cls):
    mock_resp_fail = _mock_response(429)
    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value = mock_resp_fail
    mock_client_cls.return_value = client

    with (
        patch("trade_sentinel_api.services.sec.http.time.sleep") as mock_sleep,
        patch("trade_sentinel_api.services.sec.http.get_settings") as mock_settings,
    ):
        settings = MagicMock()
        settings.sec_retry_max = 0
        settings.sec_retry_base_seconds = 1
        settings.sec_requests_per_second = 100
        settings.sec_request_min_interval_ms = 0
        mock_settings.return_value = settings
        with pytest.raises(SecRateLimitError):
            sec_get(
                "https://www.sec.gov/cgi-bin/browse-edgar",
                raise_on_rate_limit=True,
            )

    assert client.get.call_count == 1
    mock_sleep.assert_not_called()
