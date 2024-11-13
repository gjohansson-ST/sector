"""Event platform for Sector Alarm integration."""

import logging
from datetime import datetime, timezone

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm event entities."""
    coordinator: SectorDataUpdateCoordinator = entry.runtime_data
    devices = coordinator.data.get("devices", {})
    logs = coordinator.data.get("logs", {})
    entities = []

    # Create event entities for each supported device with event logs
    for serial_no, device_info in devices.items():
        if device_info.get("model") == "Smart Lock":  # Filter for Smart Locks
            # Check if there are logs for this Smart Lock to create event entities
            if serial_no in logs:
                entities.append(SectorAlarmEvent(coordinator, serial_no, device_info))
                _LOGGER.debug(
                    "SECTOR_EVENT: Created event entity for Smart Lock with serial: %s",
                    serial_no,
                )

    _LOGGER.debug("SECTOR_EVENT: Total event entities added: %d", len(entities))
    async_add_entities(entities)


class SectorAlarmEvent(SectorAlarmBaseEntity, EventEntity):
    """Representation of a single event entity for a Sector Alarm device."""

    def __init__(self, coordinator, serial_no, device_info):
        """Initialize the single event entity for the device."""
        super().__init__(coordinator, serial_no, device_info)
        self._events = []
        self._last_event_type = None
        self._attr_name = f"{device_info['name']} Event Log"
        self._attr_unique_id = f"{serial_no}_event"
        self._attr_device_class = "timestamp"
        _LOGGER.debug(
            "SECTOR_EVENT: Initialized SectorAlarmEvent for device: %s (%s)",
            device_info["name"],
            serial_no,
        )

    @property
    def event_types(self):
        """Return the list of event types this entity can handle."""
        return ["lock", "unlock", "lock_failed"]

    async def async_update(self):
        """Update entity based on the most recent event."""
        grouped_events = await self.coordinator.process_events()
        events_for_device = grouped_events.get(self._serial_no)

        if not events_for_device:
            _LOGGER.debug(
                "SECTOR_EVENT: No events found for device %s", self._serial_no
            )
            return

        for event_type, logs in events_for_device.items():
            latest_log = logs[-1]
            self._last_event_type = event_type
            self._events.append(latest_log)
            self._trigger_event(self._last_event_type, latest_log)
            self.async_write_ha_state()

    def _trigger_event(self, event_type, event_attributes):
        """Trigger an event with timestamp and details."""
        event_timestamp = event_attributes.get(
            "Time", datetime.now(timezone.utc).isoformat()
        )
        event_attributes["timestamp"] = event_timestamp
        _LOGGER.debug(
            "SECTOR_EVENT: Triggering event for device %s with event type %s and timestamp %s",
            self._serial_no,
            event_type,
            event_timestamp,
        )
        super()._trigger_event(event_type, event_attributes)

    @property
    def state(self) -> str:
        """Return the latest event type for the device."""
        return self._last_event_type or "No events"

    @property
    def extra_state_attributes(self):
        """Return additional attributes for the most recent event."""
        if not self._events:
            return {}

        recent_event = self._events[-1]
        return {
            "time": recent_event.get("Time"),
            "user": recent_event.get("User", "unknown"),
            "channel": recent_event.get("Channel", "unknown"),
        }

    @property
    def device_info(self):
        """Return device information to associate this entity with a Smart Lock."""
        return {
            "identifiers": {("sector", self._serial_no)},
            "name": self._device_info["name"],
            "manufacturer": "Sector Alarm",
            "model": self._device_info["model"],
        }

    async def async_added_to_hass(self):
        """Set up continuous event processing once added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                lambda: self.hass.async_create_task(self.async_update())
            )
        )
        _LOGGER.debug(
            "SECTOR_EVENT: Continuous event processing set up for %s", self._attr_name
        )
