"""Sector Alarm coordinator."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthenticationError, SectorAlarmAPI
from .const import CATEGORY_MODEL_MAPPING, CONF_PANEL_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Make sure the SectorAlarmConfigEntry type is present
type SectorAlarmConfigEntry = ConfigEntry[SectorDataUpdateCoordinator]


class SectorDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching from Sector Alarm."""

    config_entry: SectorAlarmConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SectorAlarmConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.api = SectorAlarmAPI(
            hass=hass,
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            panel_id=entry.data[CONF_PANEL_ID],
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Sector Alarm API."""
        try:
            await self.api.login()
            api_data = await self.api.retrieve_all_data()
            _LOGGER.debug("API ALL DATA: %s", api_data)

            # Process devices and panel status
            devices, panel_status = self._process_devices(api_data)

            # Process logs for event handling
            logs_data = api_data.get("Logs", [])
            self._event_logs = self._process_event_logs(logs_data, devices)

            return {
                "devices": devices,
                "panel_status": panel_status,
                "logs": self._event_logs,
            }

        except AuthenticationError as error:
            raise UpdateFailed(f"Authentication failed: {error}") from error
        except Exception as error:
            _LOGGER.exception("Failed to update data")
            raise UpdateFailed(f"Failed to update data: {error}") from error

    def _process_devices(self, api_data) -> tuple[dict[str, Any], dict[str, Any]]:
        """Process device data from the API, including humidity, closed, and alarm sensors."""
        devices: dict[str, Any] = {}
        panel_status = api_data.get("Panel Status", {})

        for category_name, category_data in api_data.items():
            if category_name in ["Logs", "Panel Status"]:
                continue

            _LOGGER.debug("Processing category: %s", category_name)
            if category_name == "Lock Status" and isinstance(category_data, list):
                self._process_locks(category_data, devices)
            else:
                self._process_category_devices(category_name, category_data, devices)

        return devices, panel_status

    def _process_locks(self, locks_data: list, devices: dict) -> None:
        """Process lock data and add to devices dictionary."""
        for lock in locks_data:
            serial_no = str(lock.get("Serial"))
            if not serial_no:
                _LOGGER.warning("Lock missing Serial: %s", lock)
                continue

            devices[serial_no] = {
                "name": lock.get("Label"),
                "serial_no": serial_no,
                "sensors": {
                    "lock_status": lock.get("Status"),
                    "low_battery": lock.get("BatteryLow"),
                },
                "model": "Smart Lock",
            }
            _LOGGER.debug(
                "Processed lock with serial_no %s: %s", serial_no, devices[serial_no]
            )

    def _process_category_devices(
        self, category_name: str, category_data: dict, devices: dict
    ) -> None:
        """Process devices within a specific category and add them to devices dictionary."""
        default_model_name = CATEGORY_MODEL_MAPPING.get(category_name, category_name)

        if isinstance(category_data, dict) and "Sections" in category_data:
            for section in category_data["Sections"]:
                for place in section.get("Places", []):
                    for component in place.get("Components", []):
                        serial_no = str(
                            component.get("SerialNo") or component.get("Serial")
                        )
                        if serial_no:
                            device_type = str(component.get("Type", "")).lower()
                            model_name = CATEGORY_MODEL_MAPPING.get(
                                device_type, default_model_name
                            )

                            # Initialize or update device entry with sensors
                            device_info = devices.setdefault(
                                serial_no,
                                {
                                    "name": component.get("Label")
                                    or component.get("Name"),
                                    "serial_no": serial_no,
                                    "sensors": {},
                                    "model": model_name,
                                    "type": component.get("Type", ""),
                                },
                            )

                            # Add or update each sensor in the device
                            self._add_sensor_if_present(
                                device_info["sensors"],
                                component,
                                "closed",
                                "Closed",
                                bool,
                            )
                            self._add_sensor_if_present(
                                device_info["sensors"],
                                component,
                                "low_battery",
                                ["LowBattery", "BatteryLow"],
                                bool,
                            )
                            self._add_sensor_if_present(
                                device_info["sensors"],
                                component,
                                "alarm",
                                "Alarm",
                                bool,
                            )
                            self._add_sensor_if_present(
                                device_info["sensors"],
                                component,
                                "temperature",
                                "Temperature",
                                float,
                            )
                            self._add_sensor_if_present(
                                device_info["sensors"],
                                component,
                                "humidity",
                                "Humidity",
                                float,
                            )

                            _LOGGER.debug(
                                "Processed device %s with model: %s, category: %s, type: %s",
                                serial_no,
                                model_name,
                                category_name,
                                device_type,
                            )
                        else:
                            _LOGGER.warning(
                                "Component missing SerialNo/Serial: %s", component
                            )
        else:
            _LOGGER.debug("Category %s does not contain Sections.", category_name)

    def _add_sensor_if_present(
        self,
        sensors: dict,
        component: dict,
        sensor_key: str,
        source_keys: Any,
        transform: type | None = None,
    ):
        """Add a sensor to the sensors dictionary if it exists in component."""
        if isinstance(source_keys, str):
            source_keys = [source_keys]

        for key in source_keys:
            if key in component:
                value = component[key]
                if transform:
                    try:
                        value = transform(value)
                    except ValueError as e:
                        _LOGGER.warning(
                            "Failed to transform value '%s' for key '%s': %s",
                            value,
                            key,
                            e,
                        )
                        return  # Skip adding this sensor if transformation fails

                # Add sensor to the dictionary if found and transformed successfully
                sensors[sensor_key] = value
                _LOGGER.debug(
                    "Successfully added sensor '%s' with value '%s' to sensors",
                    sensor_key,
                    value,
                )
                return  # Exit after the first match to avoid overwriting

        # Log a debug message if none of the source keys are found
        _LOGGER.debug(
            "Sensor keys %s were not found in component for sensor '%s'",
            source_keys,
            sensor_key,
        )

    def _process_event_logs(self, logs, devices):
        """Process event logs, associating them with the correct lock devices using LockName."""
        grouped_events = {}
        _LOGGER.debug("Starting event log processing. Total logs: %d", len(logs))

        lock_names = {
            device["name"]: serial_no
            for serial_no, device in devices.items()
            if device.get("model") == "Smart Lock"
        }

        for log_entry in logs:
            lock_name = log_entry.get("LockName")
            event_type = log_entry.get("EventType")
            timestamp = log_entry.get("Time")
            user = log_entry.get("User", "")
            channel = log_entry.get("Channel", "")

            if not lock_name or not event_type or not timestamp:
                _LOGGER.warning("Skipping invalid log entry: %s", log_entry)
                continue

            serial_no = lock_names.get(lock_name)
            if not serial_no:
                _LOGGER.debug(
                    "Log entry for unknown lock name '%s', skipping: %s",
                    lock_name,
                    log_entry,
                )
                continue

            if serial_no not in grouped_events:
                grouped_events[serial_no] = {}

            if event_type not in grouped_events[serial_no]:
                grouped_events[serial_no][event_type] = []

            grouped_events[serial_no][event_type].append(
                {
                    "time": timestamp,
                    "user": user,
                    "channel": channel,
                }
            )

            _LOGGER.debug(
                "Processed log entry for lock '%s' (serial %s) with event type '%s' at %s by %s via %s",
                lock_name,
                serial_no,
                event_type,
                timestamp,
                user or "unknown user",
                channel or "unknown channel",
            )

        _LOGGER.debug("Grouped events by lock: %s", grouped_events)
        return grouped_events

    async def process_events(self):
        """Return processed event logs grouped by device."""
        return self._event_logs
