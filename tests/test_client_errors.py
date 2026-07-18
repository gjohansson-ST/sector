"""Tests for the SectorAlarmAPI client – network error handling and retry behaviour."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.sector.client import (
    APIResponse,
    ApiError,
    AuthenticationError,
    Retryable,
    SectorAlarmAPI,
    AsyncTokenProvider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_token_provider() -> AsyncMock:
    provider = AsyncMock(spec=AsyncTokenProvider)
    provider.get_token = AsyncMock(return_value="fake-jwt-token")
    provider.invalidate_token = MagicMock()
    return provider


def _build_api(session: MagicMock | None = None) -> SectorAlarmAPI:
    if session is None:
        session = MagicMock(spec=aiohttp.ClientSession)
    return SectorAlarmAPI(
        client_session=session,
        panel_id="9999",
        token_provider=_mock_token_provider(),
    )


# ---------------------------------------------------------------------------
# APIResponse tests
# ---------------------------------------------------------------------------

class TestAPIResponse:
    def test_is_ok_true(self):
        r = APIResponse(response_code=200, response_data={}, response_is_json=True)
        assert r.is_ok()

    def test_is_ok_false(self):
        r = APIResponse(response_code=500, response_data="err", response_is_json=False)
        assert not r.is_ok()

    def test_is_json(self):
        r = APIResponse(response_code=200, response_data=[], response_is_json=True)
        assert r.is_json()

    def test_str_repr(self):
        r = APIResponse(response_code=200, response_data="ok", response_is_json=False)
        assert "200" in str(r)
        assert "200" in repr(r)


# ---------------------------------------------------------------------------
# Retryable – exponential back‑off
# ---------------------------------------------------------------------------

class TestRetryableBackoff:
    async def test_retries_exhaust_all_attempts(self):
        call_count = 0

        async def failing():
            nonlocal call_count
            call_count += 1
            raise ApiError("boom")

        retry = Retryable(attempts=4, retry_exceptions=(ApiError,), max_delay=0)
        with pytest.raises(ApiError):
            await retry.run(failing)
        assert call_count == 4

    async def test_succeeds_on_second_attempt(self):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ApiError("transient")
            return "ok"

        retry = Retryable(attempts=3, retry_exceptions=(ApiError,), max_delay=0)
        result = await retry.run(flaky)
        assert result == "ok"
        assert call_count == 2

    async def test_non_retryable_exception_raised_immediately(self):
        call_count = 0

        async def bad():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        retry = Retryable(attempts=5, retry_exceptions=(ApiError,), max_delay=0)
        with pytest.raises(ValueError):
            await retry.run(bad)
        assert call_count == 1


# ---------------------------------------------------------------------------
# SectorAlarmAPI._handle_exception mapping
# ---------------------------------------------------------------------------

class TestHandleException:
    def test_timeout_maps_to_api_error(self):
        api = _build_api()
        exc = api._handle_exception(TimeoutError("timed out"), "GET", "/test")
        assert isinstance(exc, ApiError)

    def test_client_error_maps_to_api_error(self):
        api = _build_api()
        exc = api._handle_exception(
            aiohttp.ClientConnectionError("refused"), "POST", "/test"
        )
        assert isinstance(exc, ApiError)

    def test_login_error_passed_through(self):
        from custom_components.sector.client import LoginError

        api = _build_api()
        original = LoginError("bad creds")
        exc = api._handle_exception(original, "GET", "/login")
        assert exc is original
