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

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        device_name: str,
        device_model: str | None,
    ) -> None:
        """Initialize the base entity with device info."""
        super().__init__(coordinator)
        self._serial_no = serial_no
        self.device_name = device_name
        self.device_model = device_model
        _LOGGER.debug(
            "Initialized entity %s with serial number: %s",
            self.__class__.__name__,
            serial_no,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for integration."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name=self.device_name,
            manufacturer="Sector Alarm",
            model=self.device_model,
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
