"""Switch platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
)
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
    """Set up Sector Alarm switches."""
    coordinator = cast(
        SectorActionDataUpdateCoordinator,
        entry.runtime_data[SectorCoordinatorType.ACTION_DEVICES],
    )
    devices: dict[str, dict[str, Any]] = coordinator.data.get("devices", {})
    entities = []

    for serial_no, device_info in devices.items():
        if device_info.get("model") == "Smart Plug":
            device_name: str = device_info["name"]
            plug_id = device_info["id"]
            model = device_info["model"]
            entities.append(
                SectorAlarmSwitch(coordinator, plug_id, serial_no, device_name, model)
            )
            _LOGGER.debug(
                "Added switch entity with serial: %s and name: %s",
                serial_no,
                device_name,
            )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No switch entities to add.")


class SectorAlarmSwitch(
    SectorAlarmBaseEntity[SectorActionDataUpdateCoordinator], SwitchEntity
):
    """
    Sector Alarm smart plug switch.

    This device is cloud-controlled and does not provide immediate state
    confirmation after a service call. State updates are retrieved via
    periodic polling using a DataUpdateCoordinator.

    For this reason, the entity uses an assumed (optimistic) state model:
    - State is updated optimistically on turn_on / turn_off
    - The coordinator later reconciles the actual device state

    This prevents UI flip-flopping caused by delayed cloud updates.
    In other words, Sector Alarm smart plug switch is asynchronous
    """

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_name = None

    def __init__(
        self,
        coordinator: SectorActionDataUpdateCoordinator,
        plug_id: str,
        serial_no: str,
        name: str,
        model: str,
    ) -> None:
        """Initialize the switch."""
        self._id = plug_id
        super().__init__(
            coordinator,
            serial_no,
            serial_no,
            name,
            model,
        )

        self._attr_unique_id = f"{self._serial_no}_switch"
        self._attr_is_on: bool | None = None

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        # Assume optimistic state if set
        if self._attr_is_on is not None:
            _LOGGER.debug(
                "Switch %s assumed status: %s",
                self._serial_no,
                self._attr_is_on,
            )
            return self._attr_is_on

        # Fall back to coordinator data
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            status = device["sensors"].get("plug_status")
            _LOGGER.debug(
                "Switch %s coordinator status: %s",
                self._serial_no,
                status,
            )
            return status == "On"

        _LOGGER.warning(
            "No switch status found for plug %s",
            self._serial_no,
        )
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.api.turn_on_smartplug(self._id)

            # Optimistic update
            self._attr_is_on = True
            self.async_write_ha_state()
        except LoginError as err:
            raise ConfigEntryAuthFailed from err
        except AuthenticationError as err:
            raise HomeAssistantError(
                "Failed to turn on switch - authentication failed"
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                "Failed to turn on switch - API related error"
            ) from err
        except Exception as err:
            raise HomeAssistantError(
                "Failed to turn on switch - unexpected error"
            ) from err

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.api.turn_off_smartplug(self._id)

            # Optimistic update
            self._attr_is_on = False
            self.async_write_ha_state()
        except LoginError as err:
            raise ConfigEntryAuthFailed from err
        except AuthenticationError as err:
            raise HomeAssistantError(
                "Failed to turn off switch - authentication failed"
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                "Failed to turn off switch - API related error"
            ) from err
        except Exception as err:
            raise HomeAssistantError(
                "Failed to turn off switch - unexpected error"
            ) from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        # Clear optimistic variable, replace by real coordinator data
        self._attr_is_on = None
        super()._handle_coordinator_update()
