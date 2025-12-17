"""Sector Alarm coordinator."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfoNotFoundError

import pytz
from aiozoneinfo import async_get_time_zone
from homeassistant.components.recorder import history
from homeassistant.helpers.recorder import get_instance
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .api_model import PanelStatus, SmartPlug, Temperature, Lock, HouseCheck, LogRecords
from .client import (
    AuthenticationError,
    SectorAlarmAPI,
    PanelInfo,
    APIResponse,
    LoginError,
)
from .const import CATEGORY_MODEL_MAPPING, CONF_PANEL_ID, DOMAIN
from .endpoints import (
    MANDATORY_DATA_ENDPOINT_TYPES,
    OPTIONAL_DATA_ENDPOINT_TYPES,
    DataEndpointType,
)

_LOGGER = logging.getLogger(__name__)

# Make sure the SectorAlarmConfigEntry type is present
type SectorAlarmConfigEntry = ConfigEntry[SectorDataUpdateCoordinator]


class SectorDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching from Sector Alarm."""

    config_entry: SectorAlarmConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SectorAlarmConfigEntry,
        sector_api: SectorAlarmAPI,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.api = sector_api
        self._panel_id = entry.data[CONF_PANEL_ID]
        self._use_legacy_api = (True,)
        self._legacy_temperature_last_update: Optional[datetime] = None
        self._data_endpoints: set[DataEndpointType] = set()
        self._event_logs: dict[str, Any] = {}
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

    async def _async_setup(self):
        try:
            panel_info: PanelInfo = await self.api.get_panel_info()

            if panel_info is None:
                raise UpdateFailed("Unable to fetch information from Sector Alarm")

            mandatory_endpoint_types = MANDATORY_DATA_ENDPOINT_TYPES.copy()
            optional_endpoint_types = OPTIONAL_DATA_ENDPOINT_TYPES.copy()
            temperatures: list[Temperature] = panel_info.get("Temperatures", {})
            locks: list[Lock] = panel_info.get("Locks", {})
            plugs: list[SmartPlug] = panel_info.get("Smartplugs", {})

            if temperatures.__len__() == 0:
                self._use_legacy_api = False
                optional_endpoint_types.remove(DataEndpointType.TEMPERATURES_LEGACY)
            if locks.__len__() == 0:
                optional_endpoint_types.remove(DataEndpointType.LOCK_STATUS)
            if plugs.__len__() == 0:
                optional_endpoint_types.remove(DataEndpointType.SMART_PLUG_STATUS)

            # Scan and build supported endpoints
            api_data: dict[
                DataEndpointType, APIResponse
            ] = await self.api.retrieve_all_data(optional_endpoint_types)
            for endpoint_type, response in api_data.items():
                if response.response_code == 404:
                    optional_endpoint_types.remove(endpoint_type)

            supported_endpoint_types = (
                mandatory_endpoint_types | optional_endpoint_types
            )
            _LOGGER.debug("Supported endpoint types: %s", supported_endpoint_types)
            self._data_endpoints = supported_endpoint_types
            self.data = {
                "devices": {},
                "logs": {}
            }

        except LoginError as error:
            raise ConfigEntryAuthFailed from error
        except AuthenticationError as error:
            raise UpdateFailed(f"Authentication failed: {error}") from error
        except Exception as error:
            _LOGGER.exception("Failed to update data")
            raise UpdateFailed(f"Failed to update data: {error}") from error

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Sector Alarm API."""
        try:
            if self._use_legacy_api:
                api_data = await self._legacy_retrieve_all_data()
            else:
                api_data = await self.api.retrieve_all_data(self._data_endpoints)
            _LOGGER.debug("API ALL DATA: %s", api_data)

            # Process devices
            devices = self._process_devices(api_data)

            # Process logs for event handling
            if (
                DataEndpointType.LOGS in api_data
                and api_data[DataEndpointType.LOGS].is_ok()
            ):
                log_data: LogRecords = api_data[DataEndpointType.LOGS].response_data
                self._event_logs = await self._process_event_logs(log_data, devices)

            # Update device information
            current_device_data: dict[str, Any] = (self.data["devices"]).copy()
            current_device_data.update(devices)

            return {
                "devices": current_device_data,
                "logs": self._event_logs,
            }

        except LoginError as error:
            raise ConfigEntryAuthFailed from error
        except AuthenticationError as error:
            raise UpdateFailed(f"Authentication failed: {error}") from error
        except Exception as error:
            _LOGGER.exception("Failed to update data")
            raise UpdateFailed(f"Failed to update data: {error}") from error

    async def _legacy_retrieve_all_data(self):
        now = datetime.now(tz=dt_util.UTC)
        # Only refresh legacy temperatures every 15 min as they are costly
        if (
            self._legacy_temperature_last_update
            and now - self._legacy_temperature_last_update < timedelta(minutes=15)
        ):
            redacted_temperatures = {
                e
                for e in self._data_endpoints
                if e != DataEndpointType.TEMPERATURES_LEGACY
            }
            return await self.api.retrieve_all_data(redacted_temperatures)

        data = await self.api.retrieve_all_data(self._data_endpoints)
        self._legacy_temperature_last_update = now
        return data

    @staticmethod
    def _get_event_id(log):
        """Create a unique identifier for each log event."""
        return f"{log['LockName']}_{log['EventType']}_{log['Time']}"

    def get_latest_log(self, event_type: str, lock_name: str):
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

    def _process_devices(
        self, api_data: dict[DataEndpointType, APIResponse]
    ) -> dict[str, Any]:
        """Process device data from the API, including humidity, closed, and alarm sensors."""
        devices: dict[str, Any] = {}
        for category_name, category_data in api_data.items():
            if category_name in [DataEndpointType.LOGS]:
                continue

            _LOGGER.debug("Processing category: %s", category_name)
            if (
                category_data is None
                or category_data.response_data is None
                or not category_data.is_ok()
            ):
                _LOGGER.warning(
                    "Unable to process data for category '%s': data=%s",
                    category_name,
                    category_data,
                )
                continue

            response_data = category_data.response_data
            if category_name == DataEndpointType.PANEL_STATUS:
                self._process_alarm_panel(response_data, devices)
            elif category_name == DataEndpointType.SMART_PLUG_STATUS:
                self._process_smart_plugs(response_data, devices)
            elif category_name == DataEndpointType.LOCK_STATUS:
                self._process_locks(response_data, devices)
            elif category_name == DataEndpointType.TEMPERATURES_LEGACY:
                self._process_legacy_temperatures(response_data, devices)
            else:
                self._process_housecheck_devices(category_name, response_data, devices)

        return devices

    def _process_legacy_temperatures(
        self, temps_data: list[Temperature], devices: dict
    ) -> None:
        """Process legacy temperatures"""
        for temp in temps_data:
            serial_no = temp.get("SerialNo") or temp.get("Serial")
            if not serial_no:
                _LOGGER.warning("Temperature sensor is missing Serial: %s", temp)
                continue

            devices[serial_no] = {
                "name": temp.get("Label"),
                "serial_no": serial_no,
                "sensors": {
                    "temperature": temp.get("Temperature"),
                },
                "model": "Temperature Sensor",
            }
            _LOGGER.debug(
                "Processed temperature sensor with serial_no %s: %s",
                serial_no,
                devices[serial_no],
            )

    def _process_smart_plugs(
        self, smart_plug_data: list[SmartPlug], devices: dict
    ) -> None:
        """Process smart plugs data and add to devices dictionary."""
        for smart_plug in smart_plug_data:
            serial_no = smart_plug.get("SerialNo") or smart_plug.get("Serial")
            plug_id = smart_plug.get("Id")
            if not serial_no or not plug_id:
                _LOGGER.warning("Smart Plug is missing SerialNo or ID: %s", smart_plug)
                continue

            devices[serial_no] = {
                "name": smart_plug.get("Label"),
                "id": plug_id,
                "serial_no": serial_no,
                "sensors": {"plug_status": smart_plug.get("Status")},
                "model": "Smart Plug",
            }
            _LOGGER.debug(
                "Processed smart plug with Serial %s: %s", serial_no, devices[serial_no]
            )

    def _process_alarm_panel(
        self, panel_status_data: PanelStatus, devices: dict
    ) -> None:
        """Process alarm panel status data and add to devices dictionary."""
        serial_no = self._panel_id
        devices["alarm_panel"] = {
            "name": "Alarm Control Panel",
            "serial_no": serial_no,
            "sensors": {
                "online": panel_status_data.get("IsOnline"),
                "alarm_status": panel_status_data.get("Status"),
            },
            "model": "Sector Alarm Control Panel",
        }
        _LOGGER.debug(
            "Processed alarm panel with Serial %s: %s",
            serial_no,
            devices["alarm_panel"],
        )

    def _process_locks(self, locks_data: list[Lock], devices: dict) -> None:
        """Process lock data and add to devices dictionary."""
        for lock in locks_data:
            serial_no = lock.get("SerialNo") or lock.get("Serial")
            if not serial_no:
                _LOGGER.warning("Lock is missing Serial: %s", lock)
                continue

            name = lock.get("Label")
            lock_status = lock.get("Status")
            low_battery = lock.get("BatteryLow")
            if low_battery is None:
                low_battery = lock.get("LowBattery")

            devices[serial_no] = {
                "name": name,
                "serial_no": serial_no,
                "sensors": {
                    "lock_status": lock_status,
                    **({"low_battery": low_battery} if low_battery is not None else {}),
                },
                "model": "Smart Lock",
            }

            _LOGGER.debug(
                "Processed lock with serial_no %s: %s", serial_no, devices[serial_no]
            )

    def _process_housecheck_devices(
        self, category_name: DataEndpointType, category_data: HouseCheck, devices: dict
    ) -> None:
        """Process devices within a specific category and add them to devices dictionary."""
        default_model_name = category_name.value

        if "Sections" in category_data:
            for section in category_data["Sections"]:
                for place in section.get("Places", []):
                    for component in place.get("Components", []):
                        serial_no = component.get("SerialNo") or component.get("Serial")

                        if serial_no is None:
                            _LOGGER.warning(
                                "Component missing SerialNo/Serial: %s", component
                            )
                            continue

                        device_type = str(component.get("Type", "")).lower()
                        model_name = CATEGORY_MODEL_MAPPING.get(
                            device_type, default_model_name
                        )

                        sensors = {}
                        if component["Closed"] is not None:
                            sensors["closed"] = component["Closed"]

                        if component["LowBattery"] is not None:
                            sensors["low_battery"] = component["LowBattery"]

                        if component["BatteryLow"] is not None:
                            sensors["low_battery"] = component["BatteryLow"]

                        if component["Alarm"] is not None:
                            sensors["alarm"] = component["Alarm"]

                        if component["Temperature"] is not None:
                            sensors["temperature"] = component["Temperature"]

                        if component["Humidity"] is not None:
                            sensors["humidity"] = component["Humidity"]

                        if sensors.__len__() == 0:
                            _LOGGER.debug(
                                "No sensors were found in component for category '%s'",
                                category_name,
                            )

                        # Initialize or update device entry with sensors
                        device_info = devices.setdefault(
                            serial_no,
                            {
                                "name": component.get("Label") or component.get("Name"),
                                "serial_no": serial_no,
                                "sensors": sensors,
                                "model": model_name,
                                "type": component.get("Type", ""),
                            },
                        )

                        _LOGGER.debug(
                            "Processed device: category: %s, device: %s",
                            category_name,
                            device_info,
                        )

        else:
            _LOGGER.debug("Category %s does not contain Sections", category_name)

    async def _process_event_logs(self, logs: LogRecords, devices):
        """Process event logs, associating them with the correct lock devices using LockName."""
        grouped_events = {}

        # Get the user's configured timezone from Home Assistant
        user_time_zone = self.hass.config.time_zone or "UTC"
        try:
            tz = pytz.timezone(self.hass.config.time_zone)
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

    def get_processed_events(self) -> dict:
        """Return processed event logs grouped by device."""
        return self._event_logs
