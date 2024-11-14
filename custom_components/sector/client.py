"""Client module for interacting with Sector Alarm API."""

from __future__ import annotations

import asyncio
import base64
import logging

import aiohttp
import async_timeout
from datetime import datetime, timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .endpoints import get_action_endpoints, get_data_endpoints
from .const import POLLING_INTERVALS, DEFAULT_POLLING_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""


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
        self.data_endpoints = get_data_endpoints(self.panel_id)
        self.action_endpoints = get_action_endpoints()

        self.last_update_times = {key: datetime.now() for key in self.data_endpoints}
        self.cached_data = {key: None for key in self.data_endpoints}

    async def login(self):
        """Authenticate with the API and obtain an access token."""
        if self.session is None:
            self.session = async_get_clientsession(self.hass)

        login_url = f"{self.API_URL}/api/Login/Login"
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
        response = await self._get(panellist_url)
        _LOGGER.debug(f"panel_payload: {response}")

        if response:
            data = {
                item["PanelId"]: item["DisplayName"]
                for item in response
                if "PanelId" in item
            }
        else:
            _LOGGER.error("Failed to retrieve any panels")

        return data

    async def retrieve_all_data(self) -> dict[str, Any]:
        """Retrieve data from API, using intervals for each endpoint."""
        current_time = datetime.now()
        data = {}

        for key, (method, url) in self.data_endpoints.items():
            interval = timedelta(seconds=POLLING_INTERVALS.get(key, DEFAULT_POLLING_INTERVAL))
            last_update = self.last_update_times.get(key)

            if last_update and current_time - last_update < interval:
                _LOGGER.debug("Interval not reached for %s; using cached data", key)
                data[key] = self.cached_data[key]  # Use cached data if interval not reached
                continue

            _LOGGER.debug("Polling data for %s", key)
            try:
                response = await (self._get(url) if method == "GET" else self._post(url, {"PanelId": self.panel_id}))
                if response:
                    data[key] = response
                    self.cached_data[key] = response  # Cache the data
                    self.last_update_times[key] = current_time
                else:
                    _LOGGER.info("No data retrieved for %s; using cached data", key)
                    data[key] = self.cached_data[key]
            except Exception as error:
                _LOGGER.error("Failed to update %s: %s", key, error)
                data[key] = self.cached_data[key]

        # Log remaining time to next update for debugging
        for endpoint, last_time in self.last_update_times.items():
            interval = timedelta(seconds=POLLING_INTERVALS.get(endpoint, DEFAULT_POLLING_INTERVAL))
            time_since_last_update = (current_time - last_time).total_seconds()
            time_until_next_update = interval.total_seconds() - time_since_last_update
            _LOGGER.debug(
                "Endpoint %s last updated %.2f seconds ago; %.2f seconds until next update",
                endpoint,
                time_since_last_update,
                max(0, time_until_next_update)
            )

        return data

    async def get_lock_status(self):
        """Retrieve the lock status."""
        url = f"{self.API_URL}/api/panel/GetLockStatus?panelId={self.panel_id}"
        response = await self._get(url)
        _LOGGER.debug("Retrieved lock status")
        if response:
            return response
        else:
            _LOGGER.error("Failed to retrieve lock status")
            return []

    async def _get(self, url):
        """Helper method to perform GET requests with timeout."""
        try:
            async with async_timeout.timeout(10):
                async with self.session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            return await response.json()
                        else:
                            text = await response.text()
                            _LOGGER.error(
                                "Received non-JSON response from %s: %s", url, text
                            )
                            return None
                    else:
                        text = await response.text()
                        _LOGGER.error(
                            "GET request to %s failed with status code %s, response: %s",
                            url,
                            response.status,
                            text,
                        )
                        return None
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout occurred during GET request to %s", url)
            return None
        except aiohttp.ClientError as e:
            _LOGGER.error("Client error during GET request to %s: %s", url, str(e))
            return None

    async def _post(self, url, payload):
        """Helper method to perform POST requests with timeout."""
        try:
            async with async_timeout.timeout(10):
                async with self.session.post(
                    url, json=payload, headers=self.headers
                ) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            return await response.json()
                        else:
                            text = await response.text()
                            _LOGGER.error(
                                "Received non-JSON response from %s: %s", url, text
                            )
                            return None
                    else:
                        text = await response.text()
                        _LOGGER.error(
                            "POST request to %s failed with status code %s, response: %s",
                            url,
                            response.status,
                            text,
                        )
                        return None
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
            url = self.action_endpoints["Arm"][1]
        elif mode == "partial":
            url = self.action_endpoints["PartialArm"][1]

        payload = {
            "PanelCode": panel_code,
            "PanelId": self.panel_id,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug("System armed successfully")
            return True
        else:
            _LOGGER.error("Failed to arm system")
            return False

    async def disarm_system(self, code: str):
        """Disarm the alarm system."""
        panel_code = code
        url = self.action_endpoints["Disarm"][1]
        payload = {
            "PanelCode": panel_code,
            "PanelId": self.panel_id,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug("System disarmed successfully")
            return True
        else:
            _LOGGER.error("Failed to disarm system")
            return False

    async def lock_door(self, serial_no: str, code: str):
        """Lock a specific door."""
        panel_code = code
        url = self.action_endpoints["Lock"][1]
        payload = {
            "LockSerial": serial_no,
            "PanelCode": panel_code,
            "PanelId": self.panel_id,
            "SerialNo": serial_no,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug("Door %s locked successfully", serial_no)
            return True
        else:
            _LOGGER.error("Failed to lock door %s", serial_no)
            return False

    async def unlock_door(self, serial_no: str, code: str):
        """Unlock a specific door."""
        panel_code = code
        url = self.action_endpoints["Unlock"][1]
        payload = {
            "LockSerial": serial_no,
            "PanelCode": panel_code,
            "PanelId": self.panel_id,
            "SerialNo": serial_no,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug("Door %s unlocked successfully", serial_no)
            return True
        else:
            _LOGGER.error("Failed to unlock door %s", serial_no)
            return False

    async def turn_on_smartplug(self, plug_id):
        """Turn on a smart plug."""
        url = self.action_endpoints["TurnOnSmartplug"][1]
        payload = {
            "PanelId": self.panel_id,
            "DeviceId": plug_id,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug("Smart plug %s turned on successfully", plug_id)
            return True
        else:
            _LOGGER.error("Failed to turn on smart plug %s", plug_id)
            return False

    async def turn_off_smartplug(self, plug_id):
        """Turn off a smart plug."""
        url = self.action_endpoints["TurnOffSmartplug"][1]
        payload = {
            "PanelId": self.panel_id,
            "DeviceId": plug_id,
        }
        result = await self._post(url, payload)
        if result is not None:
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
        response = await self._post(url, payload)
        if response and response.get("ImageData"):
            image_data = base64.b64decode(response["ImageData"])
            return image_data
        _LOGGER.error("Failed to retrieve image for camera %s", serial_no)
        return None

    async def logout(self):
        """Logout from the API."""
        logout_url = f"{self.API_URL}/api/Login/Logout"
        await self._post(logout_url, {})
