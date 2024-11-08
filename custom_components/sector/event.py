"""Event platform for Sector Alarm integration."""

import logging
import asyncio

from collections import defaultdict
from homeassistant.components.event import EventEntity, EventEntityDescription, EventDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from datetime import datetime, timezone

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sector Alarm events for each device based on log entries."""
    coordinator: SectorDataUpdateCoordinator = entry.runtime_data

    # Define setup_events to be triggered once the lock setup is complete
    async def setup_events(event=None):
        _LOGGER.debug("Sector Entry: sector_alarm_lock_setup_complete event received, starting event setup")
        logs = coordinator.data.get("logs", [])
        _LOGGER.debug("Sector Entry: Processing log entries: %d logs found", len(logs))

        # Map device labels (LockName) to device serial numbers
        device_map = {device_info["name"]: serial for serial, device_info in coordinator.data["devices"].items()}
        _LOGGER.debug("Sector Entry: Device map created: %s", device_map)

        # Group logs by device serial number, using the map
        logs_by_device = defaultdict(list)
        for log in logs:
            lock_name = log.get("LockName")
            _LOGGER.debug("Sector Entry: Processing log entry: %s", log)

            # Skip entries with empty or missing LockName
            if not lock_name:
                _LOGGER.debug("Sector Entry: Skipping log entry with missing LockName: %s", log)
                continue

            device_serial = device_map.get(lock_name)
            if device_serial:
                logs_by_device[device_serial].append(log)
                _LOGGER.debug("Sector Entry: Log entry associated with device %s (serial: %s)", lock_name, device_serial)
            else:
                _LOGGER.warning("Sector Entry: Log entry for unrecognized device: %s", lock_name)

        # Create an event entity for each device with logs
        entities = []
        for device_serial, device_logs in logs_by_device.items():
            device_info = coordinator.data["devices"].get(device_serial, {})
            device_name = device_info.get("name", "Unknown Device")

            _LOGGER.debug("Sector Entry: Creating event entity for device %s with logs: %d entries", device_name, len(device_logs))

            # Initialize event entity for this device and add its logs
            event_entity = SectorAlarmEvent(coordinator, device_serial, device_name, device_info.get("model", "Unknown Model"))
            entities.append(event_entity)
            for log in device_logs:
                event_entity.add_event(log)

        _LOGGER.debug("Sector Entry: Adding %d event entities to Home Assistant", len(entities))
        async_add_entities(entities)

    # Attempt listener for custom event
    _LOGGER.debug("Sector Entry: Registering listener for sector_alarm_lock_setup_complete")
    hass.bus.async_listen_once("sector_alarm_lock_setup_complete", lambda _: hass.async_create_task(setup_events()))

    # Fallback in case the custom event never fires
    _LOGGER.debug("Sector Entry: Scheduling fallback setup after 5 seconds")
    async_call_later(hass, 5, lambda _: hass.create_task(setup_events()))

class SectorAlarmEvent(SectorAlarmBaseEntity, EventEntity):
    """Representation of a Sector Alarm log event."""

    def __init__(self, coordinator: SectorDataUpdateCoordinator, device_serial: str, device_name: str, device_model: str):
        """Initialize the log event entity for a specific device."""
        super().__init__(coordinator, device_serial, {"name": device_name}, device_model)

        self._attr_unique_id = f"{device_serial}_event"
        self._attr_name = f"{device_name} Event Log"
        self._attr_device_class = "timestamp"
        self._events = []  # List to store recent log events for this device
        self._initialized = False
        _LOGGER.debug("Sector Entry: Created SectorAlarmEvent for device: %s with serial: %s", device_name, device_serial)

    async def async_added_to_hass(self):
        """Handle entity addition to Home Assistant."""
        self._initialized = True  # Entity is now added to Home Assistant
        _LOGGER.debug("Sector Entry: SectorAlarmEvent entity added to Home Assistant for: %s", self._attr_name)

    @property
    def state(self) -> str:
        """Return the most recent event type as the state."""
        return self._events[-1]["EventType"] if self._events else "No events"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes for the most recent log event."""
        if not self._events:
            return {}

        recent_event = self._events[-1]

        # Parse the ISO 8601 timestamp to a datetime object
        time_str = recent_event.get("Time", "unknown")
        try:
            # Replace "Z" with "+00:00" for compatibility with fromisoformat
            if time_str.endswith("Z"):
                time_str = time_str.replace("Z", "+00:00") # Parse the string and localize it to UTC

            timestamp = datetime.fromisoformat(time_str).astimezone(timezone.utc)
            timestamp_str = timestamp.isoformat()  # Convert back to ISO 8601 format
        except ValueError:
            _LOGGER.warning("Invalid timestamp format: %s", time_str)
            timestamp_str = "unknown"

        return {
            "time": timestamp_str,
            "channel": recent_event.get("Channel", "unknown"),
            "user": recent_event.get("User", "unknown"),
        }

    @property
    def event_types(self) -> list[str]:
        """Return all unique event types for this entity's logs."""
        return list({event["EventType"] for event in self._events})

    def add_event(self, log: dict):
        """Add a new log event to this entity."""
        self._events.append(log)
        if self._initialized:
            _LOGGER.debug("Sector Entry: Adding event to %s: %s", self._attr_name, log)
            self.async_write_ha_state()  # Only update if entity is initialized
        else:
            _LOGGER.debug("Sector Entry: Event added to uninitialized entity %s: %s", self._attr_name, log)
