"""Client module for interacting with Sector Alarm API."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any

import aiohttp
import async_timeout
from aiohttp import ClientResponseError, ClientSession
from homeassistant.exceptions import HomeAssistantError

from .api_model import PanelInfo
from .endpoints import ACTION_ENDPOINTS, DataEndpointType, fetch_data_endpoints, fetch_action_endpoint, \
    ActionEndpointType, DataEndpoint, API_URL

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(HomeAssistantError):
    """Exception raised for authentication errors."""

class LoginError(HomeAssistantError):
    """Raised when login fails."""

class ApiError(HomeAssistantError):
    """Raised when the API returns an unexpected result."""

class APIResponse:
    def __init__(self, response_code: int, response: Any):
        self.response_code = response_code
        self.response_data = response

    def __str__(self):
        return f"ApiResponse(response_code={self.response_code}, response_data={self.response_data})"

    def is_ok(self) -> bool:
        return self.response_code == 200

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
        message_headers = {
            "Content-Type": "application/json"
        }
        json_data = {
            "UserId": f"{self._email}",
            "Password": f"{self._password}"
        }

        try:
            async with async_timeout.timeout(15):
                async with self._session.post(uri,
                                              json=json_data,
                                              headers=message_headers,
                                              raise_for_status=True) as response:

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
                raise ApiError("Unable to authenticate user - broken API support (HTTP BAD_REQUEST 400)")

            raise ApiError(
                f"Unable to authenticate user - unexpected HTTP error occurred (HTTP {error.status} - {error.message})")

        raise ApiError(f"Unable to authenticate user - unexpected network error occurred ({error})")

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

    def __init__(self, client_session: ClientSession, panel_id, token_provider: AsyncTokenProvider):
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

    async def get_panel_list(self) -> dict[str, str]:
        """Retrieve available panels from the API."""
        data = {}
        panellist_url = f"{API_URL}/api/account/GetPanelList"
        response: APIResponse = await self._get(panellist_url)
        _LOGGER.debug(f"panel_payload: {response.response_data}")

        if response and response.is_ok():
            data = {
                item["PanelId"]: item["DisplayName"]
                for item in response.response_data
                if "PanelId" in item
            }
        else:
            _LOGGER.error("Failed to retrieve any panels")

        return data

    async def get_panel_info(self) -> PanelInfo:
        """Retrieve available panels from the API."""
        uri = f"{API_URL}/api/Panel/GetPanel?panelId={self._panel_id}"
        response: APIResponse = await self._get(uri)
        _LOGGER.debug(f"panel_payload: {response}")

        if response is None or response.is_ok() == False:
            _LOGGER.error("Failed to retrieve panel %s", self._panel_id)

        return response.response_data

    async def retrieve_all_data(self, data_endpoint_types: set[DataEndpointType]) -> dict[DataEndpointType, APIResponse]:
        """Retrieve all relevant data from the API."""
        data = {}
        data_endpoints = fetch_data_endpoints(data_endpoint_types)
        async with asyncio.TaskGroup() as tg:
            for endpoint in data_endpoints:
                tg.create_task(self._retrieve_data(endpoint, data))

        return data

    async def _retrieve_data(self, endpoint: DataEndpoint, data: dict[DataEndpointType, APIResponse]):
        """Retrieve data from the target endpoint."""
        url = endpoint.uri(self._panel_id)
        if endpoint.method() == "GET":
            response: APIResponse = await self._get(url)
        elif endpoint.method() == "POST":
            # For POST requests, we need to provide the panel ID in the payload
            payload = {"PanelId": self._panel_id}
            response: APIResponse = await self._post(url, payload)
        else:
            _LOGGER.error("Unsupported HTTP method %s for endpoint %s", endpoint.method(), url)
            return

        if response:
            data[endpoint.type()] = response

    async def _get(self, url) -> APIResponse | None:
        """Helper method to perform GET requests with timeout."""
        try:
            headers = self._build_headers(await self._token_provider.get_token())
            async with async_timeout.timeout(15):
                async with self._session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            json = await response.json()
                            return APIResponse(response_code=response.status, response=json)
                        else:
                            text = await response.text()
                            _LOGGER.error(
                                "Received non-JSON response from %s: %s", url, text
                            )
                            return None
                    else:
                        text = await response.text()
                        _LOGGER.warning(
                            "GET request to %s failed with status code %s, response: %s",
                            url,
                            response.status,
                            text,
                        )
                        return APIResponse(response_code=response.status, response=text)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout occurred during GET request to %s", url)
            return None
        except aiohttp.ClientResponseError as err:
            _LOGGER.warning(f"Client error during GET request to %s - (HTTP {err.status} - {err.message})", url)
            if err.status == 401 or err.status == 403:
                self._token_provider.invalidate_token()
            return None
        except ApiError as e:
            _LOGGER.warning("Client error during GET request to %s: %s", url, str(e))
            return None
        except aiohttp.ClientError as e:
            _LOGGER.warning("Client error during GET request to %s: %s", url, str(e))
            return None

    async def _post(self, url, payload) -> APIResponse | None:
        """Helper method to perform POST requests with timeout."""
        try:
            headers = self._build_headers(await self._token_provider.get_token())
            async with async_timeout.timeout(15):
                async with self._session.post(
                    url, json=payload, headers=headers
                ) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            json = await response.json()
                            return APIResponse(response_code=response.status, response=json)
                        else:
                            text = await response.text()
                            _LOGGER.error(
                                "Received non-JSON response from %s: %s", url, text
                            )
                            return None
                    else:
                        text = await response.text()
                        _LOGGER.warning(
                            "POST request to %s failed with status code %s, response: %s",
                            url,
                            response.status,
                            text,
                        )
                        return APIResponse(response_code=response.status, response=text)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout occurred during POST request to %s", url)
            return None
        except aiohttp.ClientResponseError as err:
            _LOGGER.warning(f"Client error during POST request to %s - (HTTP {err.status} - {err.message})", url)
            if err.status == 401 or err.status == 403:
                self._token_provider.invalidate_token()
            return None
        except ApiError as e:
            _LOGGER.warning("Client error during POST request to %s: %s", url, str(e))
            return None
        except aiohttp.ClientError as err:
            _LOGGER.error("Client error during POST request to %s: %s", url, str(err))
            return None

    async def arm_system(self, mode: str, code: str):
        """Arm the alarm system."""
        panel_code = code
        if mode == "total":
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
        result: APIResponse = await self._post(endpoint.uri(), payload)
        if result and result.is_ok():
            _LOGGER.debug("System armed successfully")
            return True
        else:
            _LOGGER.error("Failed to arm system")
            return False

    async def disarm_system(self, code: str):
        """Disarm the alarm system."""
        panel_code = code
        url = fetch_action_endpoint(ActionEndpointType.DISARM).uri()
        payload = {
            "PanelCode": panel_code,
            "PanelId": self._panel_id,
        }
        result: APIResponse = await self._post(url, payload)
        if result and result.is_ok():
            _LOGGER.debug("System disarmed successfully")
            return True
        else:
            _LOGGER.error("Failed to disarm system")
            return False

    async def lock_door(self, serial_no: str, code: str):
        """Lock a specific door."""
        panel_code = code
        url = fetch_action_endpoint(ActionEndpointType.LOCK).uri()
        payload = {
            "LockSerial": serial_no,
            "PanelCode": panel_code,
            "PanelId": self._panel_id,
            "SerialNo": serial_no,
        }
        result: APIResponse = await self._post(url, payload)
        if result and result.is_ok():
            _LOGGER.debug("Door %s locked successfully", serial_no)
            return True
        else:
            _LOGGER.error("Failed to lock door %s", serial_no)
            return False

    async def unlock_door(self, serial_no: str, code: str):
        """Unlock a specific door."""
        panel_code = code
        url = fetch_action_endpoint(ActionEndpointType.UNLOCK).uri()
        payload = {
            "LockSerial": serial_no,
            "PanelCode": panel_code,
            "PanelId": self._panel_id,
            "SerialNo": serial_no,
        }
        result: APIResponse = await self._post(url, payload)
        if result and result.is_ok():
            _LOGGER.debug("Door %s unlocked successfully", serial_no)
            return True
        else:
            _LOGGER.error("Failed to unlock door %s", serial_no)
            return False

    async def turn_on_smartplug(self, plug_id):
        """Turn on a smart plug."""
        url = fetch_action_endpoint(ActionEndpointType.TURN_ON_SMART_PLUG).uri()
        payload = {
            "PanelId": self._panel_id,
            "DeviceId": plug_id,
        }
        result: APIResponse = await self._post(url, payload)
        if result and result.is_ok():
            _LOGGER.debug("Smart plug %s turned on successfully", plug_id)
            return True
        else:
            _LOGGER.error("Failed to turn on smart plug %s", plug_id)
            return False

    async def turn_off_smartplug(self, plug_id):
        """Turn off a smart plug."""
        url = fetch_action_endpoint(ActionEndpointType.TURN_OFF_SMART_PLUG).uri()
        payload = {
            "PanelId": self._panel_id,
            "DeviceId": plug_id,
        }
        result: APIResponse = await self._post(url, payload)
        if result and result.is_ok():
            _LOGGER.debug("Smart plug %s turned off successfully", plug_id)
            return True
        else:
            _LOGGER.error("Failed to turn off smart plug %s", plug_id)
            return False

    async def get_camera_image(self, serial_no):
        """Retrieve the latest image from a camera."""
        url = f"{API_URL}/api/camera/GetCameraImage"
        payload = {
            "PanelId": self._panel_id,
            "SerialNo": serial_no,
        }
        response: APIResponse = await self._post(url, payload)
        if response and response.response_data.get("ImageData"):
            image_data = base64.b64decode(response["ImageData"])
            return image_data
        _LOGGER.error("Failed to retrieve image for camera %s", serial_no)
        return None

    async def logout(self):
        """Logout from the API."""
        logout_url = fetch_action_endpoint(ActionEndpointType.LOGOUT).uri()
        await self._post(logout_url, {})
