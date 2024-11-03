"""Lock platform for Sector Alarm integration."""
from __future__ import annotations

import logging

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Sector Alarm locks."""
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    locks_data = coordinator.data.get("locks", [])
    entities = []

    for lock in locks_data:
        entities.append(SectorAlarmLock(coordinator, lock))

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No lock entities to add.")


class SectorAlarmLock(CoordinatorEntity, LockEntity):
    """Representation of a Sector Alarm lock."""

    def __init__(self, coordinator: SectorDataUpdateCoordinator, lock_data: dict) -> None:
        """Initialize the lock."""
        super().__init__(coordinator)
        self._lock_data = lock_data
        self._serial_no = str(lock_data.get("SerialNo") or lock_data.get("Serial"))
        self._attr_unique_id = f"{self._serial_no}_lock"
        self._attr_name = lock_data.get("Label", "Sector Lock")
        _LOGGER.debug(f"Initialized lock with unique_id: {self._attr_unique_id}")

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        for lock in self.coordinator.data.get("locks", []):
            if str(lock.get("SerialNo") or lock.get("Serial")) == self._serial_no:
                return lock.get("Locked")
        return False

    async def async_lock(self, **kwargs):
        """Lock the device."""
        success = await self.coordinator.api.lock_door(self._serial_no)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        success = await self.coordinator.api.unlock_door(self._serial_no)
        if success:
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name=self._attr_name,
            manufacturer="Sector Alarm",
            model="Lock",
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True
