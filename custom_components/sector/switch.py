"""Switch platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

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
from custom_components.sector.const import RUNTIME_DATA
from .coordinator import (
    DeviceRegistry,
    SectorDeviceDataUpdateCoordinator,
    SectorAlarmConfigEntry,
)
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm switches."""
    entities: list[SectorAlarmSwitch] = []
    coordinators: list[SectorDeviceDataUpdateCoordinator] = entry.runtime_data[
        RUNTIME_DATA.DEVICE_COORDINATORS
    ]

    for coordinator in coordinators:
        device_registry: DeviceRegistry = coordinator.data.get(
            "device_registry", DeviceRegistry()
        )
        devices: dict[str, dict[str, Any]] = (
            device_registry.fetch_devices_by_coordinator(coordinator.name)
        )
        for serial_no, device in devices.items():
            device_name: str = device["name"]
            device_model = device["model"]
            for entity_model, entity in device.get("entities", {}).items():
                if entity_model == "Smart Plug":
                    plug_id = entity["id"]
                    entities.append(
                        SectorAlarmSwitch(
                            coordinator,
                            plug_id,
                            serial_no,
                            device_name,
                            device_model,
                            entity_model,
                        )
                    )
                    _LOGGER.debug("Added smart plug for device %s", serial_no)

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No switch entities to add.")


class SectorAlarmSwitch(
    SectorAlarmBaseEntity[SectorDeviceDataUpdateCoordinator], SwitchEntity
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
        coordinator: SectorDeviceDataUpdateCoordinator,
        plug_id: str,
        serial_no: str,
        device_name: str,
        device_model: str,
        entity_model: str,
    ) -> None:
        """Initialize the switch."""
        self._id = plug_id
        super().__init__(
            coordinator, serial_no, device_name, device_model, entity_model
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
        entity = self.entity_data or {}
        status = entity.get("sensors", {}).get("plug_status", "Unknown")
        _LOGGER.debug(
            "Switch %s coordinator status: %s",
            self._serial_no,
            status,
        )
        return str(status).lower() == "on"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.sector_api.turn_on_smartplug(self._id)

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
            await self.coordinator.sector_api.turn_off_smartplug(self._id)

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
