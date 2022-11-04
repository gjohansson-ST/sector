"""Sector alarm coordinator."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
import async_timeout

import aiohttp

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


from .const import API_URL, CONF_TEMP, DOMAIN, LOGGER, UPDATE_INTERVAL

TIMEOUT = 15
TO_REDACT = {
    "PanelCode",
    "PanelId",
}


class SectorDataUpdateCoordinator(DataUpdateCoordinator):
    """Sector Coordinator."""

    data: dict[str, Any]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sector hub."""

        self.websession = async_get_clientsession(hass)
        self._sector_temp: bool = entry.data[CONF_TEMP]
        self._userid: str = entry.data[CONF_USERNAME]
        self._password: str = entry.data[CONF_PASSWORD]
        self._access_token: str | None = None
        self._last_updated: datetime = datetime.utcnow() - timedelta(hours=2)
        self._last_updated_temp: datetime = datetime.utcnow() - timedelta(hours=2)
        self.logname: str | None = None

        self._update_sensors: bool = True
        self._timesync = entry.options.get(UPDATE_INTERVAL, 60)

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.options.get(UPDATE_INTERVAL, 60)),
        )

    async def triggerlock(
        self, lock: str, code: str, command: str, panel_id: str
    ) -> None:
        """Change status of lock."""

        message_json = {
            "LockSerial": lock,
            "PanelCode": code,
            "PanelId": panel_id,
            "Platform": "app",
        }

        try:
            if command == "unlock":
                await self._request(API_URL + "/Panel/Unlock", json_data=message_json)
                self.data[panel_id]["lock"][lock]["status"] = "unlock"
            if command == "lock":
                await self._request(API_URL + "/Panel/Lock", json_data=message_json)
                self.data[panel_id]["lock"][lock]["status"] = "lock"
        except (UpdateFailed, ConfigEntryAuthFailed) as error:
            raise HomeAssistantError(
                f"Could not lock {lock} on error {str(error)}"
            ) from error
        await self.async_request_refresh()

    async def triggerswitch(self, identity: str, command: str, panel_id: str) -> None:
        """Change status of switch."""

        message_json = {
            "PanelId": panel_id,
            "Platform": "app",
        }

        try:
            if command == "on":
                await self._request(
                    f"{API_URL}/Panel/TurnOnSmartplug?switchId={identity}&panelId={panel_id}",
                    json_data=message_json,
                )
                self.data[panel_id]["switch"][identity]["status"] = "On"
            if command == "off":
                await self._request(
                    f"{API_URL}/Panel/TurnOffSmartplug?switchId={identity}&panelId={panel_id}",
                    json_data=message_json,
                )
                self.data[panel_id]["switch"][identity]["status"] = "Off"
        except (UpdateFailed, ConfigEntryAuthFailed) as error:
            raise HomeAssistantError(
                f"Could not change switch {identity} on error {str(error)}"
            ) from error

        await self.async_request_refresh()

    async def triggeralarm(self, command: str, code: str, panel_id: str) -> None:
        """Change status of alarm."""

        message_json = {
            "PanelCode": code,
            "PanelId": panel_id,
            "Platform": "app",
        }

        try:
            if command == "full":
                await self._request(API_URL + "/Panel/Arm", json_data=message_json)
                self.data[panel_id]["alarmstatus"] = 3
            if command == "partial":
                await self._request(
                    API_URL + "/Panel/PartialArm", json_data=message_json
                )
                self.data[panel_id]["alarmstatus"] = 2
            if command == "disarm":
                await self._request(API_URL + "/Panel/Disarm", json_data=message_json)
                self.data[panel_id]["alarmstatus"] = 1
        except (UpdateFailed, ConfigEntryAuthFailed) as error:
            raise HomeAssistantError(
                f"Could not arm/disarm {panel_id} on error {str(error)}"
            ) from error

        await self.async_request_refresh()

    async def async_first_refresh(self) -> dict[str, Any]:
        """First refresh to get alarm system"""
        LOGGER.debug("Trying to get panels")
        response_panellist = await self._request(API_URL + "/account/GetPanelList")
        if not response_panellist:
            raise UpdateFailed("Could not retrieve panels")
        LOGGER.debug("Panels retrieved: %s", response_panellist)
        for panel in response_panellist:
            data: dict[str, Any] = {panel["PanelId"]: {}}
            data[panel["PanelId"]]["name"] = panel["DisplayName"]
            data[panel["PanelId"]]["id"] = panel["PanelId"]
            data[panel["PanelId"]]["alarmstatus"] = 0

            panel_id = panel["PanelId"]
            LOGGER.debug("trying to get Panel for panel_id: %s", panel_id)
            if panel_id is None:
                raise UpdateFailed("No panel_id found")

            response_getpanel = await self._request(
                API_URL + "/Panel/GetPanel?panelId={}".format(panel_id)
            )

            if not response_getpanel or not isinstance(response_getpanel, dict):
                raise UpdateFailed("Could not retrieve panel")

            LOGGER.debug("Panel retrieved: %s", response_getpanel)
            data[panel["PanelId"]]["codelength"] = response_getpanel.get(
                "PanelCodeLength"
            )

            if temp_list := response_getpanel.get("Temperatures"):
                LOGGER.debug("Extract Temperature info: %s", temp_list)
                temp_dict = {}
                for temp in temp_list:
                    temp_dict[temp.get("SerialNo")] = {
                        "name": temp.get("Label"),
                        "serial": temp.get("SerialNo"),
                    }
                data[panel["PanelId"]]["temp"] = temp_dict

            if lock_list := response_getpanel.get("Locks"):
                LOGGER.debug("Extract Locks info: %s", lock_list)
                lock_dict = {}
                for lock in lock_list:
                    lock_dict[lock.get("Serial")] = {
                        "name": lock.get("Label"),
                        "serial": lock.get("Serial"),
                        "autolock": lock.get("AutoLockEnabled"),
                    }
                data[panel["PanelId"]]["lock"] = lock_dict

            if switch_list := response_getpanel.get("Smartplugs"):
                LOGGER.debug("Extract Switch info: %s", switch_list)
                switch_dict = {}
                for switch in switch_list:
                    switch_dict[switch.get("Id")] = {
                        "name": switch.get("Label"),
                        "serial": switch.get("SerialNo"),
                        "id": switch.get("Id"),
                    }
                data[panel["PanelId"]]["switch"] = switch_dict

        LOGGER.debug("Trying to get user info")
        response_getuser = await self._request(API_URL + "/Login/GetUser")
        if not response_getuser or not isinstance(response_getuser, dict):
            raise UpdateFailed("Could not retrieve username")
        LOGGER.debug("User info retrieved %s", response_getuser)
        self.logname = response_getuser.get("User", {}).get("UserName")

        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch info from API."""
        data = self.data
        LOGGER.debug("Set data")
        if not data:
            LOGGER.debug("Data empty, going for first refresh")
            data = await self.async_first_refresh()
            LOGGER.debug("First refresh complete: %s", data)

        now = datetime.utcnow()
        LOGGER.debug("self._last_updated_temp = %s", self._last_updated_temp)
        LOGGER.debug("self._timesync * 5 = %s", self._timesync * 5)
        LOGGER.debug(
            "Evaluate should temp sensors update %s", now - self._last_updated_temp
        )
        if not self._sector_temp:
            self._update_sensors = False
        elif now - self._last_updated_temp < timedelta(seconds=self._timesync * 10):
            self._update_sensors = False
        else:
            self._update_sensors = True
            self._last_updated_temp = now
        LOGGER.debug("Should refresh Temp: %s", self._update_sensors)

        for key, panel in data.items():
            LOGGER.debug("Panel data: %s", panel)
            panel_id = panel.get("id")

            LOGGER.debug("Trying to get Panel status for panel_id: %s", panel_id)
            if panel_id is None:
                raise UpdateFailed("Missing panel_id")

            response_get_status = await self._request(
                API_URL + "/Panel/GetPanelStatus?panelId={}".format(panel_id)
            )
            if not response_get_status or not isinstance(response_get_status, dict):
                LOGGER.debug("Could not retrieve status for panel %s", panel_id)
            else:
                LOGGER.debug("Retrieved Panel status %s", response_get_status)
                data[key]["online"] = response_get_status.get("IsOnline")
                data[key]["alarmstatus"] = response_get_status.get("Status")
                data[key]["arm_ready"] = response_get_status.get("ReadyToArm")

            if data[key].get("temp") and self._update_sensors:
                LOGGER.debug("Trying to refresh temperatures")
                response_temp = await self._request(
                    API_URL + "/Panel/GetTemperatures?panelId={}".format(panel_id)
                )
                if not response_temp:
                    LOGGER.debug("Could not retrieve temp data for panel %s", panel_id)
                else:
                    LOGGER.debug("Temps refreshed: %s", response_temp)
                    for temp in response_temp:
                        if serial := temp.get("SerialNo"):
                            data[key]["temp"][serial]["temperature"] = temp.get(
                                "Temprature"
                            )

            if data[key].get("lock"):
                LOGGER.debug("Trying to refresh locks")
                response_lock = await self._request(
                    API_URL + "/Panel/GetLockStatus?panelId={}".format(panel_id)
                )
                if not response_lock:
                    LOGGER.debug("Could not retrieve lock data for panel %s", panel_id)
                else:
                    LOGGER.debug("Locks refreshed: %s", response_lock)
                    for lock in response_lock:
                        if serial := lock.get("Serial"):
                            data[key]["lock"][serial]["status"] = lock.get("Status")

            if data[key].get("switch"):
                LOGGER.debug("Trying to refresh switches")
                response_switch = await self._request(
                    API_URL + "/Panel/GetSmartplugStatus?panelId={}".format(panel_id)
                )
                if not response_switch:
                    LOGGER.debug(
                        "Could not retrieve switch data for panel %s", panel_id
                    )
                else:
                    LOGGER.debug("Switches refreshed: %s", response_switch)
                    for switch in response_switch:
                        if switch_id := switch.get("Id"):
                            data[key]["switch"][switch_id]["status"] = switch.get(
                                "Status"
                            )

            LOGGER.debug("Trying to refresh logs")
            response_logs = await self._request(
                API_URL + "/Panel/GetLogs?panelId={}".format(panel_id)
            )
            user_to_set: str | None = None
            if not response_logs:
                LOGGER.debug("Could not retrieve logs for panel %s", panel_id)
            else:
                LOGGER.debug("Logs refreshed: %s", response_logs)
                if response_logs:
                    log: dict
                    for log in response_logs:
                        user = log.get("User")
                        event_type: str | None = log.get("EventType")

                        user_to_set = self.logname
                        if event_type:
                            user_to_set = user if "arm" in event_type else self.logname
                            break

            data[key]["changed_by"] = user_to_set if user_to_set else self.logname
            LOGGER.debug("Log name set to: %s", data[key]["changed_by"])

        return data

    async def _request(
        self, url: str, json_data: dict | None = None, retry: int = 3
    ) -> dict | list | None:
        if self._access_token is None:
            LOGGER.debug("Access token None, trying to refresh")
            try:
                async with async_timeout.timeout(TIMEOUT):
                    await self._login()
            except aiohttp.ContentTypeError as error:
                LOGGER.error(
                    "ContentTypeError connecting to Sector: %s, %s ",
                    error.message,
                    error,
                    exc_info=True,
                )
            except asyncio.TimeoutError as error:
                LOGGER.warning("Timeout during login %s", str(error))
            except Exception as error:  # pylint: disable=broad-except
                if retry == 0:
                    LOGGER.error(
                        "Exception on last login attempt %s", str(error).lower()
                    )
                if "unauthorized" in str(error).lower():
                    raise ConfigEntryAuthFailed from error

            if self._access_token is None:
                LOGGER.debug("Access token still None, retry %d", retry)
                await asyncio.sleep(5)
                if retry > 0:
                    return await self._request(url, json_data, retry=retry - 1)
                raise ConfigEntryAuthFailed

        LOGGER.debug("Login passed")

        headers = {
            "Authorization": self._access_token,
            "API-Version": "6",
            "Platform": "iOS",
            "User-Agent": "  SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
            "Version": "2.0.27",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
        }
        try:
            async with async_timeout.timeout(TIMEOUT):
                if json_data:
                    LOGGER.debug(
                        "Request with post: %s and data %s",
                        url,
                        async_redact_data(json_data, TO_REDACT),
                    )
                    response = await self.websession.post(
                        url,
                        json=json_data,
                        headers=headers,
                        timeout=TIMEOUT,
                    )
                else:
                    LOGGER.debug("Request with get: %s", url)
                    response = await self.websession.get(
                        url,
                        headers=headers,
                        timeout=TIMEOUT,
                    )

        except asyncio.TimeoutError as error:
            LOGGER.warning(
                "Timeout during fetching %s with data %s",
                url,
                async_redact_data(json_data, TO_REDACT),
            )
            return None
        except aiohttp.ContentTypeError as error:
            LOGGER.debug("ContentTypeError: %s", error.message)
            if "unauthorized" in error.message.lower():
                raise ConfigEntryAuthFailed from error
            raise UpdateFailed from error
        except Exception as error:
            LOGGER.debug("Exception on request: %s", error)
            raise UpdateFailed from error

        if response.status == 401:
            LOGGER.debug("Response unauth, retry: %d", retry)
            self._access_token = None
            await asyncio.sleep(2)
            if retry > 0:
                return await self._request(url, json_data, retry=retry - 1)

        if response.status == 200:
            LOGGER.debug("Info retrieved successfully URL: %s", url)
            LOGGER.debug("request status: %s", response.status)

            try:
                output: dict | list = await response.json()
            except aiohttp.ContentTypeError as error:
                LOGGER.debug("ContentTypeError on ok status: %s", error.message)
                response_text = await response.text()
                LOGGER.debug("Response (200) text is: %s", response_text)
                raise UpdateFailed from error
            return output

        if response.status == 204:
            LOGGER.debug("Info retrieved successfully URL: %s", url)
            LOGGER.debug("request status: %s", response.status)
            return None

        LOGGER.debug("Did not retrieve information properly")
        LOGGER.debug("request status: %s", response.status)
        response_text = await response.text()
        LOGGER.debug("request text: %s", response_text)

        return None

    async def _login(self) -> None:
        """Login to retrieve access token."""

        LOGGER.debug("Trying to login")
        async with async_timeout.timeout(TIMEOUT):
            response = await self.websession.post(
                f"{API_URL}/Login/Login",
                headers={
                    "API-Version": "6",
                    "Platform": "iOS",
                    "User-Agent": "  SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
                    "Version": "2.0.27",
                    "Connection": "keep-alive",
                    "Content-Type": "application/json",
                },
                json={
                    "UserId": self._userid,
                    "Password": self._password,
                },
            )

        response_text = await response.text()

        if response.status == 401:
            LOGGER.debug("Response status 401: %s", response_text)
            self._access_token = None

        if response.status == 200:
            token_data = await response.json()
            LOGGER.debug("Response status ok: %s", token_data)
            self._access_token = token_data.get("AuthorizationToken")

        LOGGER.debug("Exiting login")
        LOGGER.debug("Status: %d", response.status)
        LOGGER.debug("Text: %s", response_text)


class UnauthorizedError(HomeAssistantError):
    """Exception to indicate an error in authorization."""


class CannotConnectError(HomeAssistantError):
    """Exception to indicate an error in client connection."""


class OperationError(HomeAssistantError):
    """Exception to indicate an error in operation."""
