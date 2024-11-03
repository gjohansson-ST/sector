# sector.py
"""Sector Alarm API integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from datetime import timedelta
import asyncio
import logging

from .const import DOMAIN, API_URL, UPDATE_INTERVAL, LOGGER, CONF_PANEL_CODE, CONF_PANEL_ID

TIMEOUT = 15


class SectorDataUpdateCoordinator(DataUpdateCoordinator[dict[str, any]]):
    """Sector Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sector hub."""
        self.hass = hass
        self.websession = async_get_clientsession(hass)
        self._username = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]
        self._panel_code = entry.data[CONF_PANEL_CODE]
        self._panel_id = entry.data[CONF_PANEL_ID]
        self._auth_token: str | None = None

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, any]:
        """Fetch data from Sector API."""
        if not self._auth_token:
            await self._authenticate()

        headers = {
            "Authorization": self._auth_token,
            "Content-Type": "application/json",
            "API-Version": "5",
        }
        try:
            async with asyncio.timeout(TIMEOUT):
                response = await self.websession.get(
                    f"{API_URL}/api/panel/GetPanelStatus?panelId={self._panel_id}",
                    headers=headers,
                )
                response.raise_for_status()
                data = await response.json()
                return data
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}")

    async def _authenticate(self) -> None:
        """Authenticate with Sector API and retrieve auth token."""
        headers = {
            "Content-Type": "application/json",
            "API-Version": "5",
        }
        data = {
            "UserId": self._username,
            "Password": self._password,
        }
        try:
            async with asyncio.timeout(TIMEOUT):
                response = await self.websession.post(
                    f"{API_URL}/api/Login/Login", headers=headers, json=data
                )
                response.raise_for_status()
                response_data = await response.json()
                self._auth_token = response_data.get("AuthorizationToken")
        except Exception as err:
            raise ConfigEntryAuthFailed(f"Error authenticating: {err}")
