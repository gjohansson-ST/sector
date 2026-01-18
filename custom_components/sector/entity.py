"""Base entity for Sector Alarm integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from homeassistant.util import dt as dt_util
import logging
from typing import Any, TypeVar

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from custom_components.sector.coordinator import SectorBaseDataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_DataT = TypeVar("_DataT", bound=SectorBaseDataUpdateCoordinator)

_FAILED_UPDATE_LIMIT = 2
_LAST_UPDATED_LIMIT_HOURS = 1


class SectorAlarmBaseEntity(CoordinatorEntity[_DataT]):
    """Representation of a Sector Alarm base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _DataT,
        device_id: str,
        serial_no: str,
        device_name: str,
        device_model: str | None,
    ) -> None:
        """Initialize the base entity with device info."""
        super().__init__(coordinator)
        self._device_id = device_id
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
        device = self.coordinator.data.get("devices", {}).get(self._device_id, None)
        if device is None:
            return False

        """Check if the device is older than an hour, if so it is not available."""
        last_updated: str | None = device.get("last_updated")
        if last_updated:
            now = datetime.now(tz=dt_util.UTC)
            last_updated_dt = datetime.fromisoformat(last_updated)
            is_older_than_an_hour = now - last_updated_dt > timedelta(
                hours=_LAST_UPDATED_LIMIT_HOURS
            )
            if is_older_than_an_hour:
                return False

        """Check if the coordinator is healthy and device has not too many failed updates."""
        coordinator_healthy = self.coordinator.is_healthy()
        failed_update_count: int = device.get("failed_update_count", 0)
        return coordinator_healthy and failed_update_count < _FAILED_UPDATE_LIMIT
