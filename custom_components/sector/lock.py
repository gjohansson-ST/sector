# lock.py
"""Lock platform for Sector Alarm integration."""
import logging

from homeassistant.components.lock import LockEntity
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sector Alarm lock based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    locks = []

    for device in coordinator.data.get("Lock Status", []):
        locks.append(SectorLock(coordinator, device))

    async_add_entities(locks, True)


class SectorLock(CoordinatorEntity, LockEntity):
    """Representation of a Sector Alarm lock."""

    def __init__(self, coordinator: SectorDataUpdateCoordinator, device: dict) -> None:
        """Initialize the Sector Alarm lock."""
        super().__init__(coordinator)
        self._device = device

    @property
    def name(self) -> str:
        """Return the name of the lock."""
        return self._device["Label"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this lock."""
        return self._device["Serial"]

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._device["Status"].lower() == "lock"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            ATTR_BATTERY_LEVEL: 100 if not self._device["BatteryLow"] else 20,
        }

    async def async_lock(self, **kwargs) -> None:
        """Lock the device."""
        await self.coordinator.api.triggeralarm("lock", "", self._device["Serial"])
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the device."""
        await self.coordinator.api.triggeralarm("unlock", "", self._device["Serial"])
        await self.coordinator.async_request_refresh()
