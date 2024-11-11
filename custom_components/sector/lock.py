"""Locks for Sector Alarm."""

import logging

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CODE_FORMAT
from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sector Alarm locks."""
    coordinator = entry.runtime_data
    code_format = entry.options.get(CONF_CODE_FORMAT, 6)
    devices = coordinator.data.get("devices", {})
    entities = []

    for device in devices.values():
        if device.get("model") == "Smart Lock":
            serial_no = device["serial_no"]
            description = LockEntityDescription(
                key=serial_no,
                name=f"{device.get('name', 'Smart Lock')}",
            )
            entities.append(
                SectorAlarmLock(coordinator, code_format, description, serial_no)
            )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No lock entities to add.")

class SectorAlarmLock(SectorAlarmBaseEntity, LockEntity):
    """Representation of a Sector Alarm lock."""

    _attr_name = None

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        code_format: int,
        description: LockEntityDescription,
        serial_no: str,
    ):
        """Initialize the lock."""
        super().__init__(coordinator, serial_no, {"name": description.name}, "Smart Lock")
        self._attr_unique_id = f"{self._serial_no}_lock"
        self._attr_code_format = rf"^\d{{{code_format}}}$"

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            status = device["sensors"].get("lock_status")
            return status == "lock"
        return None

    async def async_lock(self, **kwargs):
        """Lock the device."""
        code = kwargs.get(ATTR_CODE)
        _LOGGER.debug("Lock requested for lock %s. Code: %s", self._serial_no, code)

        try:
            success = await self.coordinator.api.lock_door(self._serial_no, code=code)
            if success:
                await self.coordinator.async_request_refresh()
                await self.coordinator.process_events()  # Explicitly trigger event processing
            else:
                await self.async_lock_failed()
        except Exception as e:
            _LOGGER.error("Lock failed for %s: %s", self._serial_no, e)
            await self.async_lock_failed()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        code = kwargs.get(ATTR_CODE)
        _LOGGER.debug("Unlock requested for lock %s. Code: %s", self._serial_no, code)

        try:
            success = await self.coordinator.api.unlock_door(self._serial_no, code=code)
            if success:
                await self.coordinator.async_request_refresh()
                await self.coordinator.process_events()  # Explicitly trigger event processing
            else:
                await self.async_lock_failed()
        except Exception as e:
            _LOGGER.error("Unlock failed for %s: %s", self._serial_no, e)
            await self.async_lock_failed()

    async def async_lock_failed(self, **kwargs):
        """Handle a failed lock attempt."""
        _LOGGER.debug("Lock failed for lock %s", self._serial_no)

        # Trigger the state update for Home Assistant to reflect lock_failed
        self._last_event_type = "lock_failed"
        self.async_write_ha_state()  # Force state update in Home Assistant

        # Directly log lock_failed event in the event history
        self.coordinator.data["logs"].append({
            "LockName": self._serial_no,
            "EventType": "lock_failed",
            "Time": datetime.now(timezone.utc).isoformat()
        })

        await self.coordinator.process_events()  # Explicitly trigger event processing
