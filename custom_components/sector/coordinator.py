"""Sector Alarm coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SectorAlarmAPI, AuthenticationError
from .const import (
    CONF_PANEL_CODE,
    CONF_PANEL_ID,
    DOMAIN,
    CONF_EMAIL,
    CONF_PASSWORD,
)

_LOGGER = logging.getLogger(__name__)


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
            _LOGGER,
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
                                    if "LeakDetected" in component:
                                        devices[serial_no]["sensors"]["leak_detected"] = component["LeakDetected"]
                                    if "SmokeDetected" in component:
                                        devices[serial_no]["sensors"]["smoke_detected"] = component["SmokeDetected"]
                                else:
                                    _LOGGER.warning(f"Component missing SerialNo: {component}")

                elif category_name == "Temperatures":
                    _LOGGER.debug(f"Temperatures data received: {category_data}")
                    if isinstance(category_data, dict) and "Sections" in category_data:
                        for section in category_data["Sections"]:
                            for place in section.get("Places", []):
                                for component in place.get("Components", []):
                                    serial_no = str(component.get("SerialNo") or component.get("Serial"))
                                    if serial_no:
                                        if serial_no not in devices:
                                            devices[serial_no] = {
                                                "name": component.get("Label") or component.get("Name"),
                                                "serial_no": serial_no,
                                                "sensors": {},
                                                "model": component.get("DeviceTypeName", "Temperature Sensor"),
                                            }
                                        temperature = component.get("Temperature")
                                        if temperature is not None:
                                            devices[serial_no]["sensors"]["temperature"] = float(temperature)
                                            _LOGGER.debug(f"Stored temperature {temperature} for device {serial_no}")
                                        else:
                                            _LOGGER.debug(f"No temperature value for device {serial_no}")
                                    else:
                                        _LOGGER.warning(f"Component missing SerialNo: {component}")
                    else:
                        _LOGGER.error(f"Unexpected data format for Temperatures: {category_data}")

                elif category_name == "Humidity":
                    _LOGGER.debug(f"Humidity data received: {category_data}")
                    if isinstance(category_data, dict) and "Sections" in category_data:
                        for section in category_data["Sections"]:
                            for place in section.get("Places", []):
                                for component in place.get("Components", []):
                                    serial_no = str(component.get("SerialNo") or component.get("Serial"))
                                    if serial_no:
                                        if serial_no not in devices:
                                            devices[serial_no] = {
                                                "name": component.get("Label") or component.get("Name"),
                                                "serial_no": serial_no,
                                                "sensors": {},
                                                "model": component.get("DeviceTypeName", "Humidity Sensor"),
                                            }
                                        humidity = component.get("Humidity")
                                        if humidity is not None:
                                            devices[serial_no]["sensors"]["humidity"] = float(humidity)
                                        else:
                                            _LOGGER.debug(f"No humidity value for device {serial_no}")
                                    else:
                                        _LOGGER.warning(f"Component missing SerialNo: {component}")
                    else:
                        _LOGGER.error(f"Unexpected data format for Humidity: {category_data}")


                elif category_name == "Smartplug Status":
                    _LOGGER.debug(f"Smartplug data received: {category_data}")
                    if isinstance(category_data, list):
                        devices["smartplugs"] = category_data
                    else:
                        _LOGGER.warning(f"Unexpected smartplug data format: {category_data}")

                elif category_name == "Lock Status":
                    # Locks data is already retrieved in locks_data
                    pass

                elif category_name == "Panel Status":
                    # Panel status is already retrieved
                    pass

                else:
                    _LOGGER.debug(f"Unhandled category {category_name}")

        # Process locks
        if locks_data:
            for lock in locks_data:
                serial_no = str(lock.get("Serial"))
                if serial_no:
                    if serial_no not in devices:
                        devices[serial_no] = {
                            "name": lock.get("Label"),
                            "serial_no": serial_no,
                            "sensors": {},
                            "model": "Smart Lock",
                        }
                    devices[serial_no]["sensors"]["lock_status"] = lock.get("Status")
                    devices[serial_no]["sensors"]["low_battery"] = lock.get("BatteryLow")
                else:
                    _LOGGER.warning(f"Lock missing Serial: {lock}")
        else:
            _LOGGER.debug("No locks data found.")

            return {
                "devices": devices,
                "locks": locks,
                "panel_status": panel_status,
                "logs": logs,
            }

        except AuthenticationError as error:
            raise UpdateFailed(f"Authentication failed: {error}") from error
        except Exception as error:
            _LOGGER.exception("Failed to update data")
            raise UpdateFailed(f"Failed to update data: {error}") from error
