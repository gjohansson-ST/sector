"""Event platform for Sector Alarm integration."""

import logging
from datetime import datetime, timezone
from collections import defaultdict
from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up event entities based on processed data in Sector Alarm coordinator."""
    coordinator: SectorDataUpdateCoordinator = entry.runtime_data
    grouped_events = coordinator.process_events()

    entities = []

    for device_serial, events in grouped_events.items():
        device_info = coordinator.get_device_info(device_serial)
        device_name = device_info["name"]
        device_model = device_info["model"]

        if events["lock"]:
            lock_entity = LockEventEntity(coordinator, device_serial, device_name, device_model)
            lock_entity.queue_events(events["lock"])
            entities.append(lock_entity)

    async_add_entities(entities)
    _LOGGER.debug("Added %d event entities", len(entities))

class SectorAlarmEvent(CoordinatorEntity, EventEntity):
    """Representation of a general event entity for Sector Alarm integration."""

    def __init__(self, coordinator, device_serial, device_name, device_model):
        """Initialize the general event entity."""
        super().__init__(coordinator)
        self._serial_no = device_serial
        self._device_name = device_name
        self._device_model = device_model
        self._events = []  # Store all general events
        self._event_queue = []  # Queue to store events before entity is added to Home Assistant
        self._attr_unique_id = f"{device_serial}_event"
        self._attr_name = f"{device_name} Event Log"
        self._attr_device_class = "sector_alarm_timestamp"  # Use a custom string identifier
        _LOGGER.debug("Created SectorAlarmEvent for device: %s", device_name)

    @property
    def device_info(self):
        """Return device information to associate this entity with a device."""
        return {
            "identifiers": {(DOMAIN, self._serial_no)},
            "name": self._device_name,
            "manufacturer": "Sector Alarm",
            "model": self._device_model,
        }

    async def async_added_to_hass(self):
        """Handle entity addition to Home Assistant and process queued events."""
        await super().async_added_to_hass()
        for event in self._event_queue:
            self.add_event(event)
        self._event_queue.clear()  # Clear the queue after processing

    def queue_events(self, logs):
        """Queue multiple events at once."""
        for log in logs:
            self.queue_event(log)

    @property
    def state(self):
        """Return the latest event type as the entity state."""
        return self._events[-1]["EventType"] if self._events else "No events"

    @property
    def extra_state_attributes(self):
        """Return additional attributes for the most recent event."""
        if not self._events:
            return {}

        recent_event = self._events[-1]
        timestamp_str = self._format_timestamp(recent_event.get("Time"))

        return {
            "time": timestamp_str,
            "user": recent_event.get("User", "unknown"),
            "channel": recent_event.get("Channel", "unknown"),
        }

    def queue_event(self, log):
        """Queue an event if the entity is not yet added to Home Assistant."""
        if self.hass:
            self.add_event(log)
        else:
            self._event_queue.append(log)

    def add_event(self, log):
        """Add a general event to the entity."""
        self._events.append(log)
        if self.hass:  # Ensure entity is fully initialized before calling write_ha_state
            _LOGGER.debug("Adding event to %s: %s", self._attr_name, log)
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Tried to add event to uninitialized entity: %s", self._attr_name)

    @staticmethod
    def _format_timestamp(time_str):
        """Helper to format the timestamp for state attributes."""
        if not time_str:
            return "unknown"
        try:
            timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00")).astimezone(timezone.utc)
            return timestamp.isoformat()
        except ValueError:
            _LOGGER.warning("Invalid timestamp format: %s", time_str)
            return "unknown"


class LockEventEntity(SectorAlarmEvent):
    """Representation of a lock-specific event entity for Sector Alarm integration."""

    _attr_event_types = ["lock", "unlock", "lock_failed"]

    def __init__(self, coordinator, device_serial, device_name, device_model):
        """Initialize the lock-specific event entity."""
        super().__init__(coordinator, device_serial, device_name, device_model)
        _LOGGER.debug("Created LockEventEntity for device: %s", device_name)

    def queue_event(self, log):
        """Queue a lock event if the event type is lock-related."""
        if log.get("EventType") in self._attr_event_types:
            super().queue_event(log)
