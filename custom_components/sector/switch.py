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
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import SectorAlarmHub


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Switch platform."""

    sector_hub: SectorAlarmHub = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    switch_list: list = []
    for panel, panel_data in sector_hub.data.items():
        if "switch" in panel_data:
            for switch, switch_data in panel_data["switch"].items():
                name = switch_data["name"]
                serial = switch_data["serial"]
                description = SwitchEntityDescription(
                    key=switch, name=name, device_class=SwitchDeviceClass.OUTLET
                )
                switch_list.append(
                    SectorAlarmSwitch(
                        sector_hub, coordinator, description, serial, panel
                    )
                )

    if switch_list:
        async_add_entities(switch_list)


class SectorAlarmSwitch(CoordinatorEntity, SwitchEntity):
    """Sector Switch."""

    def __init__(
        self,
        hub: SectorAlarmHub,
        coordinator: DataUpdateCoordinator,
        description: SwitchEntityDescription,
        serial: str,
        panel_id: str,
    ) -> None:
        """Initialize Switch."""
        self._hub = hub
        self._panel_id = panel_id
        super().__init__(coordinator)
        self._attr_name = description.name
        self._attr_unique_id = f"sa_switch_{serial}"
        self.entity_description = description
        self._attr_is_on = bool(
            self._hub.data[panel_id]["switch"][description.key]["status"] == "On"
        )
        self.serial = serial

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"sa_switch_{self.serial}")},
            "name": self.entity_description.name,
            "manufacturer": "Sector Alarm",
            "model": "Switch",
            "sw_version": "master",
            "via_device": (DOMAIN, f"sa_hub_{self._panel_id}"),
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Additional states for switch."""
        return {
            "Serial No": self.serial,
            "Id": self.entity_description.key,
        }

    async def async_turn_on(self, **kwargs: str) -> None:
        """Turn the switch on."""
        await self._hub.triggerswitch(self.entity_description.key, "on", self._panel_id)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: str) -> None:
        """Turn the switch off."""
        await self._hub.triggerswitch(
            self.entity_description.key, "off", self._panel_id
        )
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = bool(
            self._hub.data[self._panel_id]["switch"][self.entity_description.key].get(
                "status"
            )
            == "On"
        )
        self.async_write_ha_state()
