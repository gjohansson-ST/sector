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
                name=f"{device.get('name', 'Lock')}",
            )
            entities.append(
                SectorAlarmLock(coordinator, code_format, description, serial_no)
            )
            _LOGGER.debug("Added lock entity with serial: %s and name: %s", serial_no, description.name)

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
        super().__init__(coordinator, serial_no, {"name": description.name}, "Lock")
        self._attr_unique_id = f"{self._serial_no}_lock"
        self._attr_code_format = rf"^\d{{{code_format}}}$"

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            status = device["sensors"].get("lock_status")
            _LOGGER.debug("Lock %s status is currently: %s", self._serial_no, status)
            return status == "lock"
        _LOGGER.warning("No lock status found for lock %s", self._serial_no)
        return None

    async def async_lock(self, **kwargs):
        """Lock the device."""
        code = kwargs.get(ATTR_CODE)
        _LOGGER.debug("Lock requested for lock %s. Code: %s", self._serial_no, code)
        success = await self.coordinator.api.lock_door(self._serial_no, code=code)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        code = kwargs.get(ATTR_CODE)
        _LOGGER.debug("Unlock requested for lock %s. Code: %s", self._serial_no, code)
        success = await self.coordinator.api.unlock_door(self._serial_no, code=code)
        if success:
            await self.coordinator.async_request_refresh()
