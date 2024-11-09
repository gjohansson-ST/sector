"""Sector Alarm coordinator."""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime, timedelta, timezone

from homeassistant.components.recorder import history, get_instance
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthenticationError, SectorAlarmAPI
from .const import (
    CATEGORY_MODEL_MAPPING,
    CONF_PANEL_ID,
    DOMAIN,
    CONF_CODE_FORMAT,
)

type SectorAlarmConfigEntry = ConfigEntry[SectorDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
_lock_event_types = ["lock", "unlock", "lock_failed"]

def normalize_name(name):
    return ''.join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'
    ).lower()

class SectorDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching from Sector Alarm."""

    def __init__(self, hass: HomeAssistant, entry: SectorAlarmConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.code_format = entry.options.get(CONF_CODE_FORMAT, 6)
        _LOGGER.debug(
            "Initializing SectorDataUpdateCoordinator with code_format: %s",
            self.code_format,
        )
        self.api = SectorAlarmAPI(
            hass=hass,
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            panel_id=entry.data[CONF_PANEL_ID],
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    async def get_last_event_timestamp(self, device_name):
        """Fetch the last event timestamp from Home Assistant history for the specific device."""
        entity_id = f"event.{device_name}_event_log"
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=1)  # Assuming history within 1 day is sufficient

        # Use async_add_executor_job to avoid blocking the event loop
        history_data = await get_instance(self.hass).async_add_executor_job(
            history.state_changes_during_period,
            self.hass,
            start_time,
            end_time,
            entity_id
        )

        # Extract the latest timestamp if any history is found
        if entity_id in history_data and history_data[entity_id]:
            latest_state = history_data[entity_id][-1]  # Get the last entry
            _LOGGER.debug(f"Last available state for {device_name}: {latest_state}")
            return datetime.fromisoformat(latest_state.last_changed.isoformat())

        # Default to None if no history found
        return None

    async def process_events(self):
        """Process only new events and group them by device, based on the latest event timestamp."""
        _LOGGER.debug("Starting LockName-to-device mapping for logs")
        logs = self.data.get("logs", {}).get("Records", [])

        if not isinstance(logs, list):
            _LOGGER.error("Unexpected logs format, expected list of dictionaries")
            return {}

        grouped_events = {}
        event_timestamp_cache = {}

        for log in logs:
            lock_name = log.get("LockName")
            normalized_lock_name = normalize_name(lock_name)
            event_type = log.get("EventType")
            event_timestamp = datetime.fromisoformat(log.get("Time").replace("Z", "+00:00"))

            if lock_name not in event_timestamp_cache:
                event_timestamp_cache[normalized_lock_name] = await self.get_last_event_timestamp(normalized_lock_name)

            # Fetch the latest event timestamp for this device from history
            last_event_timestamp = event_timestamp_cache[normalized_lock_name]
            _LOGGER.debug("Fetched last event timestamp for lock_name '%s': %s", normalized_lock_name, last_event_timestamp)

            # Skip logs that are older than the latest event timestamp
            if last_event_timestamp and event_timestamp <= last_event_timestamp:
                _LOGGER.debug(
                    "Skipping log '%s' for %s as it's older than the last event timestamp %s >= %s",
                    event_type, lock_name, last_event_timestamp.isoformat(), event_timestamp.isoformat()
                )
                continue

            # Process new event as it's newer than the last history entry
            _LOGGER.debug("Processing new event: %s at %s", event_type, event_timestamp.isoformat())

            # Perform a full lookup to find the device by name
            matched_device = None
            for serial_no, device_info in self.data["devices"].items():
                if device_info.get("name") == lock_name:
                    matched_device = device_info
                    break

            if matched_device:
                _LOGGER.debug("LockName '%s' matched to device with serial '%s'", lock_name, matched_device["serial_no"])
                device_serial = matched_device["serial_no"]
                grouped_events.setdefault(device_serial, {}).setdefault("lock", []).append(log)

                _LOGGER.debug("Added log entry to grouped events for device '%s' with serial '%s'", lock_name, device_serial)
            else:
                _LOGGER.warning("No match found for LockName '%s'", lock_name)

        _LOGGER.debug("Final grouped events structure: %s", grouped_events)
        return grouped_events

    def get_device_info(self, serial):
        """Fetch device information by serial number."""
        return self.data["devices"].get(serial, {"name": "Unknown Device", "model": "Unknown Model"})

    async def _async_update_data(self):
        """Fetch data from Sector Alarm API."""
        data = {}  # Initialize data dictionary

        try:
            await self.api.login()
            api_data = await self.api.retrieve_all_data()

            for key, value in api_data.items():
                if isinstance(value, dict) and key not in ["Lock Status", "Logs"]:
                    data[key] = value
                    data[key]["code_format"] = self.code_format

            # Retrieve and limit logs to the latest 40 entries
            logs = api_data.get("Logs", [])
            if isinstance(logs, list):
                data["Logs"] = logs
            elif isinstance(logs, dict) and "Records" in logs:
                data["Logs"] = logs.get("Records", [])

            # Process devices, panel status, and lock status as usual
            devices = {}
            panel_status = api_data.get("Panel Status", {})
            locks_data = api_data.get("Lock Status", [])

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
                            devices[serial_no]["sensors"]["lock_status"] = lock.get(
                                "Status"
                            )
                            devices[serial_no]["sensors"]["low_battery"] = lock.get(
                                "BatteryLow"
                            )
                    else:
                        _LOGGER.warning("Lock missing Serial: %s", lock)
            else:
                _LOGGER.debug("No locks data found.")

            # Process devices from different categories
            for category_name, category_data in data.items():
                _LOGGER.debug("Processing category: %s", category_name)
                model_name = CATEGORY_MODEL_MAPPING.get(category_name, category_name)
                if category_name in [
                        "Doors and Windows",
                        "Smoke Detectors",
                        "Leakage Detectors",
                        "Cameras",
                        "Keypad",
                ]:
                    for section in category_data.get("Sections", []):
                        for place in section.get("Places", []):
                            for component in place.get("Components", []):
                                serial_no = str(
                                    component.get("SerialNo") or component.get("Serial")
                                )
                                device_type = component.get("Type", "")
                                device_type_lower = str(device_type).lower()

                                if device_type_lower in CATEGORY_MODEL_MAPPING:
                                    model = CATEGORY_MODEL_MAPPING[device_type_lower]
                                else:
                                    _LOGGER.debug(
                                        "Unknown device_type '%s' for serial '%s', falling back to category model '%s'",
                                        device_type,
                                        serial_no,
                                        model_name,
                                    )
                                    model = model_name  # Use category model as fallback

                                if serial_no:
                                    if serial_no not in devices:
                                        devices[serial_no] = {
                                            "name": component.get("Label")
                                            or component.get("Name"),
                                            "serial_no": serial_no,
                                            "sensors": {},
                                            "model": model,
                                            "type": device_type,
                                        }
                                    _LOGGER.debug(
                                        "Processed device %s with type '%s' and model '%s'",
                                        serial_no,
                                        device_type,
                                        model,
                                    )
                                    # Add sensors based on component data
                                    if "Closed" in component:
                                        devices[serial_no]["sensors"]["closed"] = (
                                            component["Closed"]
                                        )
                                    low_battery_value = component.get(
                                        "LowBattery", component.get("BatteryLow")
                                    )
                                    if low_battery_value is not None:
                                        devices[serial_no]["sensors"]["low_battery"] = (
                                            low_battery_value
                                        )
                                        _LOGGER.debug(
                                            "Assigned low_battery sensor for device %s with value %s",
                                            serial_no,
                                            low_battery_value,
                                        )
                                    else:
                                        _LOGGER.warning(
                                            "No LowBattery or BatteryLow found for device %s of type '%s'",
                                            serial_no,
                                            device_type,
                                        )
                                    if (
                                        "Humidity" in component
                                        and component["Humidity"]
                                    ):
                                        devices[serial_no]["sensors"]["humidity"] = (
                                            float(component["Humidity"])
                                        )
                                    if (
                                        "Temperature" in component
                                        and component["Temperature"]
                                    ):
                                        devices[serial_no]["sensors"]["temperature"] = (
                                            float(component["Temperature"])
                                        )
                                    if "LeakDetected" in component:
                                        devices[serial_no]["sensors"][
                                            "leak_detected"
                                        ] = component["LeakDetected"]
                                    if "Alarm" in component:
                                        devices[serial_no]["sensors"]["alarm"] = (
                                            component["Alarm"]
                                        )

                                else:
                                    _LOGGER.warning(
                                        "Component missing SerialNo: %s", component
                                    )

                elif category_name == "Temperatures":
                    _LOGGER.debug("Temperatures data received: %s", category_data)
                    if isinstance(category_data, dict) and "Sections" in category_data:
                        for section in category_data["Sections"]:
                            for place in section.get("Places", []):
                                for component in place.get("Components", []):
                                    serial_no = str(
                                        component.get("SerialNo")
                                        or component.get("Serial")
                                    )
                                    device_type = component.get("Type", "")
                                    device_type_lower = str(device_type).lower()

                                    if device_type_lower in CATEGORY_MODEL_MAPPING:
                                        model = CATEGORY_MODEL_MAPPING[
                                            device_type_lower
                                        ]
                                    else:
                                        _LOGGER.debug(
                                            "Unknown device_type '%s' for serial '%s', falling back to category model '%s'",
                                            device_type,
                                            serial_no,
                                            model_name,
                                        )
                                        model = (
                                            model_name  # Use category model as fallback
                                        )

                                    if serial_no:
                                        if serial_no not in devices:
                                            devices[serial_no] = {
                                                "name": component.get("Label")
                                                or component.get("Name"),
                                                "serial_no": serial_no,
                                                "sensors": {},
                                                "model": model,
                                                "type": device_type,
                                            }
                                        temperature = component.get("Temperature")
                                        if temperature is not None:
                                            devices[serial_no]["sensors"][
                                                "temperature"
                                            ] = float(temperature)
                                            _LOGGER.debug(
                                                "Stored temperature %s for device %s",
                                                temperature,
                                                serial_no,
                                            )
                                        else:
                                            _LOGGER.debug(
                                                "No temperature value for device %s",
                                                serial_no,
                                            )
                                        low_battery_value = component.get(
                                            "LowBattery", component.get("BatteryLow")
                                        )
                                        if low_battery_value is not None:
                                            devices[serial_no]["sensors"][
                                                "low_battery"
                                            ] = low_battery_value
                                            _LOGGER.debug(
                                                "Assigned low_battery sensor for device %s with value %s",
                                                serial_no,
                                                low_battery_value,
                                            )
                                        else:
                                            _LOGGER.warning(
                                                "No LowBattery or BatteryLow found for device %s of type '%s'",
                                                serial_no,
                                                device_type,
                                            )

                                    else:
                                        _LOGGER.warning(
                                            "Component missing SerialNo: %s", component
                                        )
                    else:
                        _LOGGER.error(
                            "Unexpected data format for Temperatures: %s", category_data
                        )

                elif category_name == "Humidity":
                    _LOGGER.debug("Humidity data received: %s", category_data)
                    if isinstance(category_data, dict) and "Sections" in category_data:
                        for section in category_data["Sections"]:
                            for place in section.get("Places", []):
                                for component in place.get("Components", []):
                                    serial_no = str(
                                        component.get("SerialNo")
                                        or component.get("Serial")
                                    )
                                    device_type = component.get("Type", "")
                                    device_type_lower = str(device_type).lower()

                                    if device_type_lower in CATEGORY_MODEL_MAPPING:
                                        model = CATEGORY_MODEL_MAPPING[
                                            device_type_lower
                                        ]
                                    else:
                                        _LOGGER.debug(
                                            "Unknown device_type '%s' for serial '%s', falling back to category model '%s'",
                                            device_type,
                                            serial_no,
                                            model_name,
                                        )
                                        model = (
                                            model_name  # Use category model as fallback
                                        )

                                    if serial_no:
                                        if serial_no not in devices:
                                            devices[serial_no] = {
                                                "name": component.get("Label")
                                                or component.get("Name"),
                                                "serial_no": serial_no,
                                                "sensors": {},
                                                "model": model,
                                                "type": device_type,
                                            }
                                            _LOGGER.debug(
                                                "Registering device %s with model: %s",
                                                serial_no,
                                                model_name,
                                            )
                                        humidity = component.get("Humidity")
                                        if humidity is not None:
                                            devices[serial_no]["sensors"][
                                                "humidity"
                                            ] = float(humidity)
                                        else:
                                            _LOGGER.debug(
                                                "No humidity value for device %s",
                                                serial_no,
                                            )
                                    else:
                                        _LOGGER.warning(
                                            "Component missing SerialNo: %s", component
                                        )
                    else:
                        _LOGGER.error(
                            "Unexpected data format for Humidity: %s", category_data
                        )

                elif category_name == "Smartplug Status":
                    _LOGGER.debug("Smartplug data received: %s", category_data)
                    if isinstance(category_data, list):
                        devices["smartplugs"] = category_data
                    else:
                        _LOGGER.warning(
                            "Unexpected smartplug data format: %s", category_data
                        )

                elif category_name == "Lock Status":
                    # Locks data is already retrieved in locks_data
                    pass

                elif category_name == "Panel Status":
                    # Panel status is already retrieved
                    pass

                elif category_name == "Logs":
                    # Logs are already retrieved
                    pass

                else:
                    _LOGGER.debug("Unhandled category %s", category_data)

            for serial, device_info in devices.items():
                _LOGGER.debug("Initialized device with name '%s' and serial '%s'", device_info["name"], serial)

            return {
                "devices": devices,
                "panel_status": panel_status,
                "logs": logs,
            }

        except AuthenticationError as error:
            _LOGGER.error("Authentication failed: %s", error)
            raise UpdateFailed(f"Authentication failed: {error}") from error
        except Exception as error:
            _LOGGER.exception("Failed to update data")
            raise UpdateFailed(f"Failed to update data: {error}") from error

    @staticmethod
    def _get_event_id(log):
        """Create a unique identifier for each log event."""
        return f"{log['LockName']}_{log['EventType']}_{log['Time']}"

    def get_latest_log(self, event_type: str, lock_name: str = None):
        """Retrieve the latest log for a specific event type, optionally by LockName."""
        logs = self.data.get("logs", [])
        for log in logs:
            if log.get("EventType") == event_type and (lock_name is None or log.get("LockName") == lock_name):
                return log
        _LOGGER.debug("No matching log found for event type '%s' and lock name '%s'", event_type, lock_name)
        return None  # Return None if no matching log is found
