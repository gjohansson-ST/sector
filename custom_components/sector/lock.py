"""Locks for Sector Alarm."""

import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.lock import LockEntity
from homeassistant.components.lock.const import LockState
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant, callback
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
    """
    Sector Alarm Lock.

    To ensure UI responsiveness during lock/unlock operations, a custom pending state is used.
    This state is set immediately when a lock/unlock command is issued and cleared upon
    successful completion or failure of the operation.
    """

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
        self._pending_state: LockState | None = None
        self._attr_code_format = rf"^\d{{{self._panel_code_length_property}}}$"
        self._attr_unique_id = f"{serial_no}_lock"

    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        return self._pending_state == LockState.LOCKING

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        return self._pending_state == LockState.UNLOCKING

    @property
    def is_locked(self) -> bool:
        """Return true if the lock is locked."""
        # If there's a pending state, show it instead
        if self._pending_state is not None:
            return False

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

        # Set pending state immediately, before API call, for better UI experience
        self._pending_state = LockState.LOCKING
        self.async_write_ha_state()

        try:
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
        except Exception as err:
            # Clear pending state on failure, resets UI
            self._pending_state = None
            self.async_write_ha_state()
            raise err

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the device."""
        code: str | None = kwargs.get(ATTR_CODE)
        if TYPE_CHECKING:
            assert code is not None

        # Set pending state immediately, before API call, for better UI experience
        self._pending_state = LockState.UNLOCKING
        self.async_write_ha_state()

        try:
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
        except Exception as err:
            # Clear pending state on failure, resets UI
            self._pending_state = None
            self.async_write_ha_state()
            raise err

    @callback
    def _handle_coordinator_update(self) -> None:
        # Reset custom pending state
        self._pending_state = None
        super()._handle_coordinator_update()

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
