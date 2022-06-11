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

    logname: str

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
            self.api_data[panel["PanelId"]] = {
                "name": panel["DisplayName"],
                "alarmstatus": panel["Status"],
            }
            panels.append(panel["PanelId"])

        now = datetime.utcnow()
        LOGGER.debug("self._last_updated_temp = %s", self._last_updated_temp)
        LOGGER.debug("self._timesync * 5 = %s", self._timesync * 5)
        LOGGER.debug(
            "Evaluate should temp sensors update %s", now - self._last_updated_temp
        )
        if not tempcheck:
            self._update_sensors = False
        elif now - self._last_updated_temp < timedelta(seconds=self._timesync * 5):
            self._update_sensors = False
        else:
            self._update_sensors = True
            self._last_updated_temp = now

        response_getuser: dict = await self._request(API_URL + "/Login/GetUser")
        self.logname = response_getuser["User"]["UserName"]

        for panel in panels:
            response_getpanel: dict = await self._request(
                API_URL + "/GetPanel?panelId={}".format(panel)
            )

            self.api_data[panel]["codelength"] = response_getpanel["PanelCodeLength"]
            self.api_data[panel]["online"] = response_getpanel["IsOnline"]
            self.api_data[panel]["arm_ready"] = response_getpanel["ReadyToArm"]

            temps = []
            locks = []
            switches = []
            if response_getpanel["Temperatures"]:
                temps = response_getpanel["Temperatures"]
            if response_getpanel["Locks"]:
                locks = response_getpanel["Locks"]
            if response_getpanel["Smartplugs"]:
                switches = response_getpanel["Smartplugs"]

            if temps and self._sector_temp and self._update_sensors:
                response_temp: dict = await self._request(
                    API_URL + "/Panel/GetTemperatures?panelId={}".format(panel)
                )
                if response_temp:
                    temp_dict = {}
                    for temp in response_temp:
                        temp_dict[temp["SerialNo"]] = {
                            "name": temp["Label"],
                            "serial": temp["SerialNo"],
                            "temperature": temp["Temprature"],
                        }

                    self.api_data[panel]["temp"] = temp_dict

            if locks:
                response_lock: dict = await self._request(
                    API_URL + "/Panel/GetLockStatus?panelId={}".format(panel)
                )
                if response_lock:
                    lock_dict = {}
                    for lock in response_lock:
                        lock_dict[lock["Serial"]] = {
                            "name": lock["Label"],
                            "serial": lock["Serial"],
                            "status": lock["Status"],
                            "autolock": lock["AutoLockEnabled"],
                        }

                    self.api_data[panel]["lock"] = lock_dict

            if switches:
                response_switch: dict = await self._request(
                    API_URL + "/Panel/GetSmartplugStatus?panelId={}".format(panel)
                )
                if response_switch:
                    switch_dict = {}
                    for switch in response_switch:
                        switch_dict[switch["Id"]] = {
                            "name": switch["Label"],
                            "serial": switch["SerialNo"],
                            "status": switch["Status"],
                            "id": switch["Id"],
                        }

                    self.api_data[panel]["switch"] = switch_dict

            response_logs: list = await self._request(
                API_URL + "/Panel/GetLogs?panelId={}".format(panel)
            )
            if response_logs:
                for users in response_logs:
                    if users["User"] != "" and "arm" in users["EventType"]:
                        self.api_data[panel]["changed_by"] = users["User"]
                        break
                    self.api_data[panel]["changed_by"] = self.logname

    async def _request(
        self, url: str, json_data: dict | None = None, retry: int = 3
    ) -> dict | list:
        if self._access_token is None:
            try:
                await self._login()
            except Exception as error:  # pylint: disable=broad-except
                if "unauthorized" in str(error.args[0]).lower():
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

        except aiohttp.ClientConnectorError as error:
            raise UpdateFailed from error

        except aiohttp.ContentTypeError as error:
            text = await response.text()
            LOGGER.error(
                "ContentTypeError connecting to Sector: %s, %s ",
                text,
                error,
                exc_info=True,
            )
            if "unauthorized" in str(error.args[0]).lower():
                raise ConfigEntryAuthFailed from error
            raise UpdateFailed from error

        except asyncio.TimeoutError as error:
            raise UpdateFailed from error

        except asyncio.CancelledError as error:
            raise UpdateFailed from error

        return output

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
                    self._access_token = token_data["AuthorizationToken"]

        except aiohttp.ClientConnectorError as error:
            LOGGER.error("ClientError connecting to Sector: %s ", error, exc_info=True)

        except aiohttp.ContentTypeError as error:
            text = await response.text()
            LOGGER.error(
                "ContentTypeError connecting to Sector: %s, %s ",
                text,
                error,
                exc_info=True,
            )

        except asyncio.TimeoutError:
            LOGGER.error("Timed out when connecting to Sector")

        except asyncio.CancelledError:
            LOGGER.error("Task was cancelled")

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
