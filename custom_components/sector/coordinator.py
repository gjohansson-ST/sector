"""Sector Alarm coordinator."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SectorAlarmAPI, AuthenticationError
from .const import (
    CONF_PANEL_CODE,
    CONF_PANEL_ID,
    DOMAIN,
    LOGGER,
)


class SectorDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching from Sector Alarm."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.api = SectorAlarmAPI(
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            panel_id=entry.data[CONF_PANEL_ID],
            panel_code=entry.data[CONF_PANEL_CODE],
        )
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self):
        """Fetch data from Sector Alarm API."""
        try:
            await self.api.login()
            data = await self.hass.async_add_executor_job(self.api.retrieve_all_data)

            # Parse data and extract devices using SerialNo as unique identifiers
            devices = {}
            locks = data.get("Lock Status", [])
            panels = data.get("Panel Status", {})
            logs = data.get("Logs", [])

            # Process devices from different categories
            for category_name, category_data in data.items():
                if category_name in ["Doors and Windows", "Smoke Detectors", "Temperatures", "Humidity"]:
                    for section in category_data.get("Sections", []):
                        for place in section.get("Places", []):
                            for component in place.get("Components", []):
                                serial_no = str(component.get("SerialNo") or component.get("Serial"))
                                if serial_no:
                                    if serial_no not in devices:
                                        devices[serial_no] = {
                                            "name": component.get("Label") or component.get("Name"),
                                            "serial_no": serial_no,
                                            "sensors": {},
                                        }
                                    # Add sensors based on component data
                                    if "Closed" in component:
                                        devices[serial_no]["sensors"]["closed"] = component["Closed"]
                                    if "LowBattery" in component:
                                        devices[serial_no]["sensors"]["low_battery"] = component["LowBattery"]
                                    if "Humidity" in component:
                                        devices[serial_no]["sensors"]["humidity"] = component["Humidity"]
                                    if "Temperature" in component:
                                        devices[serial_no]["sensors"]["temperature"] = component["Temperature"]

            # Process locks
            locks_data = []
            for lock in locks:
                locks_data.append(lock)

            return {
                "devices": devices,
                "locks": locks_data,
                "panel_status": panels,
                "logs": logs,
            }

        except AuthenticationError as error:
            raise UpdateFailed(f"Authentication failed: {error}") from error
