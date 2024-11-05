"""Locks for Sector Alarm."""

import logging

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_CODE
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError

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
    devices = coordinator.data.get("devices", {})
    entities = []

    for device in devices.values():
        if device.get("model") == "Smart Lock":
            entities.append(SectorAlarmLock(coordinator, device))

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No lock entities to add.")


class SectorAlarmLock(SectorAlarmBaseEntity, LockEntity):
    """Representation of a Sector Alarm lock."""

    _attr_name = None
    _attr_code_required = True

    def __init__(self, coordinator: SectorDataUpdateCoordinator, device_info: dict):
        """Initialize the lock."""
        super().__init__(
            coordinator, device_info["serial_no"], device_info, device_info["model"]
        )
        self._attr_unique_id = f"{self._serial_no}_lock"

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
        is_valid = self._is_valid_code(code)
        _LOGGER.debug(
            "Lock requested for lock %s. Code: %s, Is valid: %s", self._serial_no, code, is_valid
        )
        if self._attr_code_required and not is_valid:
            raise HomeAssistantError("Code required to lock the system.")
        success = await self.coordinator.api.lock_door(self._serial_no, code=code)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        code = kwargs.get(ATTR_CODE)
        is_valid = self._is_valid_code(code)
        _LOGGER.debug(
            "Unlock requested for lock %s. Code: %s, Is valid: %s", self._serial_no, code, is_valid
        )
        if self._attr_code_required and not is_valid:
            raise HomeAssistantError("Code required to unlock the system.")
        success = await self.coordinator.api.unlock_door(self._serial_no, code=code)
        if success:
            await self.coordinator.async_request_refresh()
