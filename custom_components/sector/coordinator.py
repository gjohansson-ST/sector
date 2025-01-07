"""Sector Alarm coordinator."""

import logging
from datetime import datetime, timedelta
from typing import Any

from aiozoneinfo import async_get_time_zone
from homeassistant.components.recorder import get_instance, history
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from zoneinfo import ZoneInfoNotFoundError

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

    async def get_last_event_timestamp(self, device_name):
        """Get last event timestamp for a device."""
        entity_id = f"event.{device_name}_event_log"
        end_time = datetime.now(dt_util.UTC)
        start_time = end_time - timedelta(days=1)

        history_data = await get_instance(self.hass).async_add_executor_job(
            history.state_changes_during_period,
            self.hass,
            start_time,
            end_time,
            entity_id,
        )

        if entity_id in history_data and history_data[entity_id]:
            latest_state = history_data[entity_id][-1]
            _LOGGER.debug("SECTOR_EVENT: Latest known state: %s", latest_state)
            return datetime.fromisoformat(latest_state.last_changed.isoformat())

        return None

    def get_device_info(self, serial):
        """Fetch device information by serial number."""
        return self.data["devices"].get(
            serial, {"name": "Unknown Device", "model": "Unknown Model"}
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
            self._event_logs = await self._process_event_logs(logs_data, devices)

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

    @staticmethod
    def _get_event_id(log):
        """Create a unique identifier for each log event."""
        return f"{log['LockName']}_{log['EventType']}_{log['Time']}"

    def get_latest_log(self, event_type: str, lock_name: str = None):
        """Retrieve the latest log for a specific event type, optionally by LockName."""
        if not lock_name:
            _LOGGER.debug("Lock name not provided. Unable to fetch latest log.")
            return None

        # Normalize lock_name for consistent naming
        normalized_name = slugify(lock_name)
        entity_id = f"event.{normalized_name}_{normalized_name}_event_log"  # Adjusted format for entity IDs

        # Log the generated entity ID
        _LOGGER.debug("Generated entity ID for lock '%s': %s", lock_name, entity_id)

        state = self.hass.states.get(entity_id)

        if not state or not state.attributes:
            _LOGGER.debug("No state or attributes found for entity '%s'.", entity_id)
            return None

        _LOGGER.debug("Fetched state for entity '%s': %s", entity_id, state)

        # Extract the latest log matching the event type
        latest_event_type = state.state
        latest_time = state.attributes.get("timestamp")

        # Log the latest event type and timestamp
        _LOGGER.debug(
            "Latest event for entity '%s': type=%s, time=%s, attributes=%s",
            entity_id,
            latest_event_type,
            latest_time,
            state.attributes,
        )

        if latest_event_type == event_type and latest_time:
            try:
                parsed_time = datetime.fromisoformat(latest_time)
                _LOGGER.debug(
                    "Parsed latest event time for entity '%s': %s",
                    entity_id,
                    parsed_time,
                )
                return {
                    "event_type": latest_event_type,
                    "time": datetime.fromisoformat(latest_time),
                }
            except ValueError as err:
                _LOGGER.warning(
                    "Invalid timestamp format in entity '%s': %s (%s)",
                    entity_id,
                    latest_time,
                    err,
                )
                return None

        _LOGGER.debug(
            "No matching event found for type '%s' in entity '%s'.",
            event_type,
            entity_id,
        )
        return None

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

    async def _process_event_logs(self, logs, devices):
        """Process event logs, associating them with the correct lock devices using LockName."""
        grouped_events = {}

        # Get the user's configured timezone from Home Assistant
        user_time_zone = self.hass.config.time_zone or "UTC"
        try:
            tz = async_get_time_zone(user_time_zone)
        except ZoneInfoNotFoundError:
            _LOGGER.debug("Invalid timezone '%s', defaulting to UTC.", user_time_zone)
            tz = async_get_time_zone("UTC")

        records = list(reversed(logs.get("Records", [])))
        _LOGGER.debug("Processing %d log records", len(records))

        lock_names = {
            device["name"]: serial_no
            for serial_no, device in devices.items()
            if device.get("model") == "Smart Lock"
        }

        for log_entry in records:
            if not isinstance(log_entry, dict):
                _LOGGER.error("Skipping invalid log entry: %s", log_entry)
                continue

            lock_name = log_entry.get("LockName")
            event_type = log_entry.get("EventType")
            timestamp = log_entry.get("Time")
            user = log_entry.get("User", "")
            channel = log_entry.get("Channel", "")

            if not lock_name or not event_type or not timestamp:
                _LOGGER.debug("Skipping incomplete log entry: %s", log_entry)
                continue

            try:
                utc_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                local_time = utc_time.astimezone(tz)
                timestamp = local_time.isoformat()
            except ValueError:
                _LOGGER.error("Invalid timestamp in log entry: %s", log_entry)
                continue

            serial_no = lock_names.get(lock_name)
            if not serial_no:
                _LOGGER.debug(
                    "Unknown lock name '%s', skipping log entry: %s",
                    lock_name,
                    log_entry,
                )
                continue

            # Check against the latest event from Home Assistant
            latest_log = self.get_latest_log(event_type, lock_name)
            if latest_log:
                try:
                    latest_time = latest_log["time"]
                    if datetime.fromisoformat(timestamp) <= latest_time:
                        _LOGGER.debug(
                            "Skipping event for lock '%s' (serial %s): event is not newer than %s.",
                            lock_name,
                            serial_no,
                            latest_time,
                        )
                        continue
                except Exception as err:
                    _LOGGER.error(
                        "Error comparing timestamps for event: %s. Skipping event.",
                        err,
                    )
                    continue

            formatted_event = f"{lock_name} {event_type.replace('_', ' ')} by {user or 'unknown'} via {channel or 'unknown'}"

            # Group valid events
            grouped_events.setdefault(serial_no, {}).setdefault(event_type, []).append(
                {
                    "time": timestamp,
                    "user": user,
                    "channel": channel,
                    "formatted_event": formatted_event,
                }
            )

            _LOGGER.debug(
                "Processed event for lock '%s' (serial %s) with type '%s' at %s by %s via %s",
                lock_name,
                serial_no,
                event_type,
                timestamp,
                user or "unknown user",
                channel or "unknown channel",
            )

        _LOGGER.debug("Grouped events by lock: %s", grouped_events)
        return grouped_events

    @property
    def process_events(self) -> dict:
        """Return processed event logs grouped by device."""
        return self._event_logs
