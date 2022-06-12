"""Sector alarm coordinator."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import async_timeout

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import API_URL, LOGGER

TIMEOUT = 8


class SectorAlarmHub:
    """Sector connectivity hub."""

    logname: str | None

    def __init__(
        self,
        sector_temp: bool,
        userid: str,
        password: str,
        timesync: int,
        websession: aiohttp.ClientSession,
    ) -> None:
        """Initialize the sector hub."""

        self.websession = websession
        self._sector_temp = sector_temp
        self._userid = userid
        self._password = password
        self._access_token: str | None = None
        self._last_updated: datetime = datetime.utcnow() - timedelta(hours=2)
        self._last_updated_temp: datetime = datetime.utcnow() - timedelta(hours=2)

        self._update_sensors: bool = True
        self._timesync = timesync

        self.api_data: dict[str, dict] = {}

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

        if command == "unlock":
            await self._request(API_URL + "/Panel/Unlock", json_data=message_json)
        if command == "lock":
            await self._request(API_URL + "/Panel/Lock", json_data=message_json)
        await self.fetch_info(False)

    async def triggerswitch(self, identity: str, command: str, panel_id: str) -> None:
        """Change status of switch."""

        message_json = {
            "PanelId": panel_id,
            "Platform": "app",
        }

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
        await self.fetch_info(False)

    async def triggeralarm(self, command: str, code: str, panel_id: str) -> None:
        """Change status of alarm."""

        message_json = {
            "PanelCode": code,
            "PanelId": panel_id,
            "Platform": "app",
        }

        if command == "full":
            await self._request(API_URL + "/Panel/Arm", json_data=message_json)
        if command == "partial":
            await self._request(API_URL + "/Panel/PartialArm", json_data=message_json)
        if command == "disarm":
            await self._request(API_URL + "/Panel/Disarm", json_data=message_json)
        await self.fetch_info(False)

    async def fetch_info(self, tempcheck: bool = True) -> None:
        """Fetch info from API."""
        response_panellist: list = await self._request(
            API_URL + "/account/GetPanelList"
        )
        if not response_panellist:
            raise UpdateFailed("Could not retrieve panels")
        panels = []
        for panel in response_panellist:
            self.api_data[panel["PanelId"]] = {"name": panel["DisplayName"]}
            panels.append(panel["PanelId"])

        now = datetime.utcnow()
        LOGGER.debug("self._last_updated_temp = %s", self._last_updated_temp)
        LOGGER.debug("self._timesync * 5 = %s", self._timesync * 5)
        LOGGER.debug(
            "Evaluate should temp sensors update %s", now - self._last_updated_temp
        )
        if not tempcheck:
            self._update_sensors = False
        elif now - self._last_updated_temp < timedelta(seconds=self._timesync * 10):
            self._update_sensors = False
        else:
            self._update_sensors = True
            self._last_updated_temp = now

        response_getuser: dict = await self._request(API_URL + "/Login/GetUser")
        self.logname = response_getuser.get("User", {}).get("UserName")

        for panel in panels:
            response_get_status: dict = await self._request(
                API_URL + "/Panel/GetPanelStatus?panelId={}".format(panel)
            )
            self.api_data[panel]["alarmstatus"] = response_get_status.get("Status")
            self.api_data[panel]["online"] = response_get_status.get("IsOnline")
            self.api_data[panel]["arm_ready"] = response_get_status.get("ReadyToArm")

            response_getpanel: dict = await self._request(
                API_URL + "/Panel/GetPanel?panelId={}".format(panel)
            )

            self.api_data[panel]["codelength"] = response_getpanel.get(
                "PanelCodeLength"
            )

            if temp_list := response_getpanel.get("Temperatures"):
                temp_dict = {}
                for temp in temp_list:
                    temp_dict[temp.get("SerialNo")] = {
                        "name": temp.get("Label"),
                        "serial": temp.get("SerialNo"),
                    }
                self.api_data[panel]["temp"] = temp_dict

            if lock_list := response_getpanel.get("Locks"):
                lock_dict = {}
                for lock in lock_list:
                    lock_dict[lock.get("Serial")] = {
                        "name": lock.get("Label"),
                        "serial": lock.get("Serial"),
                        "autolock": lock.get("AutoLockEnabled"),
                    }
                self.api_data[panel]["lock"] = lock_dict

            if switch_list := response_getpanel.get("Smartplugs"):
                switch_dict = {}
                for switch in switch_list:
                    switch_dict[switch.get("Id")] = {
                        "name": switch.get("Label"),
                        "serial": switch.get("SerialNo"),
                        "id": switch.get("Id"),
                    }
                self.api_data[panel]["switch"] = switch_dict

            if temp_list and self._sector_temp and self._update_sensors:
                response_temp: list = await self._request(
                    API_URL + "/Panel/GetTemperatures?panelId={}".format(panel)
                )
                if response_temp:
                    for temp in response_temp:
                        if serial := temp.get("SerialNo"):
                            self.api_data[panel]["temp"][serial][
                                "temperature"
                            ] = temp.get("Temprature")

            if lock_list:
                response_lock: list = await self._request(
                    API_URL + "/Panel/GetLockStatus?panelId={}".format(panel)
                )
                if response_lock:
                    for lock in response_lock:
                        if serial := lock.get("Serial"):
                            self.api_data[panel]["lock"][serial]["status"] = lock.get(
                                "Status"
                            )

            if switch_list:
                response_switch: list = await self._request(
                    API_URL + "/Panel/GetSmartplugStatus?panelId={}".format(panel)
                )
                if response_switch:
                    for switch in response_switch:
                        if switch_id := switch.get("Id"):
                            self.api_data[panel]["switch"][switch_id][
                                "status"
                            ] = switch.get("Status")

            response_logs: list = await self._request(
                API_URL + "/Panel/GetLogs?panelId={}".format(panel)
            )
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

            self.api_data[panel]["changed_by"] = (
                user_to_set if user_to_set else self.logname
            )

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

        try:
            with async_timeout.timeout(TIMEOUT):
                if json_data:
                    response = await self.websession.post(
                        url, json=json_data, headers=headers
                    )
                else:
                    response = await self.websession.get(url, headers=headers)

            if response.status == 401:
                self._access_token = None
                await asyncio.sleep(2)
                if retry > 0:
                    return await self._request(url, json_data, retry=retry - 1)

            if response.status in (200, 204):
                LOGGER.debug("Info retrieved successfully URL: %s", url)
                LOGGER.debug("request status: %s", response.status)

                output: dict | list = await response.json()
                return output

        except aiohttp.ContentTypeError as error:
            text = await response.text()
            LOGGER.error(
                "ContentTypeError connecting to Sector: %s, %s ",
                text,
                error,
                exc_info=True,
            )
            if "unauthorized" in error.message.lower():
                raise ConfigEntryAuthFailed from error
            raise UpdateFailed from error

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
                    return

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

    @property
    def data(self) -> dict[str, Any]:
        """Return data."""
        return self.api_data


class UnauthorizedError(HomeAssistantError):
    """Exception to indicate an error in authorization."""


class CannotConnectError(HomeAssistantError):
    """Exception to indicate an error in client connection."""


class OperationError(HomeAssistantError):
    """Exception to indicate an error in operation."""
