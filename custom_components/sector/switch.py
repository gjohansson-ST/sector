"""Switch platform for Sector Alarm integration."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_OUTLET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Sector Alarm switches."""
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    switches_data = coordinator.data.get("Smartplug Status", [])
    entities = []

    for plug in switches_data:
        entities.append(SectorAlarmSwitch(coordinator, plug))

    if entities:
        async_add_entities(entities)
    else:
        LOGGER.debug("No switch entities to add.")


class SectorAlarmSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Sector Alarm smart plug."""

    _attr_device_class = DEVICE_CLASS_OUTLET

    def __init__(
        self, coordinator: SectorDataUpdateCoordinator, plug_data: dict
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._plug_data = plug_data
        self._id = plug_data.get("Id")
        self._serial_no = plug_data.get("SerialNo") or plug_data.get("Serial")
        self._attr_unique_id = f"{self._serial_no}_switch"
        self._attr_name = plug_data.get("Label", "Sector Smart Plug")
        LOGGER.debug(f"Initialized switch with unique_id: {self._attr_unique_id}")

    @property
    def is_on(self):
        """Return true if the switch is on."""
        for plug in self.coordinator.data.get("Smartplug Status", []):
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
