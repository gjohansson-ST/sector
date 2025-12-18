"""Switch platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
                "Added lock entity with serial: %s and name: %s",
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
    """Representation of a Sector Alarm smart plug."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_name = None

    def __init__(
        self,
        coordinator: SectorActionDataUpdateCoordinator,
        plug_id,
        serial_no,
        name,
        model,
    ) -> None:
        """Initialize the switch."""
        self._id = plug_id
        super().__init__(
            coordinator,
            serial_no,
            name,
            model,
        )

        self._attr_unique_id = f"{self._serial_no}_switch"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            status = device["sensors"].get("plug_status")
            _LOGGER.debug("Switch %s status is currently: %s", self._serial_no, status)
            return status == "On"
        _LOGGER.warning("No switch status found for plug %s", self._serial_no)
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        success = await self.coordinator.api.turn_on_smartplug(self._id)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        success = await self.coordinator.api.turn_off_smartplug(self._id)
        if success:
            await self.coordinator.async_request_refresh()
