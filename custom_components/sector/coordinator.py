"""Sector alarm coordinator."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import API_URL, CONF_TEMP, DOMAIN, LOGGER, MIN_SCAN_INTERVAL

TIMEOUT = 15
TO_REDACT = {
    "PanelCode",
    "PanelId",
}


class SectorDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Sector Coordinator."""

    data: dict[str, Any]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sector hub."""

        self.websession = async_get_clientsession(hass)
        self._sector_temp: bool = entry.data[CONF_TEMP]
        self._userid: str = entry.data[CONF_USERNAME]
        self._password: str = entry.data[CONF_PASSWORD]
        self._access_token: str | None = None
        self._last_updated: datetime = datetime.now(tz=dt_util.UTC) - timedelta(hours=2)
        self._last_updated_temp: datetime = datetime.now(tz=dt_util.UTC) - timedelta(
            hours=2
        )
        self.logname: str | None = None

        self._update_sensors: bool = True
        self._timesync = MIN_SCAN_INTERVAL

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=MIN_SCAN_INTERVAL),
        )

    async def async_first_refresh(self) -> dict[str, Any]:
        """First refresh to get alarm system."""
        LOGGER.debug("Trying to get panels")
        response_panellist = await self._request(API_URL + "/account/GetPanelList")
        if not response_panellist:
            raise UpdateFailed("Could not retrieve panels")
        LOGGER.debug("Panels retrieved: %s", response_panellist)
        return_data = {}
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
                API_URL + f"/Panel/GetPanel?panelId={panel_id}"
            )

            if not response_getpanel or not isinstance(response_getpanel, dict):
                raise UpdateFailed("Could not retrieve panel")

            LOGGER.debug("Panel retrieved: %s", response_getpanel)
            data[panel["PanelId"]]["codelength"] = response_getpanel.get(
                "PanelCodeLength"
            )

            response_doors_windows = await self._request(
                API_URL + "/v2/housecheck/doorsandwindows",
                json_data={"panelId": panel_id}
            )
            if not response_doors_windows:
                LOGGER.warning("Could not retrieve doors and windows data for panel %s", panel_id)
            else:
                LOGGER.debug("Doors and windows data retrieved: %s", response_doors_windows)
                doors_windows_dict = {}
                for section in response_doors_windows.get("Sections", []):
                    for place in section.get("Places", []):
                        for component in place.get("Components", []):
                            serial_str = component.get("SerialString")
                            doors_windows_dict[serial_str] = {
                                "Closed": component.get("Closed"),
                                "LowBattery": component.get("LowBattery"),
                                "Name": component.get("Name"),
                                "Location": place.get("Name"),
                            }
                data[panel["PanelId"]]["doors_and_windows"] = doors_windows_dict

            return_data.update(data.copy())

        LOGGER.debug("Trying to get user info")
        response_getuser = await self._request(API_URL + "/Login/GetUser")
        if not response_getuser or not isinstance(response_getuser, dict):
            raise UpdateFailed("Could not retrieve username")
        LOGGER.debug("User info retrieved %s", response_getuser)
        self.logname = response_getuser.get("User", {}).get("UserName")

        return return_data

    async def _request(
        self, url: str, json_data: dict | None = None, retry: int = 3
    ) -> dict | list | None:
        if self._access_token is None:
            await self._login()

        headers = {
            "Authorization": self._access_token,
            "API-Version": "6",
            "Platform": "iOS",
            "User-Agent": "SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
            "Version": "2.0.27",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
        }
        try:
            async with asyncio.timeout(TIMEOUT):
                if json_data:
                    response = await self.websession.post(
                        url,
                        json=json_data,
                        headers=headers,
                        timeout=TIMEOUT,
                    )
                else:
                    response = await self.websession.get(
                        url,
                        headers=headers,
                        timeout=TIMEOUT,
                    )

        except Exception as error:
            if retry == 0:
                raise UpdateFailed from error
            await asyncio.sleep(2)
            return await self._request(url, json_data, retry=retry - 1)

        if response.status == 200:
            try:
                output: dict | list = await response.json()
            except aiohttp.ContentTypeError as error:
                response_text = await response.text()
                raise UpdateFailed from error
            return output

        if response.status == 204:
            return None

        response_text = await response.text()
        return None

    async def _login(self) -> None:
        async with asyncio.timeout(TIMEOUT):
            response = await self.websession.post(
                f"{API_URL}/Login/Login",
                headers={
                    "API-Version": "6",
                    "Platform": "iOS",
                    "User-Agent": "SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
                    "Version": "2.0.27",
                    "Connection": "keep-alive",
                    "Content-Type": "application/json",
                },
                json={
                    "UserId": self._userid,
                    "Password": self._password,
                },
            )

        if response.status == 200:
            token_data = await response.json()
            self._access_token = token_data.get("AuthorizationToken")
