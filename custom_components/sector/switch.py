"""Adds switch for Sector integration."""
import logging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .__init__ import SectorAlarmHub
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Switch platform."""

    sector_hub: SectorAlarmHub = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    switches = await sector_hub.get_switches()
    switchlist: list = []
    for switch in switches:
        name = await sector_hub.get_name(switch, "switch")
        description = SwitchEntityDescription(
            key=switch, name=name, device_class=SwitchDeviceClass.OUTLET
        )
        switchlist.append(SectorAlarmSwitch(sector_hub, coordinator, description))

    if switchlist:
        async_add_entities(switchlist)


class SectorAlarmSwitch(CoordinatorEntity, SwitchEntity):
    """Sector Switch."""

    def __init__(
        self,
        hub: SectorAlarmHub,
        coordinator: DataUpdateCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize Switch."""
        self._hub = hub
        super().__init__(coordinator)
        self._serial = description.key
        self._attr_name = description.name
        self._attr_unique_id: str = "sa_switch_" + str(description.key)
        self.entity_description = description
        self._attr_is_on = bool(self._hub.switch_state[self._serial] == "On")
        self._id: str = self._hub.switch_id[self._serial]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self._attr_name,
            "manufacturer": "Sector Alarm",
            "model": "Switch",
            "sw_version": "master",
            "via_device": (DOMAIN, "sa_hub_" + str(self._hub.alarm_id)),
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Additional states for switch."""
        return {
            "Serial No": self._serial,
            "Id": self._id,
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self.async_triggerswitch("On")

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self.async_triggerswitch("Off")

    async def async_triggerswitch(self, command) -> None:
        """Trigger switch."""
        await self._hub.triggerswitch(self._id, command)
        await self.coordinator.async_refresh()
