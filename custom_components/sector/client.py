"""Client module for interacting with Sector Alarm API."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any
from builtins import ExceptionGroup

import aiohttp
from aiohttp import ClientResponseError, ClientSession
from homeassistant.exceptions import HomeAssistantError

from .endpoints import (
    ACTION_ENDPOINTS,
    DataEndpointType,
    fetch_data_endpoints,
    fetch_action_endpoint,
    ActionEndpointType,
    DataEndpoint,
    API_URL,
)

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(HomeAssistantError):
    """Exception raised for authentication errors."""


class LoginError(HomeAssistantError):
    """Raised when login fails."""


class ApiError(HomeAssistantError):
    """Raised when the API returns an unexpected result."""


class APIResponse:
    def __init__(self, response_code: int, response_data: Any, response_json: bool):
        self.response_code = response_code
        self.response_data = response_data
        self.response_json: bool = response_json

    def __str__(self) -> str:
        return (
            f"APIResponse("
            f"response_code={self.response_code}, "
            f"response_json={self.response_json}, "
            f"response_data={self.response_data}"
            f")"
        )

    def __repr__(self) -> str:
        return (
            f"APIResponse("
            f"response_code={self.response_code!r}, "
            f"response_json={self.response_json!r}, "
            f"response_data={self.response_data!r}"
            f")"
        )

    def is_ok(self) -> bool:
        return self.response_code == 200

    def is_json(self) -> bool:
        return self.response_json


class AsyncTokenProvider:
    def __init__(self, client_session: ClientSession, email, password):
        self._token = None
        self._expires_at = 0
        self._lock = asyncio.Lock()
        self._session = client_session
        self._email = email
        self._password = password

    async def _renew_token(self):
        uri = fetch_action_endpoint(ActionEndpointType.LOGIN).uri()
        message_headers = {"Content-Type": "application/json"}
        json_data = {"UserId": f"{self._email}", "Password": f"{self._password}"}

        try:
            async with asyncio.timeout(15):
                async with self._session.post(
                    uri, json=json_data, headers=message_headers, raise_for_status=True
                ) as response:
                    response_json = await response.json()
                    access_token = response_json["AuthorizationToken"]
                    jwt = self._parse_jwt_raw(token=access_token)
                    self._expires_at = jwt["exp"] - 5
                    self._token = access_token
                    _LOGGER.info("Renewed token, expires_at=%s", self._expires_at)
                    return access_token
        except aiohttp.ClientError as error:
            self._handle_exception(error)

    async def get_token(self):
        if self._token and time.time() < self._expires_at:
            return self._token

        # Slow path: acquire lock and refresh if needed
        async with self._lock:
            # Another coroutine may have refreshed while we waited
            if self._token and time.time() < self._expires_at:
                return self._token

            return await self._renew_token()

    def _handle_exception(self, error: aiohttp.ClientError) -> None:
        if isinstance(error, ClientResponseError):
            if error.status == 401:
                self.invalidate_token()
                raise LoginError("Unable to login user - (HTTP UNAUTHORIZED 401)")
            if error.status == 400:
                self.invalidate_token()
                raise ApiError(
                    "Unable to authenticate user - broken API support (HTTP BAD_REQUEST 400)"
                )

            raise ApiError(
                f"Unable to authenticate user - unexpected HTTP error occurred (HTTP {error.status} - {error.message})"
            )

        raise ApiError(
            f"Unable to authenticate user - unexpected network error occurred ({error})"
        )

    def _parse_jwt_raw(self, token: str) -> dict:
        _, payload_b64, _ = token.split(".")

        # Fix padding
        payload_b64 += "=" * (-len(payload_b64) % 4)

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)

    def invalidate_token(self):
        self._token = None
        self._expires_at = 0
        logging.info("Invalidating token, new token needs to be requested")


class SectorAlarmAPI:
    """Class to interact with the Sector Alarm API."""

    def __init__(
        self,
        client_session: ClientSession,
        panel_id,
        token_provider: AsyncTokenProvider,
    ):
        """Initialize the API client."""
        self._panel_id = panel_id
        self._session = client_session
        self._token_provider = token_provider
        self._action_endpoints = ACTION_ENDPOINTS

    def _build_headers(self, token):
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    def _handle_exception(self, err: Exception, method: str, url: str) -> Exception:
        if isinstance(err, TimeoutError):
            return ApiError(
                f"Timeout occurred during {method} request to '{url}': {str(err)}",
                err,
            )
        elif isinstance(err, aiohttp.ClientError):
            return ApiError(
                f"Network connection error during {method} request to '{url}': {str(err)}",
                err,
            )
        elif isinstance(err, Exception):
            _LOGGER.error(
                f"Unexpected error during {method} request to '{url}': {str(err)}"
            )

        # fall through LoginError, APIError, AuthenticationError
        return err

    async def get_panel_list(self) -> APIResponse:
        """Retrieve available panels from the API."""
        data = {}
        panellist_url = f"{API_URL}/api/account/GetPanelList"
        response: APIResponse = await self._get(panellist_url)
        _LOGGER.debug(f"panel_payload: {response.response_data}")

        if response.is_ok() and response.is_json():
            data = {
                item["PanelId"]: item["DisplayName"]
                for item in response.response_data
                if "PanelId" in item
            }
            return APIResponse(
                response_code=response.response_code,
                response_json=response.response_json,
                response_data=data,
            )
        else:
            return response

    async def get_panel_info(self) -> APIResponse:
        """Retrieve available panels from the API."""
        uri = f"{API_URL}/api/Panel/GetPanel?panelId={self._panel_id}"
        response: APIResponse = await self._get(uri)
        _LOGGER.debug(f"panel_payload: {response}")
        return response

    async def retrieve_all_data(
        self, data_endpoint_types: set[DataEndpointType]
    ) -> dict[DataEndpointType, APIResponse]:
        """Retrieve all relevant data from the API."""
        data = {}
        data_endpoints = fetch_data_endpoints(data_endpoint_types)
        try:
            async with asyncio.TaskGroup() as tg:
                for endpoint in data_endpoints:
                    tg.create_task(self._retrieve_data(endpoint, data))
            return data
        except ExceptionGroup as eg:
            relevant_errors = [
                e
                for e in self._flatten_exception_group(eg)
                if not isinstance(e, asyncio.CancelledError)
            ]
            if relevant_errors:
                raise relevant_errors[0] from None
            raise

    def _flatten_exception_group(self, eg: ExceptionGroup):
        for exc in eg.exceptions:
            if isinstance(exc, ExceptionGroup):
                yield from self._flatten_exception_group(exc)
            else:
                yield exc

    async def _retrieve_data(
        self, endpoint: DataEndpoint, data: dict[DataEndpointType, APIResponse]
    ):
        """Retrieve data from the target endpoint."""
        url = endpoint.uri(self._panel_id)
        if endpoint.method() == "GET":
            response: APIResponse = await self._get(url)
        elif endpoint.method() == "POST":
            # For POST requests, we need to provide the panel ID in the payload
            payload = {"PanelId": self._panel_id}
            response: APIResponse = await self._post(url, payload)
        else:
            _LOGGER.error(
                f"Unsupported HTTP method {endpoint.method()} for endpoint {url}"
            )
            raise NotImplementedError(f"Unsupported HTTP method {endpoint.method()}")

        if response:
            data[endpoint.type()] = response

    async def _get(self, url) -> APIResponse:
        """Helper method to perform GET requests with timeout."""
        try:
            headers = self._build_headers(await self._token_provider.get_token())
            async with asyncio.timeout(15):
                async with self._session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            json = await response.json()
                            return APIResponse(
                                response_code=response.status,
                                response_data=json,
                                response_json=True,
                            )
                        else:
                            text = await response.text()
                            return APIResponse(
                                response_code=response.status,
                                response_data=text,
                                response_json=False,
                            )
                    elif response.status == 401 or response.status == 403:
                        self._token_provider.invalidate_token()
                        raise AuthenticationError(
                            f"Authentication failure during GET request to '{url}' - (HTTP {response.status})"
                        )
                    elif response.status == 400:
                        self._token_provider.invalidate_token()
                        raise ApiError(
                            f"Bad request failure during GET request to '{url}', this may indicate broken Sector API support - (HTTP {response.status})"
                        )
                    else:
                        text = await response.text()
                        return APIResponse(
                            response_code=response.status,
                            response_data=text,
                            response_json=False,
                        )
        except Exception as err:
            raise self._handle_exception(err=err, method="GET", url=url)

    async def _post(self, url, payload) -> APIResponse:
        """Helper method to perform POST requests with timeout."""
        try:
            headers = self._build_headers(await self._token_provider.get_token())
            async with asyncio.timeout(15):
                async with self._session.post(
                    url, json=payload, headers=headers
                ) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            json = await response.json()
                            return APIResponse(
                                response_code=response.status,
                                response_data=json,
                                response_json=True,
                            )
                        else:
                            text = await response.text()
                            return APIResponse(
                                response_code=response.status,
                                response_data=text,
                                response_json=False,
                            )
                    elif response.status == 401 or response.status == 403:
                        self._token_provider.invalidate_token()
                        raise AuthenticationError(
                            f"Authentication failure during POST request to '{url}' - (HTTP {response.status})"
                        )
                    elif response.status == 400:
                        self._token_provider.invalidate_token()
                        raise ApiError(
                            f"Bad request failure during POST request to '{url}', this may indicate broken Sector API support - (HTTP {response.status})"
                        )
                    else:
                        text = await response.text()
                        return APIResponse(
                            response_code=response.status,
                            response_data=text,
                            response_json=False,
                        )
        except Exception as err:
            raise self._handle_exception(err=err, method="POST", url=url)

    async def arm_system(self, mode: str, code: str) -> None:
        """Arm the alarm system."""
        panel_code = code
        if mode == "full":
            endpoint = fetch_action_endpoint(ActionEndpointType.ARM)
        elif mode == "partial":
            endpoint = fetch_action_endpoint(ActionEndpointType.PARTIAL_ARM)
        else:
            _LOGGER.error("Unsupported mode %s", mode)
            raise NotImplementedError("Unsupported mode %s", mode)

        payload = {
            "PanelCode": panel_code,
            "PanelId": self._panel_id,
        }
        response: APIResponse = await self._post(endpoint.uri(), payload)
        if not response.is_ok():
            raise ApiError(
                f"Request failure during ARM request to '{endpoint}' (PanelId {self._panel_id}, HTTP {response.response_code} - {response.response_data})"
            )

    async def disarm_system(self, code: str) -> None:
        """Disarm the alarm system."""
        panel_code = code
        url = fetch_action_endpoint(ActionEndpointType.DISARM).uri()
        payload = {
            "PanelCode": panel_code,
            "PanelId": self._panel_id,
        }
        response: APIResponse = await self._post(url, payload)
        if not response.is_ok():
            raise ApiError(
                f"Request failure during DISARM request to '{url}' (PanelId {self._panel_id}, HTTP {response.response_code} - {response.response_data})"
            )

    async def lock_door(self, serial_no: str, code: str) -> None:
        """Lock a specific door."""
        panel_code = code
        url = fetch_action_endpoint(ActionEndpointType.LOCK).uri()
        payload = {
            "LockSerial": serial_no,
            "PanelCode": panel_code,
            "PanelId": self._panel_id,
            "SerialNo": serial_no,
        }
        response: APIResponse = await self._post(url, payload)
        if not response.is_ok():
            raise ApiError(
                f"Request failure during LOCK request to '{url}' (LockSerial {serial_no}, HTTP {response.response_code} - {response.response_data})"
            )

    async def unlock_door(self, serial_no: str, code: str) -> None:
        """Unlock a specific door."""
        panel_code = code
        url = fetch_action_endpoint(ActionEndpointType.UNLOCK).uri()
        payload = {
            "LockSerial": serial_no,
            "PanelCode": panel_code,
            "PanelId": self._panel_id,
            "SerialNo": serial_no,
        }
        response: APIResponse = await self._post(url, payload)
        if not response.is_ok():
            raise ApiError(
                f"Request failure during UNLOCK request to '{url}' (LockSerial {serial_no}, HTTP {response.response_code} - {response.response_data})"
            )

    async def turn_on_smartplug(self, plug_id):
        """Turn on a smart plug."""
        url = fetch_action_endpoint(ActionEndpointType.TURN_ON_SMART_PLUG).uri()
        url = url + f"?switchId={plug_id}&panelId={self._panel_id}"
        payload = {
            "PanelId": self._panel_id,
            "DeviceId": plug_id,
        }
        response: APIResponse = await self._post(url, payload)
        if not response.is_ok():
            raise ApiError(
                f"Request failure during TURN_ON_SMART_PLUG request to '{url}' (SwitchId {plug_id}, HTTP {response.response_code} - {response.response_data})"
            )

    async def turn_off_smartplug(self, plug_id):
        """Turn off a smart plug."""
        url = fetch_action_endpoint(ActionEndpointType.TURN_OFF_SMART_PLUG).uri()
        url = url + f"?switchId={plug_id}&panelId={self._panel_id}"
        payload = {
            "PanelId": self._panel_id,
            "DeviceId": plug_id,
        }
        response: APIResponse = await self._post(url, payload)
        if not response.is_ok():
            raise ApiError(
                f"Request failure during TURN_OFF_SMART_PLUG request to '{url}' (SwitchId {plug_id}, HTTP {response.response_code} - {response.response_data})"
            )

    async def get_camera_image(self, serial_no):
        """Retrieve the latest image from a camera."""
        url = f"{API_URL}/api/camera/GetCameraImage"
        payload = {
            "PanelId": self._panel_id,
            "SerialNo": serial_no,
        }
        response: APIResponse = await self._post(url, payload)
        if response.is_json() and response.response_data.get("ImageData"):
            image_data = base64.b64decode(response.response_data.get("ImageData"))
            return image_data
        _LOGGER.warning("Failed to retrieve image for camera %s", serial_no)
        return None

    async def logout(self):
        """Logout from the API."""
        logout_url = fetch_action_endpoint(ActionEndpointType.LOGOUT).uri()
        await self._post(logout_url, {})
