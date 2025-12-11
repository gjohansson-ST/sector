"""Client module for interacting with Sector Alarm API."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import aiohttp
import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_model import PanelInfo
from .endpoints import ACTION_ENDPOINTS, DataEndpointType, fetch_data_endpoints, fetch_action_endpoint, \
    ActionEndpointType

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""

class APIResponse:
    def __init__(self, response_code: int, response: Any):
        self.response_code = response_code
        self.response_data = response

    def __str__(self):
        return f"ApiResponse(response_code={self.response_code}, response_data={self.response_data})"

    def is_ok(self) -> bool:
        return self.response_code == 200

class SectorAlarmAPI:
    """Class to interact with the Sector Alarm API."""

    API_URL = "https://mypagesapi.sectoralarm.net"

    def __init__(self, hass: HomeAssistant, email, password, panel_id):
        """Initialize the API client."""
        self.hass = hass
        self.email = email
        self.password = password
        self.panel_id = panel_id
        self.access_token = None
        self.headers: dict[str, str] = {}
        self.session = None
        self.action_endpoints = ACTION_ENDPOINTS

    async def login(self):
        """Authenticate with the API and obtain an access token."""
        if self.session is None:
            self.session = async_get_clientsession(self.hass)

        login_url = fetch_action_endpoint(ActionEndpointType.LOGIN).uri()
        payload = {
            "userId": self.email,
            "password": self.password,
        }
        try:
            async with async_timeout.timeout(10):
                async with self.session.post(login_url, json=payload) as response:
                    if response.status != 200:
                        _LOGGER.error(
                            "Login failed with status code %s", response.status
                        )
                        raise AuthenticationError("Invalid credentials")
                    data = await response.json()
                    self.access_token = data.get("AuthorizationToken")
                    if not self.access_token:
                        _LOGGER.error("Login failed: No access token received")
                        raise AuthenticationError("Invalid credentials")
                    self.headers = {
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json",
                    }

        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout occurred during login")
            raise AuthenticationError("Timeout during login") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Client error during login: %s", str(err))
            raise AuthenticationError("Client error during login") from err

    async def get_panel_list(self) -> dict[str, str]:
        """Retrieve available panels from the API."""
        data = {}
        panellist_url = f"{self.API_URL}/api/account/GetPanelList"
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
        uri = f"{self.API_URL}/api/Panel/GetPanel?panelId={self.panel_id}"
        response: APIResponse = await self._get(uri)
        _LOGGER.debug(f"panel_payload: {response}")

        if response is None or response.is_ok() == False:
            _LOGGER.error("Failed to retrieve panel %s", self.panel_id)

        return response.response_data

    async def retrieve_all_data(self, data_endpoint_types: set[DataEndpointType]) -> dict[DataEndpointType, APIResponse]:
        """Retrieve all relevant data from the API."""
        data = {}
        data_endpoints = fetch_data_endpoints(data_endpoint_types)

        # Iterate over data endpoints
        for endpoint in data_endpoints:
            url = endpoint.uri(self.panel_id)
            if endpoint.method() == "GET":
                response: APIResponse = await self._get(url)
            elif endpoint.method() == "POST":
                # For POST requests, we need to provide the panel ID in the payload
                payload = {"PanelId": self.panel_id}
                response: APIResponse = await self._post(url, payload)
            else:
                _LOGGER.error("Unsupported HTTP method %s for endpoint %s", endpoint.method(), url)
                continue

            if response:
                data[endpoint.type()] = response
        return data

    async def _get(self, url) -> APIResponse | None:
        """Helper method to perform GET requests with timeout."""
        try:
            async with async_timeout.timeout(15):
                async with self.session.get(url, headers=self.headers) as response:
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
        except aiohttp.ClientError as e:
            _LOGGER.error("Client error during GET request to %s: %s", url, str(e))
            return None

    async def _post(self, url, payload) -> APIResponse | None:
        """Helper method to perform POST requests with timeout."""
        try:
            async with async_timeout.timeout(15):
                async with self.session.post(
                    url, json=payload, headers=self.headers
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
            "PanelId": self.panel_id,
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
            "PanelId": self.panel_id,
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
            "PanelId": self.panel_id,
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
            "PanelId": self.panel_id,
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
            "PanelId": self.panel_id,
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
            "PanelId": self.panel_id,
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
        url = f"{self.API_URL}/api/camera/GetCameraImage"
        payload = {
            "PanelId": self.panel_id,
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
