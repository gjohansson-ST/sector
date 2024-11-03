# coordinator.py
"""Coordinator for Sector Alarm integration."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL
from .sector import Sector

_LOGGER = logging.getLogger(__name__)

class SectorDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Sector Alarm data from the Sector API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize Sector Alarm coordinator."""
        self.api = Sector(
            username=config_entry.data["username"],
            password=config_entry.data["password"],
        )
        self.entry = config_entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Sector Alarm API."""
        return await self.api.get_all_data()

    async def triggeralarm(self, command: str, code: str, panel_id: str) -> None:
        """Trigger an alarm command."""
        await self.api.triggeralarm(command, code, panel_id)
