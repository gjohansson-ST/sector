"""Sector Alarm coordinator."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SectorAlarmAPI, AuthenticationError
from .const import (
    CONF_PANEL_CODE,
    CONF_PANEL_ID,
    DOMAIN,
    LOGGER,
    CONF_EMAIL,
    CONF_PASSWORD,
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
            data = await self.api.retrieve_all_data()

            devices = {}
            logs = data.get("Logs", [])
            panel_status = data.get("Panel Status", {})
            locks_data = data.get("Lock Status", [])

            # Process devices from different categories
            for category_name, category_data in data.items():
                if category_name in ["Doors and Windows", "Smoke Detectors", "Leakage Detectors"]:
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
                                    if "Humidity" in component and component["Humidity"]:
                                        devices[serial_no]["sensors"]["humidity"] = float(component["Humidity"])
                                    if "Temperature" in component and component["Temperature"]:
                                        devices[serial_no]["sensors"]["temperature"] = float(component["Temperature"])
                                else:
                                    LOGGER.warning(f"Component missing SerialNo: {component}")

                elif category_name == "Temperatures":
                    for temp_device in category_data:
                        serial_no = str(temp_device.get("DeviceId") or temp_device.get("SerialNo"))
                        if serial_no:
                            if serial_no not in devices:
                                devices[serial_no] = {
                                    "name": temp_device.get("Label") or temp_device.get("Name"),
                                    "serial_no": serial_no,
                                    "sensors": {},
                                }
                            temperature = temp_device.get("Temperature")
                            if temperature:
                                devices[serial_no]["sensors"]["temperature"] = float(temperature)
                        else:
                            LOGGER.warning(f"Temperature device missing SerialNo: {temp_device}")

                elif category_name == "Humidity":
                    for humidity_device in category_data:
                        serial_no = str(humidity_device.get("DeviceId") or humidity_device.get("SerialNo"))
                        if serial_no:
                            if serial_no not in devices:
                                devices[serial_no] = {
                                    "name": humidity_device.get("Label") or humidity_device.get("Name"),
                                    "serial_no": serial_no,
                                    "sensors": {},
                                }
                            humidity = humidity_device.get("Humidity")
                            if humidity:
                                devices[serial_no]["sensors"]["humidity"] = float(humidity)
                        else:
                            LOGGER.warning(f"Humidity device missing SerialNo: {humidity_device}")

            # Process locks
            locks = []
            for lock in locks_data:
                locks.append(lock)

            return {
                "devices": devices,
                "locks": locks,
                "panel_status": panel_status,
                "logs": logs,
            }

        except AuthenticationError as error:
            raise UpdateFailed(f"Authentication failed: {error}") from error
        except Exception as error:
            LOGGER.exception("Failed to update data")
            raise UpdateFailed(f"Failed to update data: {error}") from error
