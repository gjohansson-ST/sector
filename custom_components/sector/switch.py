"""Adds switch for Sector integration."""
from __future__ import annotations

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Switch platform."""

    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    switch_list: list = []
    for panel, panel_data in coordinator.data.items():
        if "switch" in panel_data:
            for switch, switch_data in panel_data["switch"].items():
                name = switch_data["name"]
                serial = switch_data["serial"]
                description = SwitchEntityDescription(
                    key=switch, name=name, device_class=SwitchDeviceClass.OUTLET
                )
                switch_list.append(
                    SectorAlarmSwitch(coordinator, description, serial, panel)
                )

    if switch_list:
        async_add_entities(switch_list)


class SectorAlarmSwitch(CoordinatorEntity[SectorDataUpdateCoordinator], SwitchEntity):
    """Sector Switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        description: SwitchEntityDescription,
        serial: str,
        panel_id: str,
    ) -> None:
        """Initialize Switch."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        self._attr_unique_id = f"sa_switch_{serial}"
        self.entity_description = description
        self._attr_is_on = bool(
            self.coordinator.data[panel_id]["switch"][description.key]["status"] == "On"
        )
        self.serial = serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"sa_switch_{serial}")},
            name=description.name,
            manufacturer="Sector Alarm",
            model="Switch",
            sw_version="master",
            via_device=(DOMAIN, f"sa_hub_{panel_id}"),
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Additional states for switch."""
        return {
            "Serial No": self.serial,
            "Id": self.entity_description.key,
        }

    async def async_turn_on(self, **kwargs: str) -> None:
        """Turn the switch on."""
        await self.coordinator.triggerswitch(
            self.entity_description.key, "on", self._panel_id
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: str) -> None:
        """Turn the switch off."""
        await self.coordinator.triggerswitch(
            self.entity_description.key, "off", self._panel_id
        )
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if switch := self.coordinator.data[self._panel_id]["switch"].get(
            self.entity_description.key
        ):
            self._attr_is_on = bool(switch.get("status") == "On")
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity available."""
        return True
