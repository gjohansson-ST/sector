"""Lock platform for Sector Alarm integration."""
from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Sector Alarm locks."""
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    locks_data = coordinator.data.get("locks", [])
    entities = []

    for lock in locks_data:
        entities.append(SectorAlarmLock(coordinator, lock))

    async_add_entities(entities)


class SectorAlarmLock(CoordinatorEntity, LockEntity):
    """Representation of a Sector Alarm lock."""

    def __init__(
        self, coordinator: SectorDataUpdateCoordinator, lock_data: dict
    ) -> None:
        """Initialize the lock."""
        super().__init__(coordinator)
        self._lock_data = lock_data
        self._serial_no = lock_data.get("Serial")
        self._attr_unique_id = self._serial_no
        self._attr_name = lock_data.get("Label", "Sector Lock")

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._lock_data.get("Status") == "lock"

    async def async_lock(self, **kwargs):
        """Lock the device."""
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.actions_manager.lock_door, self._lock_data["Serial"]
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.actions_manager.unlock_door, self._lock_data["Serial"]
        )
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
