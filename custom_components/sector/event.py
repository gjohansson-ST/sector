"""Event platform for Sector Alarm integration."""

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from custom_components.sector.const import RUNTIME_DATA

from .coordinator import (
    SectorDeviceDataUpdateCoordinator,
    SectorAlarmConfigEntry,
)
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up a single event entity per device in Sector Alarm coordinator."""
    entities = []
    coordinators: list[SectorDeviceDataUpdateCoordinator] = entry.runtime_data[
        RUNTIME_DATA.DEVICE_COORDINATORS
    ]

    for coordinator in coordinators:
        grouped_events = coordinator.get_processed_events()
        for device_serial in grouped_events.keys():
            device_info = coordinator.get_device_info(device_serial)
            device_name = device_info["name"]
            device_model = device_info["model"]

            _LOGGER.debug(
                "SECTOR_EVENT: Creating event entity for device: %s, Model: %s",
                device_name,
                device_model,
            )

            # Define unique entity ID for each device, regardless of event type
            entity_unique_id = f"{device_serial}_event"

            # Check if the entity already exists by unique ID
            if hass.states.get(f"event.{entity_unique_id}"):
                _LOGGER.debug(
                    "SECTOR_EVENT: Entity with unique ID '%s' already exists, skipping.",
                    entity_unique_id,
                )
                continue

            # Create a single entity to handle multiple event types for the device
            entity = SectorAlarmEvent(coordinator, device_serial, device_info)
            entities.append(entity)
            _LOGGER.debug(
                "SECTOR_EVENT: Created event entity: %s (unique_id=%s, name=%s)",
                entity,
                entity.unique_id,
                entity.name,
            )

    _LOGGER.debug("SECTOR_EVENT: Total event entities added: %d", len(entities))
    async_add_entities(entities)


class SectorAlarmEvent(
    SectorAlarmBaseEntity[SectorDeviceDataUpdateCoordinator], EventEntity
):
    """Representation of a single event entity for a Sector Alarm device."""

    def __init__(self, coordinator, serial_no, device_info):
        """Initialize the single event entity for the device."""
        # Pass serial_no, device_name, and device_model to the parent class
        super().__init__(
            coordinator,
            serial_no,
            device_info["name"],
            device_info["model"],
            device_info["model"],
        )
        self._device_name = device_info["name"]
        self._device_model = device_info["model"]
        self._events = []  # Store all events
        self._attr_unique_id = f"{self._device_name}_event"
        self._attr_name = f"{self._device_name} Event Log"
        self._last_event_type = None
        self._last_formatted_event = None
        _LOGGER.debug(
            "SECTOR_EVENT: Initialized SectorAlarmEvent for device: %s (%s)",
            self._device_name,
            self._serial_no,
        )

    @property
    def event_types(self):
        """Return the list of event types this entity can handle."""
        return ["lock", "unlock", "lock_failed"]

    @callback
    def _async_handle_event(self):
        """Update entity based on the most recent event."""
        grouped_events = self.coordinator.get_processed_events()
        _LOGGER.debug("SECTOR_EVENT: Processing events for device %s", self._serial_no)

        if self._serial_no not in grouped_events:
            _LOGGER.debug(
                "SECTOR_EVENT: No events found for device %s", self._serial_no
            )
            return

        if self._serial_no in grouped_events:
            for event_type, logs in grouped_events[self._serial_no].items():
                latest_log = logs[-1]  # Get the latest log
                event_time = datetime.fromisoformat(latest_log["time"])

                if (
                    self._events
                    and datetime.fromisoformat(self._events[-1]["time"]) >= event_time
                ):
                    _LOGGER.debug(
                        "Skipping update for %s: Event is not newer than the last processed event.",
                        self._serial_no,
                    )
                    continue

                self._last_event_type = event_type
                self._events.append(latest_log)
                self._last_formatted_event = latest_log.get(
                    "formatted_event", f"{event_type.capitalize()} occurred"
                )
                event_time = event_time.replace(tzinfo=dt_util.UTC)
                self._trigger_event(
                    self._last_event_type, {"timestamp": event_time.isoformat()}
                )
                self.async_write_ha_state()

                _LOGGER.debug(
                    "SECTOR_EVENT: Entity %s updated with new event: type=%s, time=%s",
                    self._attr_unique_id,
                    self._last_event_type,
                    event_time,
                )

    def _trigger_event(self, event_type, event_attributes: dict[str, Any]):
        """Trigger an event update with the latest type."""
        event_timestamp = event_attributes.get(
            "timestamp", datetime.now(dt_util.UTC).isoformat()
        )
        event_attributes["timestamp"] = event_timestamp
        _LOGGER.debug(
            "SECTOR_EVENT: Triggering event update for device %s with event type %s and timestamp %s",
            self._serial_no,
            event_type,
            event_timestamp,
        )
        super()._trigger_event(event_type, event_attributes)

    @property
    def state(self) -> str:
        """Return the latest event type for the device."""
        _LOGGER.debug(
            "SECTOR_EVENT: Returning state for device %s: %s",
            self._serial_no,
            self._last_event_type or "No events",
        )
        return self._last_event_type or "No events"

    @property
    def extra_state_attributes(self):
        """Return additional attributes for the most recent event."""
        if not self._events:
            return {}

        recent_event = self._events[-1]
        self._last_formatted_event = recent_event.get(
            "formatted_event", "Event occurred"
        )
        _LOGGER.debug(
            "SECTOR_EVENT: Returning extra state attributes for device %s: %s",
            self._serial_no,
            recent_event,
        )
        return {
            "time": recent_event.get("Time"),
            "user": recent_event.get("User", "unknown"),
            "channel": recent_event.get("Channel", "unknown"),
            "formatted_event": self._last_formatted_event,
        }

    def logbook_message(self, event_type: str, event_attributes: dict[str, Any]) -> str:
        """Return a custom logbook message for this entity."""
        return self._last_formatted_event or f"{self._device_name} detected an event."

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
            timestamp = datetime.fromisoformat(
                time_str.replace("Z", "+00:00")
            ).astimezone(dt_util.UTC)
            _LOGGER.debug(
                "SECTOR_EVENT: Formatted timestamp: %s", timestamp.isoformat()
            )
            return timestamp.isoformat()
        except ValueError:
            _LOGGER.warning("SECTOR_EVENT: Invalid timestamp format: %s", time_str)
            return "unknown"

    async def async_added_to_hass(self):
        """Set up continuous event processing once added to Home Assistant."""
        await super().async_added_to_hass()

        # Set up listener to call _async_handle_event whenever the coordinator updates
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_handle_event)
        )

        _LOGGER.debug(
            "SECTOR_EVENT: Continuous event processing set up for %s", self._attr_name
        )

    @property
    def device_info(self):
        """Return device information to associate this entity with a device."""
        return {
            "identifiers": {("sector", self._serial_no)},
            "name": self._device_name,
            "manufacturer": "Sector Alarm",
            "model": self._device_model,
        }

    @callback
    def async_describe_events(hass, async_describe_event):
        """Describe Sector Alarm events for the Logbook."""
        async_describe_event(
            "sector_alarm",
            "sector_alarm_event",
            lambda event: {
                "name": event.data.get("entity_id", "Unknown"),
                "message": event.data.get("formatted_event", "Unknown event occurred"),
            },
        )
