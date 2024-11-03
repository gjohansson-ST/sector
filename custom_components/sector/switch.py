"""Switch platform for Sector Alarm integration."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DeviceClass
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
    devices = coordinator.data.get("devices", {})
    entities = []

    for device in devices.values():
        serial_no = device["serial_no"]
        sensors = device.get("sensors", {})
        if "smartplug_state" in sensors:
            entities.append(SectorAlarmSwitch(coordinator, serial_no, device))

    if entities:
        async_add_entities(entities)
    else:
        LOGGER.debug("No switch entities to add.")


class SectorAlarmSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Sector Alarm smart plug."""

    _attr_device_class = DeviceClass.OUTLET

    def __init__(
        self, coordinator: SectorDataUpdateCoordinator, serial_no: str, device_info: dict
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._serial_no = serial_no
        self._device_info = device_info
        self._attr_unique_id = f"{serial_no}_switch"
        self._attr_name = device_info.get("name", "Sector Smart Plug")
        LOGGER.debug(f"Initialized switch with unique_id: {self._attr_unique_id}")

    @property
    def is_on(self):
        """Return true if the switch is on."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            return device["sensors"].get("smartplug_state", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        success = await self.coordinator.api.turn_on_smartplug(self._serial_no)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        success = await self.coordinator.api.turn_off_smartplug(self._serial_no)
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
