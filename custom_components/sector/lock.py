"""Locks for Sector Alarm."""

import logging

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator

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


class SectorAlarmLock(CoordinatorEntity[SectorDataUpdateCoordinator], LockEntity):
    """Representation of a Sector Alarm lock."""

    def __init__(self, coordinator: SectorDataUpdateCoordinator, device_info: dict):
        """Initialize the lock."""
        super().__init__(coordinator)
        self._serial_no = device_info["serial_no"]
        self._device_info = device_info
        self._attr_unique_id = f"{self._serial_no}_lock"
        self._attr_name = device_info["name"]
        _LOGGER.debug("Initialized lock with unique_id: %s", self._attr_unique_id)

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
        await self.coordinator.api.lock_door(self._serial_no)
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        await self.coordinator.api.unlock_door(self._serial_no)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name=self._device_info["name"],
            manufacturer="Sector Alarm",
            model=self._device_info["model"],
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "serial_number": self._serial_no,
        }
