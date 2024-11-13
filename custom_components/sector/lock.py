"""Locks for Sector Alarm."""

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.lock import LockEntity
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
) -> None:
    """Set up Sector Alarm locks."""
    coordinator = entry.runtime_data
    code_format = entry.options[CONF_CODE_FORMAT]
    devices: dict[str, dict[str, Any]] = coordinator.data.get("devices", {})
    entities = []

    for serial_no, device_info in devices.items():
        if device_info.get("model") == "Smart Lock":
            device_name: str = device_info["name"]
            entities.append(
                SectorAlarmLock(
                    coordinator, code_format, serial_no, device_name, "Smart Lock"
                )
            )
            _LOGGER.debug(
                "Added lock entity with serial: %s and name: %s",
                serial_no,
                device_name,
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
        serial_no: str,
        device_name: str,
        device_model: str | None,
    ) -> None:
        """Initialize the lock with device info."""
        super().__init__(coordinator, serial_no, device_name, device_model)
        self._attr_code_format = rf"^\d{{{code_format}}}$"
        self._attr_unique_id = f"{serial_no}_lock"

    @property
    def is_locked(self) -> bool:
        """Return true if the lock is locked."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            status = device["sensors"].get("lock_status")
            _LOGGER.debug("Lock %s status is currently: %s", self._serial_no, status)
            return status == "lock"
        _LOGGER.warning("No lock status found for lock %s", self._serial_no)
        return False

    async def async_lock(self, **kwargs) -> None:
        """Lock the device."""
        code: str | None = kwargs.get(ATTR_CODE)
        if TYPE_CHECKING:
            assert code is not None
        _LOGGER.debug("Lock requested for lock %s. Code: %s", self._serial_no, code)
        success = await self.coordinator.api.lock_door(self._serial_no, code=code)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the device."""
        code: str | None = kwargs.get(ATTR_CODE)
        if TYPE_CHECKING:
            assert code is not None
        _LOGGER.debug("Unlock requested for lock %s. Code: %s", self._serial_no, code)
        success = await self.coordinator.api.unlock_door(self._serial_no, code=code)
        if success:
            await self.coordinator.async_request_refresh()
