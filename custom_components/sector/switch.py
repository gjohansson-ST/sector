"""Switch platform for Sector Alarm integration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sector Alarm switches."""
    coordinator = entry.runtime_data
    devices = coordinator.data.get("devices", {})
    entities = []

    smartplugs = devices.get("smartplugs", [])

    for plug in smartplugs:
        entities.append(SectorAlarmSwitch(coordinator, plug))

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No switch entities to add.")


class SectorAlarmSwitch(CoordinatorEntity[SectorDataUpdateCoordinator], SwitchEntity):
    """Representation of a Sector Alarm smart plug."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(
        self, coordinator: SectorDataUpdateCoordinator, plug_data: dict
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._plug_data = plug_data
        self._id = plug_data.get("Id")
        self._serial_no = str(plug_data.get("SerialNo") or plug_data.get("Serial"))
        self._attr_unique_id = f"{self._serial_no}_switch"
        self._attr_name = plug_data.get("Label", "Sector Smart Plug")
        _LOGGER.debug("Initialized switch with unique_id: %s", self._attr_unique_id)

    @property
    def is_on(self):
        """Return true if the switch is on."""
        smartplugs = self.coordinator.data["devices"].get("smartplugs", [])
        for plug in smartplugs:
            if plug.get("Id") == self._id:
                return plug.get("State") == "On"
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        success = await self.coordinator.api.turn_on_smartplug(self._id)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        success = await self.coordinator.api.turn_off_smartplug(self._id)
        if success:
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name=self._attr_name,
            manufacturer="Sector Alarm",
            model="Smart Plug",
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True
