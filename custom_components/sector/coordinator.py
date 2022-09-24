"""Sector alarm coordinator."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL, CONF_TEMP, DOMAIN, LOGGER, UPDATE_INTERVAL

TIMEOUT = 8


class SectorDataUpdateCoordinator(DataUpdateCoordinator):
    """Sector Coordinator."""

    data: dict[str, Any]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sector hub."""

        self.websession = async_get_clientsession(hass)
        self._sector_temp = entry.data[CONF_TEMP]
        self._userid = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]
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
            if command == "lock":
                await self._request(API_URL + "/Panel/Lock", json_data=message_json)
        except (UpdateFailed, ConfigEntryAuthFailed) as error:
            raise HomeAssistantError from error
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
            if command == "off":
                await self._request(
                    f"{API_URL}/Panel/TurnOffSmartplug?switchId={identity}&panelId={panel_id}",
                    json_data=message_json,
                )
        except (UpdateFailed, ConfigEntryAuthFailed) as error:
            raise HomeAssistantError from error

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
            if command == "partial":
                await self._request(
                    API_URL + "/Panel/PartialArm", json_data=message_json
                )
            if command == "disarm":
                await self._request(API_URL + "/Panel/Disarm", json_data=message_json)
        except (UpdateFailed, ConfigEntryAuthFailed) as error:
            raise HomeAssistantError from error

        await self.async_request_refresh()

    async def async_first_refresh(self) -> dict[str, Any]:
        """First refresh to get alarm system"""
        response_panellist = await self._request(API_URL + "/account/GetPanelList")
        if not response_panellist:
            raise UpdateFailed("Could not retrieve panels")
        for panel in response_panellist:
            data: dict[str, Any] = {panel["PanelId"]: {}}
            data[panel["PanelId"]]["name"] = panel["DisplayName"]
            data[panel["PanelId"]]["id"] = panel["PanelId"]

            response_getpanel = await self._request(
                API_URL + "/Panel/GetPanel?panelId={}".format(panel)
            )

            if not response_getpanel or not isinstance(response_getpanel, dict):
                raise UpdateFailed("Could not retrieve panel")

            data[panel["PanelId"]]["codelength"] = response_getpanel.get(
                "PanelCodeLength"
            )

            if temp_list := response_getpanel.get("Temperatures"):
                temp_dict = {}
                for temp in temp_list:
                    temp_dict[temp.get("SerialNo")] = {
                        "name": temp.get("Label"),
                        "serial": temp.get("SerialNo"),
                    }
                data[panel["PanelId"]]["temp"] = temp_dict

            if lock_list := response_getpanel.get("Locks"):
                lock_dict = {}
                for lock in lock_list:
                    lock_dict[lock.get("Serial")] = {
                        "name": lock.get("Label"),
                        "serial": lock.get("Serial"),
                        "autolock": lock.get("AutoLockEnabled"),
                    }
                data[panel["PanelId"]]["lock"] = lock_dict

            if switch_list := response_getpanel.get("Smartplugs"):
                switch_dict = {}
                for switch in switch_list:
                    switch_dict[switch.get("Id")] = {
                        "name": switch.get("Label"),
                        "serial": switch.get("SerialNo"),
                        "id": switch.get("Id"),
                    }
                data[panel["PanelId"]]["switch"] = switch_dict

        response_getuser = await self._request(API_URL + "/Login/GetUser")
        if not response_getuser or not isinstance(response_getuser, dict):
            raise UpdateFailed("Could not retrieve username")
        self.logname = response_getuser.get("User", {}).get("UserName")

        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch info from API."""
        data = self.data
        if not data:
            data = await self.async_first_refresh()

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

        for panel in data:
            response_get_status = await self._request(
                API_URL + "/Panel/GetPanelStatus?panelId={}".format(panel)
            )
            if not response_get_status or not isinstance(response_get_status, dict):
                raise UpdateFailed("Could not retrieve status")

            data[panel]["alarmstatus"] = response_get_status.get("Status")
            data[panel]["online"] = response_get_status.get("IsOnline")
            data[panel]["arm_ready"] = response_get_status.get("ReadyToArm")

            if data[panel]["temp"] and self._sector_temp and self._update_sensors:
                response_temp = await self._request(
                    API_URL + "/Panel/GetTemperatures?panelId={}".format(panel)
                )
                if not response_temp:
                    raise UpdateFailed("Could not retrieve temp data")
                if response_temp:
                    for temp in response_temp:
                        if serial := temp.get("SerialNo"):
                            data[panel]["temp"][serial]["temperature"] = temp.get(
                                "Temprature"
                            )

            if data[panel]["lock"]:
                response_lock = await self._request(
                    API_URL + "/Panel/GetLockStatus?panelId={}".format(panel)
                )
                if not response_lock:
                    raise UpdateFailed("Could not retrieve lock data")
                if response_lock:
                    for lock in response_lock:
                        if serial := lock.get("Serial"):
                            data[panel]["lock"][serial]["status"] = lock.get("Status")

            if data[panel]["switch"]:
                response_switch = await self._request(
                    API_URL + "/Panel/GetSmartplugStatus?panelId={}".format(panel)
                )
                if not response_switch:
                    raise UpdateFailed("Could not retrieve switch data")
                if response_switch:
                    for switch in response_switch:
                        if switch_id := switch.get("Id"):
                            data[panel]["switch"][switch_id]["status"] = switch.get(
                                "Status"
                            )

            response_logs = await self._request(
                API_URL + "/Panel/GetLogs?panelId={}".format(panel)
            )
            if not response_logs:
                raise UpdateFailed("Could not retrieve logs")
            user_to_set: str | None = None
            if response_logs:
                log: dict
                for log in response_logs:
                    user = log.get("User")
                    event_type: str | None = log.get("EventType")

                    user_to_set = self.logname
                    if event_type:
                        user_to_set = user if "arm" in event_type else self.logname
                        break

            data[panel]["changed_by"] = user_to_set if user_to_set else self.logname

        return data

    async def _request(
        self, url: str, json_data: dict | None = None, retry: int = 3
    ) -> dict | list | None:
        if self._access_token is None:
            try:
                await self._login()
            except Exception as error:  # pylint: disable=broad-except
                if "unauthorized" in str(error).lower():
                    raise ConfigEntryAuthFailed from error
            if self._access_token is None:
                await asyncio.sleep(5)
                if retry > 0:
                    return await self._request(url, json_data, retry=retry - 1)
                raise ConfigEntryAuthFailed

        headers = {
            "Authorization": self._access_token,
            "API-Version": "6",
            "Platform": "iOS",
            "User-Agent": "  SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
            "Version": "2.0.27",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
        }
        with async_timeout.timeout(TIMEOUT):
            try:
                if json_data:
                    response = await self.websession.post(
                        url, json=json_data, headers=headers
                    )
                else:
                    response = await self.websession.get(url, headers=headers)

            except aiohttp.ContentTypeError as error:
                if "unauthorized" in error.message.lower():
                    raise ConfigEntryAuthFailed from error
                raise UpdateFailed from error
            except Exception as error:
                raise UpdateFailed from error

        if response.status == 401:
            self._access_token = None
            await asyncio.sleep(2)
            if retry > 0:
                return await self._request(url, json_data, retry=retry - 1)

        if response.status in (200, 204):
            LOGGER.debug("Info retrieved successfully URL: %s", url)
            LOGGER.debug("request status: %s", response.status)

            try:
                output: dict | list = await response.json()
            except aiohttp.ContentTypeError as error:
                raise UpdateFailed from error
            return output

        LOGGER.debug("Did not retrieve information properly")
        LOGGER.debug("request status: %s", response.status)
        LOGGER.debug("request text: %s", response.text())

        return None

    async def _login(self) -> None:
        """Login to retrieve access token."""
        try:
            with async_timeout.timeout(TIMEOUT):
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

                if response.status == 401:
                    self._access_token = None

                if response.status in (200, 204):
                    token_data = await response.json()
                    self._access_token = token_data.get("AuthorizationToken")

        except aiohttp.ContentTypeError as error:
            text = await response.text()
            LOGGER.error(
                "ContentTypeError connecting to Sector: %s, %s ",
                text,
                error,
                exc_info=True,
            )


class UnauthorizedError(HomeAssistantError):
    """Exception to indicate an error in authorization."""


class CannotConnectError(HomeAssistantError):
    """Exception to indicate an error in client connection."""


class OperationError(HomeAssistantError):
    """Exception to indicate an error in operation."""
