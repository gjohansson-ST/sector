"""Event platform for Sector Alarm integration."""

import logging
from datetime import datetime, timezone
from typing import Any
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
    grouped_events = await coordinator.process_events()

    entities = []

    # Loop through each device and its event categories, create entities based on categories only
    for device_serial, event_categories in grouped_events.items():
        device_info = coordinator.get_device_info(device_serial)
        device_name = device_info["name"]
        device_model = device_info["model"]

        # Debug statement to check device and logs being processed
        _LOGGER.debug("Processing device '%s' (serial %s) with model '%s' for events", device_name, device_serial, device_model)

        for category in event_categories:
            # Get the entity class for the category; if none, skip
            entity_class = EVENT_ENTITY_CLASSES.get(category)
            if not entity_class:
                _LOGGER.warning("No entity class defined for category: %s", category)
                continue

            # Debug to verify logs are found for each category
            _LOGGER.debug("Creating event entity for category '%s' with logs", category)

            # Create an entity without triggering events
            entity = entity_class(coordinator, device_serial, device_name, device_model, category, lock_name=device_name)
            entities.append(entity)

    _LOGGER.debug("Total event entities added: %d", len(entities))
    async_add_entities(entities)

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
        self._attr_unique_id = f"{device_serial}_event"
        self._attr_name = f"{device_name} Event Log"
        self._attr_device_class = "sector_alarm_timestamp"  # Use a custom string identifier
        self._last_event_timestamp = None  # Or set a default timestamp if preferred
        _LOGGER.debug("Created SectorAlarmEvent for device: %s", device_name)

    def _trigger_event(self, event_type: str, event_attributes: dict[str, Any] | None = None):
        """Process a new event with timestamp and additional attributes."""
        event_attributes = event_attributes or {}
        current_time = datetime.now(timezone.utc).isoformat()
        event_attributes['timestamp'] = current_time  # Add timestamp for consistency

        # Fire the event
        super()._trigger_event(event_type, event_attributes)

        # Store the event timestamp in the state for Home Assistant to track
        self._last_event_timestamp = current_time
        self.async_write_ha_state()

    @property
    def state(self) -> str:
        """Return the latest event type."""
        return self._event_type or "No events"

    @staticmethod
    def _format_timestamp(time_str: str) -> str:
        """Format a timestamp string to UTC timezone if possible."""
        if not time_str:
            return "unknown"
        try:
            timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00")).astimezone(timezone.utc)
            return timestamp.isoformat()
        except ValueError:
            _LOGGER.warning("Invalid timestamp format: %s", time_str)
            return "unknown"

    async def async_added_to_hass(self):
        """Set up continuous event processing once added to Home Assistant."""
        await super().async_added_to_hass()

        # Set up listener to call async_update whenever the coordinator updates
        self.async_on_remove(
            self.coordinator.async_add_listener(lambda: self.hass.async_create_task(self.async_update()))
        )

        _LOGGER.debug("Continuous event processing set up for %s", self._attr_name)

    async def async_update(self):
        """Handle only new logs from coordinator and trigger events for them."""
        grouped_events = await self.coordinator.process_events()

        # Process only new logs for this entity
        if self._serial_no in grouped_events:
            for category, logs in grouped_events[self._serial_no].items():
                if category == self._event_type:
                    for log in logs:
                        event_type = log.get("EventType")
                        timestamp = self._format_timestamp(log.get("Time"))

                        # Trigger event and update state
                        self._trigger_event(event_type, {"timestamp": timestamp})
                        _LOGGER.debug("Triggered event for device %s: %s", self._serial_no, log)

    @property
    def device_info(self):
        """Return device information to associate this entity with a device."""
        return {
            "identifiers": {(DOMAIN, self._serial_no)},
            "name": self._device_name,
            "manufacturer": "Sector Alarm",
            "model": self._device_model,
        }

    def _process_event(self, log: dict):
        """Update the entity with a new event and refresh HA state."""
        self._events.append(log)
        self.async_write_ha_state()
        _LOGGER.debug("Processed event: %s", log)

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
