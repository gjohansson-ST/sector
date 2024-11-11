"""Event platform for Sector Alarm integration."""

import logging
from datetime import datetime, timezone
from typing import Any
from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up a single event entity per device in Sector Alarm coordinator."""
    coordinator: SectorDataUpdateCoordinator = entry.runtime_data
    grouped_events = await coordinator.process_events()
    entities = []

    for device_serial, event_categories in grouped_events.items():
        device_info = coordinator.get_device_info(device_serial)
        device_name = device_info["name"]
        device_model = device_info["model"]

        _LOGGER.debug("SECTOR_EVENT: Creating event entity for device: %s, Model: %s", device_name, device_model)

        # Define unique entity ID for each device, regardless of event type
        entity_unique_id = f"{device_serial}_event"

        # Check if the entity already exists by unique ID
        if hass.states.get(f"event.{entity_unique_id}"):
            _LOGGER.debug("SECTOR_EVENT: Entity with unique ID '%s' already exists, skipping.", entity_unique_id)
            continue

        # Create a single entity to handle multiple event types for the device
        entity = SectorAlarmEvent(coordinator, device_serial, device_name, device_model)
        entities.append(entity)
        _LOGGER.debug("SECTOR_EVENT: Created event entity: %s", entity)  # Log each created entity

    _LOGGER.debug("SECTOR_EVENT: Total event entities added: %d", len(entities))
    async_add_entities(entities)

class SectorAlarmEvent(CoordinatorEntity, EventEntity):
    """Representation of a single event entity for a Sector Alarm device."""

    def __init__(self, coordinator, device_serial, device_name, device_model):
        """Initialize the single event entity for the device."""
        super().__init__(coordinator)
        self._serial_no = device_serial
        self._device_name = device_name
        self._device_model = device_model
        self._events = []  # Store all events
        self._attr_unique_id = f"{device_serial}_event"
        self._attr_name = f"{device_name} Event Log"
        self._attr_device_class = "timestamp"
        self._last_event_type = None
        _LOGGER.debug("SECTOR_EVENT: Initialized SectorAlarmEvent for device: %s (%s)", device_name, device_serial)

    @property
    def event_types(self):
        """Return the list of event types this entity can handle."""
        return ["lock", "unlock", "lock_failed"]

    async def async_update(self):
        """Update entity based on the most recent event."""
        grouped_events = await self.coordinator.process_events()
        _LOGGER.debug("SECTOR_EVENT: Processing events for device %s", self._serial_no)

        if self._serial_no not in grouped_events:
            _LOGGER.debug("SECTOR_EVENT: No events found for device %s", self._serial_no)
            return

        for event_type, logs in grouped_events[self._serial_no].items():
            latest_log = logs[-1]  # Get the latest log
            event_time = latest_log["Time"]

            # Set state as the latest event type to trigger the state update
            self._last_event_type = event_type
            self._events.append(latest_log)  # Store the event for attributes

            # Explicitly trigger an event update and set the state
            self._trigger_event(self._last_event_type, {"timestamp": event_time})
            self.async_write_ha_state()  # Explicitly write state to force update in Home Assistant

            _LOGGER.debug(
                "SECTOR_EVENT: Updated entity %s with event type %s at %s",
                self._attr_unique_id,
                self._last_event_type,
                event_time
            )

    def _trigger_event(self, event_type, event_attributes):
        """Trigger an event update with the latest type."""
        event_timestamp = event_attributes.get("timestamp", datetime.now(timezone.utc).isoformat())
        event_attributes["timestamp"] = event_timestamp
        _LOGGER.debug(
            "SECTOR_EVENT: Triggering event update for device %s with event type %s and timestamp %s",
            self._serial_no,
            event_type,
            event_timestamp
        )
        super()._trigger_event(event_type, event_attributes)

    @property
    def state(self) -> str:
        """Return the latest event type for the device."""
        _LOGGER.debug("SECTOR_EVENT: Returning state for device %s: %s", self._serial_no, self._last_event_type or "No events")
        return self._last_event_type or "No events"

    @property
    def extra_state_attributes(self):
        """Return additional attributes for the most recent event."""
        if not self._events:
            return {}

        recent_event = self._events[-1]
        _LOGGER.debug("SECTOR_EVENT: Returning extra state attributes for device %s: %s", self._serial_no, recent_event)
        return {
            "time": recent_event.get("Time"),
            "user": recent_event.get("User", "unknown"),
            "channel": recent_event.get("Channel", "unknown"),
        }

    @property
    def unique_id(self):
        """Return the unique ID for this entity."""
        return self._attr_unique_id

    @staticmethod
    def _format_timestamp(time_str: str) -> str:
        """Format a timestamp string to UTC timezone if possible."""
        if not time_str:
            return "unknown"
        try:
            timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00")).astimezone(timezone.utc)
            _LOGGER.debug("SECTOR_EVENT: Formatted timestamp: %s", timestamp.isoformat())
            return timestamp.isoformat()
        except ValueError:
            _LOGGER.warning("SECTOR_EVENT: Invalid timestamp format: %s", time_str)
            return "unknown"

    async def async_added_to_hass(self):
        """Set up continuous event processing once added to Home Assistant."""
        await super().async_added_to_hass()

        # Set up listener to call async_update whenever the coordinator updates
        self.async_on_remove(
            self.coordinator.async_add_listener(lambda: self.hass.async_create_task(self.async_update()))
        )

        _LOGGER.debug("SECTOR_EVENT: Continuous event processing set up for %s", self._attr_name)

    @property
    def device_info(self):
        """Return device information to associate this entity with a device."""
        return {
            "identifiers": {("sector", self._serial_no)},
            "name": self._device_name,
            "manufacturer": "Sector Alarm",
            "model": self._device_model,
        }
