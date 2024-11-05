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
        device_info: dict,
        model: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._serial_no = serial_no
        self._name = device_info["name"]
        self._model = model
        _LOGGER.debug(
            "Initialized entity %s %s with unique_id: %s",
            self._name,
            self._model,
            self._serial_no
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name=self._name,
            manufacturer="Sector Alarm",
            model=self._model,
            serial_number=self._serial_no,
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if hasattr(self, "_serial_no"):
            return {
                "serial_number": self._serial_no,
            }

    def _is_valid_code(self, code: str) -> bool:
        expected_length = self.coordinator.code_format
        is_valid = bool(code and len(code) == expected_length)
        _LOGGER.debug("Validating code. Received code: %s, Expected length: %d, Is valid: %s", code, expected_length, is_valid)
        return is_valid
