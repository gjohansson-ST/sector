"""Locks for Sector Alarm."""

import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.lock import LockEntity
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import (
    HomeAssistantError,
    ConfigEntryAuthFailed,
)
from custom_components.sector.client import ApiError, AuthenticationError, LoginError

from .coordinator import (
    SectorActionDataUpdateCoordinator,
    SectorAlarmConfigEntry,
    SectorCoordinatorType,
)
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm locks."""
    coordinator = cast(
        SectorActionDataUpdateCoordinator,
        entry.runtime_data[SectorCoordinatorType.ACTION_DEVICES],
    )

    devices: dict[str, dict[str, Any]] = coordinator.data.get("devices", {})
    entities = []

    for serial_no, device_info in devices.items():
        model: str = device_info.get("model", "")
        if model == "Smart Lock":
            device_name: str = device_info["name"]
            entities.append(SectorAlarmLock(coordinator, serial_no, device_name, model))
            _LOGGER.debug(
                "Added lock entity with serial: %s and name: %s",
                serial_no,
                device_name,
            )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No lock entities to add.")


class SectorAlarmLock(
    SectorAlarmBaseEntity[SectorActionDataUpdateCoordinator], LockEntity
):
    """Representation of a Sector Alarm lock."""

    _attr_name = None

    def __init__(
        self,
        coordinator: SectorActionDataUpdateCoordinator,
        serial_no: str,
        device_name: str,
        device_model: str | None,
    ) -> None:
        """Initialize the lock with device info."""
        super().__init__(coordinator, serial_no, serial_no, device_name, device_model)
        self._attr_code_format = rf"^\d{{{self._panel_code_length_property}}}$"
        self._attr_unique_id = f"{serial_no}_lock"

    @property
    def is_locked(self) -> bool:
        """Return true if the lock is locked."""
        status: str = self._lock_status_property
        if status == "unknown":
            _LOGGER.warning("No lock status found for lock %s", self._serial_no)
            return False
        else:
            _LOGGER.debug("Lock %s status is currently: %s", self._serial_no, status)
            return str(status).lower() == "lock"

    async def async_lock(self, **kwargs) -> None:
        """Lock the device."""
        code: str | None = kwargs.get(ATTR_CODE)
        if TYPE_CHECKING:
            assert code is not None

        try:
            await self.coordinator.sector_api.lock_door(self._serial_no, code=code)
            await self.coordinator.async_request_refresh()
        except LoginError as err:
            raise ConfigEntryAuthFailed from err
        except AuthenticationError as err:
            raise HomeAssistantError(
                "Failed to lock door - authentication failed"
            ) from err
        except ApiError as err:
            raise HomeAssistantError("Failed to lock door - API related error") from err
        except Exception as err:
            raise HomeAssistantError("Failed to lock door - unexpected error") from err

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the device."""
        code: str | None = kwargs.get(ATTR_CODE)
        if TYPE_CHECKING:
            assert code is not None

        try:
            await self.coordinator.sector_api.unlock_door(self._serial_no, code=code)
            await self.coordinator.async_request_refresh()
        except LoginError as err:
            raise ConfigEntryAuthFailed from err
        except AuthenticationError as err:
            raise HomeAssistantError(
                "Failed to unlock door - authentication failed"
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                "Failed to unlock door - API related error"
            ) from err
        except Exception as err:
            raise HomeAssistantError(
                "Failed to unlock door - unexpected error"
            ) from err

    @property
    def _panel_code_length_property(self) -> int:
        lock_device = self._lock_device
        return lock_device.get("panel_code_length", 0)

    @property
    def _lock_status_property(self) -> str:
        lock_device = self._lock_device
        return lock_device.get("sensors", {}).get("lock_status", "unknown")

    @property
    def _lock_device(self) -> dict[str, Any]:
        return self.coordinator.data.get("devices", {}).get(self._device_id, {})
