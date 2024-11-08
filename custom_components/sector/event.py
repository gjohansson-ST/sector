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

    # Loop through each device and its event categories
    for device_serial, event_categories in grouped_events.items():
        device_info = coordinator.get_device_info(device_serial)
        device_name = device_info["name"]
        device_model = device_info["model"]

        for category, logs in event_categories.items():
            # Get the entity class for the category; if none, skip
            entity_class = EVENT_ENTITY_CLASSES.get(category)
            if not entity_class:
                _LOGGER.warning("No entity class defined for category: %s", category)
                continue

            # Create an entity for this category and add the logs
            entity = entity_class(coordinator, device_serial, device_name, device_model, category, lock_name=device_name)
            for log in logs:
                entity._trigger_event(log.get("EventType"), entity._format_timestamp(log.get("Time")), log)
            entities.append(entity)

    async_add_entities(entities)
    _LOGGER.debug("Added %d event entities", len(entities))

class SectorAlarmEvent(CoordinatorEntity, EventEntity):
    """Representation of a general event entity for Sector Alarm integration."""

    def __init__(self, coordinator, device_serial, device_name, device_model, event_type, lock_name):
        """Initialize the general event entity."""
        super().__init__(coordinator)
        self._serial_no = device_serial
        self._device_name = device_name
        self._device_model = device_model
        self._event_type = event_type  # Initialize event_type
        self._lock_name = lock_name  # Initialize lock_name
        self._events = []  # Store all general events
        self._queued_events = []  # Queue for events before hass is set up
        self._attr_unique_id = f"{device_serial}_event"
        self._attr_name = f"{device_name} Event Log"
        self._attr_device_class = "sector_alarm_timestamp"  # Use a custom string identifier
        _LOGGER.debug("Created SectorAlarmEvent for device: %s", device_name)

    async def async_update(self):
        """Periodically check for the latest log and update state if a new one is found."""
        latest_log = self.coordinator.get_latest_log(self._event_type, self._lock_name)
        if latest_log:
            latest_log_id = latest_log.get("Time")
            if latest_log_id != getattr(self, "_last_log_id", None):
                self._last_log_id = latest_log_id
                self._events = [latest_log]
                self.async_write_ha_state()
            else:
                _LOGGER.debug("No new log to process for %s", self._attr_name)


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
        """Process queued events once the entity is added to Home Assistant."""
        await super().async_added_to_hass()
        for event in self._queued_events:
            self._process_event(event)
        self._queued_events.clear()  # Clear the queue after processing

    def _trigger_event(self, event_type: str, timestamp: str, attributes: dict = None):
        """Process a new event by setting state and attributes."""
        log = {"EventType": event_type, "Time": timestamp}
        if attributes:
            log.update(attributes)

        # Queue the event if Home Assistant isn't fully ready
        if not self.hass:
            self._queued_events.append(log)
            _LOGGER.debug("Queued event: %s for processing later", log)
            return

        # Process the event immediately if hass is ready
        self._process_event(log)

    def _process_event(self, log: dict):
        """Update the entity with a new event and refresh HA state."""
        self._events.append(log)
        self.async_write_ha_state()
        _LOGGER.debug("Processed event: %s", log)

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
        formatted_time = self._format_timestamp(recent_event.get("Time"))

        return {
            "time": recent_event.get("Time"),
            "user": recent_event.get("User", "unknown"),
            "channel": recent_event.get("Channel", "unknown"),
        }

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

    def __init__(self, coordinator, device_serial, device_name, device_model, event_type, lock_name):
        """Initialize the lock-specific event entity."""
        super().__init__(coordinator, device_serial, device_name, device_model, event_type, lock_name)
        _LOGGER.debug("Created LockEventEntity for device: %s", device_name)

EVENT_ENTITY_CLASSES = {
    "lock": LockEventEntity,
}
