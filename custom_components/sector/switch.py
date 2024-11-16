"""Switch platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm switches."""
    coordinator = entry.runtime_data
    devices = coordinator.data.get("devices", {})
    smartplugs = devices.get("smartplugs", [])

    if smartplugs:
        async_add_entities(SectorAlarmSwitch(coordinator, plug) for plug in smartplugs)
    else:
        _LOGGER.debug("No switch entities to add.")


class SectorAlarmSwitch(SectorAlarmBaseEntity, SwitchEntity):
    """Representation of a Sector Alarm smart plug."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_name = None

    def __init__(
        self, coordinator: SectorDataUpdateCoordinator, plug_data: dict[str, Any]
    ) -> None:
        """Initialize the switch."""
        self._id = plug_data.get("Id")
        serial_no = str(plug_data.get("SerialNo") or plug_data.get("Serial"))
        super().__init__(
            coordinator,
            serial_no,
            plug_data.get("Label", "Sector Smart Plug"),
            "Smart Plug",
        )

        self._attr_unique_id = f"{self._serial_no}_switch"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        smartplugs = self.coordinator.data["devices"].get("smartplugs", [])
        for plug in smartplugs:
            if plug.get("Id") == self._id:
                return plug.get("State") == "On"
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
