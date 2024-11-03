"""Switch platform for Sector Alarm integration."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Sector Alarm switches."""
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    switches_data = coordinator.data.get("smartplugs", [])
    entities = []

    for switch in switches_data:
        entities.append(SectorAlarmSwitch(coordinator, switch))

    async_add_entities(entities)


class SectorAlarmSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Sector Alarm smart plug."""

    _attr_device_class = DeviceClass.OUTLET

    def __init__(
        self, coordinator: SectorDataUpdateCoordinator, switch_data: dict
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._switch_data = switch_data
        self._serial_no = switch_data.get("SerialNo") or switch_data.get("Serial")
        self._attr_unique_id = self._serial_no
        self._attr_name = switch_data.get("Label", "Sector Smart Plug")

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._switch_data.get("Status") == "On"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.actions_manager.turn_on_smartplug,
            self._switch_data["Id"],
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.actions_manager.turn_off_smartplug,
            self._switch_data["Id"],
        )
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
