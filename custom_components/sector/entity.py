"""Base entity for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class SectorAlarmBaseEntity(CoordinatorEntity[SectorDataUpdateCoordinator]):
    """Representation of a Sector Alarm base entity."""

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        device_info: Dict[str, str]
    ) -> None:
        """Initialize the base entity with device info."""
        super().__init__(coordinator)
        self._serial_no = serial_no
        self._device_info = device_info  # Store device info centrally
        self._attr_unique_id = f"{serial_no}_{self.__class__.__name__.lower()}"
        _LOGGER.debug(
            "Initialized entity %s with serial number: %s", self.__class__.__name__, serial_no
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for integration."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name=self._device_info.get("name"),
            manufacturer="Sector Alarm",
            model=self._device_info.get("model"),
            serial_number=self._serial_no,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {"serial_number": self._serial_no}

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True
