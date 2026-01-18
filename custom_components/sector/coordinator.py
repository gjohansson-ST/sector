"""Sector Alarm coordinator."""

from enum import Enum
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import history
from homeassistant.helpers.recorder import get_instance
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .api_model import (
    PanelInfo,
    PanelStatus,
    SmartPlug,
    Temperature,
    Lock,
    HouseCheck,
    LogRecords,
)
from .client import (
    ApiError,
    AuthenticationError,
    SectorAlarmAPI,
    APIResponse,
    LoginError,
)
from .const import CONF_PANEL_ID
from .endpoints import (
    DataEndpointType,
)

_LOGGER = logging.getLogger(__name__)


class SectorCoordinatorType(Enum):
    PANEL_INFO = "Panel Info Coordinator"
    ACTION_DEVICES = "Action Devices Coordinator"
    SENSOR_DEVICES = "Sensor Devices Coordinator"


# Make sure the SectorAlarmConfigEntry type is present
type SectorAlarmConfigEntry = ConfigEntry[
    dict[
        SectorCoordinatorType,
        DataUpdateCoordinator,
    ]
]

_PANEL_INFO_UPDATE_INTERVAL = timedelta(minutes=5)
_ACTION_UPDATE_INTERVAL = timedelta(seconds=60)
_SENSOR_UPDATE_INTERVAL = timedelta(minutes=15)


class SectorBaseDataUpdateCoordinator(DataUpdateCoordinator):
    """Base class for Sector Alarm Data Update Coordinators."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SectorAlarmConfigEntry,
        sector_api: SectorAlarmAPI,
        name: str,
        update_interval: timedelta,
    ) -> None:
        self._hass = hass
        self.sector_api = sector_api
        self.panel_id = config_entry.data[CONF_PANEL_ID]
        self._update_error_counter: int = 0
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )

    def _increment_update_error_counter(self):
        self._update_error_counter += 1

    def _reset_update_error_counter(self):
        self._update_error_counter = 0

    def is_healthy(self) -> bool:
        """Determine if the coordinator is healthy based on error count."""
        return self._update_error_counter < 3


class SectorPanelInfoDataUpdateCoordinator(SectorBaseDataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: SectorAlarmConfigEntry,
        sector_api: SectorAlarmAPI,
    ) -> None:
        super().__init__(
            hass=hass,
            config_entry=entry,
            sector_api=sector_api,
            name="SectorPanelInfoDataUpdateCoordinator",
            update_interval=_PANEL_INFO_UPDATE_INTERVAL,
        )

    async def _async_setup(self):
        await self._fetch_data()

    async def _async_update_data(self) -> dict[str, Any]:
        return await self._fetch_data()

    async def _fetch_data(self) -> dict[str, Any]:
        try:
            response = await self.sector_api.get_panel_info()
            if not response.is_ok():
                raise UpdateFailed(
                    f"Failed to retrieve panel information for panel '{self.panel_id}' (HTTP {response.response_code} - {response.response_data})"
                )
            if not response.is_json():
                raise UpdateFailed(
                    f"Failed to retrieve panel information for panel '{self.panel_id}' (response data is not JSON '{response.response_data}')"
                )
            panel_info: PanelInfo = response.response_data
            if panel_info is None:
                raise UpdateFailed(
                    f"Failed to retrieve panel information for panel '{self.panel_id}' (no data returned from API)"
                )

            self._reset_update_error_counter()
            return {"panel_info": panel_info}

        except LoginError as error:
            self._increment_update_error_counter()
            raise ConfigEntryAuthFailed from error
        except AuthenticationError as error:
            self._increment_update_error_counter()
            raise UpdateFailed(str(error)) from error
        except ApiError as error:
            self._increment_update_error_counter()
            raise UpdateFailed(str(error)) from error


class SectorActionDataUpdateCoordinator(SectorBaseDataUpdateCoordinator):
    _MANDATORY_ENDPOINT_TYPES = {DataEndpointType.PANEL_STATUS, DataEndpointType.LOGS}

    _OPTIONAL_DATA_ENDPOINT_TYPES = {
        DataEndpointType.LOCK_STATUS,
        DataEndpointType.SMART_PLUG_STATUS,
        DataEndpointType.DOORS_AND_WINDOWS, # Magnetic sensor but contains vital alert binary sensor, making it an action
    }

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SectorAlarmConfigEntry,
        sector_api: SectorAlarmAPI,
        panel_info_coordinator: SectorPanelInfoDataUpdateCoordinator,
    ) -> None:
        super().__init__(
            hass=hass,
            sector_api=sector_api,
            config_entry=entry,
            name="SectorActionDataUpdateCoordinator",
            update_interval=_ACTION_UPDATE_INTERVAL,
        )
        self._panel_info_coordinator = panel_info_coordinator
        self._panel_info_coordinator.async_add_listener(self._handle_parent_update)
        self._data_endpoints: set[DataEndpointType] = set()
        self._event_logs: dict[str, Any] = {}
        self._device_proccessor = _DeviceProcessor(self._hass, self.panel_id)

    @callback
    def _handle_parent_update(self):
        # currently does nothing
        pass

    async def _async_setup(self):
        panel_info: PanelInfo = self._panel_info_coordinator.data["panel_info"]
        if panel_info is None:
            raise UpdateFailed(
                f"Failed to retrieve panel information for panel '{self.panel_id}' (no data returned from coordinator)"
            )

        mandatory_endpoint_types = (
            SectorActionDataUpdateCoordinator._MANDATORY_ENDPOINT_TYPES.copy()
        )
        optional_endpoint_types = (
            SectorActionDataUpdateCoordinator._OPTIONAL_DATA_ENDPOINT_TYPES.copy()
        )

        locks: list[Lock] = panel_info.get("Locks", {})
        plugs: list[SmartPlug] = panel_info.get("Smartplugs", {})

        if locks.__len__() == 0:
            optional_endpoint_types.discard(DataEndpointType.LOCK_STATUS)
        if plugs.__len__() == 0:
            optional_endpoint_types.discard(DataEndpointType.SMART_PLUG_STATUS)

        # Scan and build supported endpoints from non-panel-info endpoints
        api_data: dict[
            DataEndpointType, APIResponse
        ] = await self.sector_api.retrieve_all_data(optional_endpoint_types)
        for endpoint_type, response in api_data.items():
            if response.response_code == 404:
                optional_endpoint_types.discard(endpoint_type)

        supported_endpoint_types = mandatory_endpoint_types | optional_endpoint_types
        _LOGGER.debug("Supported ACTION endpoint types: %s", supported_endpoint_types)
        self._data_endpoints = supported_endpoint_types
        self.data = {"devices": {}, "logs": {}}

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data: dict[str, Any] = {}
            if self.data:
                data = self.data.copy().get("devices", {})

            panel_info: PanelInfo = self._panel_info_coordinator.data["panel_info"]
            if panel_info is None:
                raise UpdateFailed(
                    f"Failed to retrieve panel information for panel '{self.panel_id}' (no data returned from coordinator)"
                )

            api_data: dict[
                DataEndpointType, APIResponse
            ] = await self.sector_api.retrieve_all_data(self._data_endpoints)
            _LOGGER.debug("API ALL DATA: %s", str(api_data))

            # Process devices
            devices = self._device_proccessor.process_devices(
                panel_info, api_data, data
            )

            # Process logs for event handling
            self._event_logs = await self._device_proccessor.process_event_logs(
                api_data, devices
            )

            self._reset_update_error_counter()
            return {
                "devices": devices,
                "logs": self._event_logs,
            }

        except LoginError as error:
            self._increment_update_error_counter()
            raise ConfigEntryAuthFailed from error
        except AuthenticationError as error:
            self._increment_update_error_counter()
            raise UpdateFailed(str(error)) from error
        except ApiError as error:
            self._increment_update_error_counter()
            raise UpdateFailed(str(error)) from error

    def get_device_info(self, serial):
        """Fetch device information by serial number."""
        return self.data["devices"].get(
            serial, {"name": "Unknown Device", "model": "Unknown Model"}
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

    def get_processed_events(self) -> dict:
        """Return processed event logs grouped by device."""
        return self._event_logs


class SectorSensorDataUpdateCoordinator(SectorBaseDataUpdateCoordinator):
    _OPTIONAL_DATA_ENDPOINT_TYPES = {
        # via HouseCheck API
        # DataEndpointType.TEMPERATURES, <--- not used by Sector App
        DataEndpointType.HUMIDITY,
        # DataEndpointType.LEAKAGE_DETECTORS, <--- not used by Sector App
        # DataEndpointType.SMOKE_DETECTORS, <--- not used by Sector App
        # DataEndpointType.CAMERAS, <--- not yet supported
        # via legacy
        DataEndpointType.TEMPERATURES_LEGACY,
    }

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SectorAlarmConfigEntry,
        sector_api: SectorAlarmAPI,
        panel_info_coordinator: SectorPanelInfoDataUpdateCoordinator,
    ) -> None:
        super().__init__(
            hass=hass,
            sector_api=sector_api,
            config_entry=entry,
            name="SectorSensorDataUpdateCoordinator",
            update_interval=_SENSOR_UPDATE_INTERVAL,
        )
        self._panel_info_coordinator = panel_info_coordinator
        self._panel_info_coordinator.async_add_listener(self._handle_parent_update)
        self._data_endpoints: set[DataEndpointType] = set()
        self._device_proccessor = _DeviceProcessor(self._hass, self.panel_id)

    @callback
    def _handle_parent_update(self):
        # Currently does nothing
        pass

    async def _async_setup(self):
        try:
            panel_info: PanelInfo = self._panel_info_coordinator.data["panel_info"]
            if panel_info is None:
                raise UpdateFailed(
                    f"Failed to retrieve panel information for panel '{self.panel_id}' (no data returned from coordinator)"
                )

            optional_endpoint_types = (
                SectorSensorDataUpdateCoordinator._OPTIONAL_DATA_ENDPOINT_TYPES.copy()
            )

            temperatures: list[Temperature] = panel_info.get("Temperatures", {})
            if temperatures.__len__() == 0:
                optional_endpoint_types.discard(DataEndpointType.TEMPERATURES_LEGACY)

            # Scan and build supported endpoints from non-panel-info endpoints
            api_data: dict[
                DataEndpointType, APIResponse
            ] = await self.sector_api.retrieve_all_data(optional_endpoint_types)
            for endpoint_type, response in api_data.items():
                if response.response_code == 404:
                    optional_endpoint_types.discard(endpoint_type)

            _LOGGER.debug("Supported endpoint types: %s", optional_endpoint_types)
            self._data_endpoints = optional_endpoint_types
            self.data = {"devices": {}, "logs": {}}

        except LoginError as error:
            raise ConfigEntryAuthFailed from error
        except AuthenticationError as error:
            raise UpdateFailed(str(error)) from error
        except ApiError as error:
            raise UpdateFailed(str(error)) from error

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Sector Alarm API."""
        try:
            data: dict[str, Any] = {}
            if self.data:
                data = self.data.copy().get("devices", {})

            panel_info: PanelInfo = self._panel_info_coordinator.data["panel_info"]
            if panel_info is None:
                raise UpdateFailed(
                    f"Failed to retrieve panel information for panel '{self.panel_id}' (no data returned from coordinator)"
                )

            api_data = await self.sector_api.retrieve_all_data(self._data_endpoints)
            _LOGGER.debug("API ALL DATA: %s", str(api_data))

            # Process devices
            devices = self._device_proccessor.process_devices(
                panel_info, api_data, data
            )

            self._reset_update_error_counter()
            return {"devices": devices}

        except LoginError as error:
            self._increment_update_error_counter()
            raise ConfigEntryAuthFailed from error
        except AuthenticationError as error:
            self._increment_update_error_counter()
            raise UpdateFailed(str(error)) from error
        except ApiError as error:
            self._increment_update_error_counter()
            raise UpdateFailed(str(error)) from error

class _DeviceProcessor:
    def __init__(self, hass: HomeAssistant, panel_id: str) -> None:
        self._hass = hass
        self._panel_id = panel_id

    def _count_failed_entity(
        self, endpoint_type: DataEndpointType, devices: dict[str, Any]
    ):
        """Increment the failed_update_count counter for devices of a specific type."""
        for unused, device in devices.items():
            if device.get("model") == endpoint_type.value:
                fail_count: int = device.get("failed_update_count", 0)
                device["failed_update_count"] = fail_count + 1

    def process_devices(
        self,
        panel_info: PanelInfo,
        api_data: dict[DataEndpointType, APIResponse],
        devices: dict[str, Any],
    ) -> dict[str, Any]:
        """Process device data from the API, including humidity, closed, and alarm sensors."""
        proccess_time = datetime.now(tz=dt_util.UTC)
        for endpoint_type, endpoint_data in api_data.items():
            # Skip logs processing here
            if endpoint_type in [DataEndpointType.LOGS]:
                continue

            _LOGGER.debug("Processing category: %s", endpoint_type)

            if not endpoint_data.is_ok():
                _LOGGER.warning(
                    f"Unable to process data for category '{endpoint_type}' due to API error: data={str(endpoint_data)}"
                )
                self._count_failed_entity(endpoint_type, devices)
                continue

            if not endpoint_data.is_json():
                _LOGGER.warning(
                    f"Unable to process data for category '{endpoint_type}' due to unexpected response type: data={str(endpoint_data)}"
                )
                self._count_failed_entity(endpoint_type, devices)
                continue

            response_data = endpoint_data.response_data
            if endpoint_type == DataEndpointType.PANEL_STATUS:
                self.process_alarm_panel(
                    endpoint_type, panel_info, response_data, proccess_time, devices
                )
            elif endpoint_type == DataEndpointType.SMART_PLUG_STATUS:
                self.process_smart_plugs(
                    endpoint_type, response_data, proccess_time, devices
                )
            elif endpoint_type == DataEndpointType.LOCK_STATUS:
                self.process_locks(endpoint_type, response_data, proccess_time, devices)
            elif endpoint_type == DataEndpointType.TEMPERATURES_LEGACY:
                self.process_legacy_temperatures(
                    endpoint_type, response_data, proccess_time, devices
                )
            else:
                self.process_housecheck_devices(
                    endpoint_type, response_data, proccess_time, devices
                )

        return devices

    def process_legacy_temperatures(
        self,
        endpoint_type: DataEndpointType,
        temps_data: list[Temperature],
        proccess_time: datetime,
        devices: dict,
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
                "model": f"{endpoint_type.value}",
                "last_updated": proccess_time.isoformat(),
            }
            _LOGGER.debug(
                "Processed temperature sensor with serial_no %s: %s",
                serial_no,
                devices[serial_no],
            )

    def process_smart_plugs(
        self,
        endpoint_type: DataEndpointType,
        smart_plug_data: list[SmartPlug],
        proccess_time: datetime,
        devices: dict,
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
                "model": f"{endpoint_type.value}",
                "last_updated": proccess_time.isoformat(),
            }
            _LOGGER.debug(
                "Processed smart plug with Serial %s: %s", serial_no, devices[serial_no]
            )

    def process_alarm_panel(
        self,
        endpoint_type: DataEndpointType,
        panel_info: PanelInfo,
        panel_status_data: PanelStatus,
        proccess_time: datetime,
        devices: dict,
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
            "panel_code_length": panel_info.get("PanelCodeLength", 0),
            "panel_quick_arm": panel_info.get("QuickArmEnabled", False),
            "panel_partial_arm": panel_info.get("CanPartialArm", False),
            "model": f"{endpoint_type.value}",
            "last_updated": proccess_time.isoformat(),
        }
        _LOGGER.debug(
            "Processed alarm panel with Serial %s: %s",
            serial_no,
            devices["alarm_panel"],
        )

    def process_locks(
        self,
        endpoint_type: DataEndpointType,
        locks_data: list[Lock],
        proccess_time: datetime,
        devices: dict,
    ) -> None:
        """Process lock data and add to devices dictionary."""
        for lock in locks_data:
            serial_no = lock.get("SerialNo") or lock.get("Serial")
            if not serial_no:
                _LOGGER.warning("Lock is missing Serial: %s", lock)
                continue

            name = lock.get("Label")
            lock_status = lock.get("Status")

            devices[serial_no] = {
                "name": name,
                "serial_no": serial_no,
                "sensors": {
                    "lock_status": lock_status,
                },
                "model": f"{endpoint_type.value}",
                "last_updated": proccess_time.isoformat(),
            }

            _LOGGER.debug(
                "Processed lock with serial_no %s: %s", serial_no, devices[serial_no]
            )

    def process_housecheck_devices(
        self,
        endpoint_type: DataEndpointType,
        category_data: HouseCheck,
        proccess_time: datetime,
        devices: dict,
    ) -> None:
        """Process devices within a specific category and add them to devices dictionary."""
        # Floors is currently only used by Humidity sensors
        if "Sections" in category_data:
            for section in category_data.get("Sections", []):
                for place in section.get("Places", []):
                    for component in place.get("Components", []):
                        self._process_housecheck_device(
                            endpoint_type,
                            component,  # type: ignore
                            proccess_time,
                            devices,
                        )
        elif "Floors" in category_data:
            for floor in category_data.get("Floors", []):
                for room in floor.get("Rooms", []):
                    for device in room.get("Devices", []):
                        self._process_housecheck_device(
                            endpoint_type,
                            device,  # type: ignore
                            proccess_time,
                            devices,
                        )
        else:
            _LOGGER.debug("Category %s does not contain Sections", endpoint_type)

    def _process_housecheck_device(
        self,
        endpoint_type: DataEndpointType,
        device_data: dict[Any, Any],
        proccess_time: datetime,
        devices: dict,
    ):
        serial_no = device_data.get("SerialNo") or device_data.get("Serial")

        if serial_no is None:
            _LOGGER.warning("Device data missing SerialNo/Serial: %s", device_data)
            return

        sensors = {}
        closed = device_data.get("Closed")
        if closed is not None:
            sensors["closed"] = closed

        low_battery = device_data.get("LowBattery")
        if low_battery is not None:
            sensors["low_battery"] = low_battery

        battery_low = device_data.get("BatteryLow")
        if battery_low is not None:
            sensors["low_battery"] = battery_low

        alarm = device_data.get("Alarm")
        if alarm is not None:
            sensors["alarm"] = alarm

        temperature = device_data.get("Temperature")
        if temperature is not None:
            sensors["temperature"] = temperature

        humidity = device_data.get("Humidity")
        if humidity is not None:
            sensors["humidity"] = humidity

        if sensors.__len__() == 0:
            _LOGGER.debug(
                "No sensors were found in device data for category '%s'",
                endpoint_type,
            )
            return

        # Initialize or update device entry with sensors
        device_info = devices.setdefault(
            serial_no,
            {
                "name": device_data.get("Label") or device_data.get("Name"),
                "serial_no": serial_no,
                "sensors": sensors,
                "type": device_data.get("Type", ""),
                "model": f"{endpoint_type.value}",
                "last_updated": proccess_time.isoformat(),
            },
        )

        _LOGGER.debug(
            "Processed device: category: %s, device: %s",
            endpoint_type,
            device_info,
        )

    async def process_event_logs(
        self,
        api_data: dict[DataEndpointType, APIResponse],
        devices: dict[str, Any],
    ) -> dict[str, Any]:
        """Process event logs, associating them with the correct lock devices using LockName."""

        endpoint_type = DataEndpointType.LOGS
        if endpoint_type not in api_data:
            return {}

        api_response = api_data[endpoint_type]
        if not api_response.is_ok():
            _LOGGER.warning(
                f"Unable to process data for category '{endpoint_type}' due to API error: data={str(api_response)}"
            )
            return {}

        if not api_response.is_json():
            _LOGGER.warning(
                f"Unable to process data for category '{endpoint_type}' due to unexpected response type: data={str(api_response)}"
            )
            return {}

        grouped_events = {}
        logs: LogRecords = api_response.response_data

        # Get the user's configured timezone from Home Assistant
        user_time_zone = self._hass.config.time_zone or "UTC"
        try:
            tz: ZoneInfo = ZoneInfo(self._hass.config.time_zone)
        except Exception:
            _LOGGER.debug("Invalid timezone '%s', defaulting to UTC.", user_time_zone)
            tz: ZoneInfo = ZoneInfo("UTC")

        records = list(reversed(logs.get("Records", [])))
        _LOGGER.debug("Processing %d log records", len(records))

        lock_names = {
            device["name"]: serial_no
            for serial_no, device in devices.items()
            if device.get("model") == DataEndpointType.LOCK_STATUS.value
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
            latest_log = self._get_latest_log(event_type, lock_name)
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
                    "model": endpoint_type,
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

    def _get_latest_log(self, event_type: str, lock_name: str):
        """Retrieve the latest log for a specific event type, optionally by LockName."""
        if not lock_name:
            _LOGGER.debug("Lock name not provided. Unable to fetch latest log.")
            return None

        # Normalize lock_name for consistent naming
        normalized_name = slugify(lock_name)
        entity_id = f"event.{normalized_name}_{normalized_name}_event_log"  # Adjusted format for entity IDs

        # Log the generated entity ID
        _LOGGER.debug("Generated entity ID for lock '%s': %s", lock_name, entity_id)

        state = self._hass.states.get(entity_id)

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
