"""Adds Alarm Panel for Sector integration."""
from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    CodeFormat,
)
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .__init__ import SectorAlarmHub
from .const import CONF_CODE, DOMAIN

ALARM_STATE_TO_HA_STATE = {
    3: STATE_ALARM_ARMED_AWAY,
    2: STATE_ALARM_ARMED_HOME,
    1: STATE_ALARM_DISARMED,
    0: STATE_ALARM_PENDING,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up alarm panel from config entry."""

    sector_hub: SectorAlarmHub = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    code: str = entry.data[CONF_CODE]

    async_add_entities([SectorAlarmPanel(sector_hub, coordinator, code)])


class SectorAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Sector Alarm Panel."""

    def __init__(
        self, hub: SectorAlarmHub, coordinator: DataUpdateCoordinator, code: str
    ) -> None:
        """Initialize the Alarm panel."""
        self._hub = hub
        super().__init__(coordinator)
        self._code: str = code if code != "" else None
        self._displayname: str = self._hub.alarm_displayname
        self._isonline: str = self._hub.alarm_isonline
        self._attr_name = f"Sector Alarmpanel {self._hub.alarm_id}"
        self._attr_unique_id = f"sa_panel_{str(self._hub.alarm_id)}"
        self._attr_changed_by = self._hub.alarm_changed_by
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
        )
        self._attr_code_arm_required = False
        self._attr_code_format = CodeFormat.NUMBER
        self._attr_state = self._hub.alarm_state

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self._attr_name,
            "manufacturer": "Sector Alarm",
            "model": "Alarmpanel",
            "sw_version": "master",
            "via_device": (DOMAIN, f"sa_hub_{str(self._hub.alarm_id)}"),
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Additional states for alarm panel."""
        return {"Display name": self._displayname, "Is Online": self._isonline}

    async def async_alarm_arm_home(self, code=None) -> None:
        """Arm alarm home."""
        command = "partial"
        if code is None:
            code = self._code
        if code:
            await self._hub.triggeralarm(command, code=code)
            self._attr_state = STATE_ALARM_ARMED_HOME
            if self._hub.log_name:
                self._attr_changed_by = self._hub.log_name
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided")

    async def async_alarm_disarm(self, code=None) -> None:
        """Arm alarm off."""
        command = "disarm"
        if code is None:
            code = self._code
        if code:
            await self._hub.triggeralarm(command, code=code)
            self._attr_state = STATE_ALARM_DISARMED
            if self._hub.log_name:
                self._attr_changed_by = self._hub.log_name
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided")

    async def async_alarm_arm_away(self, code=None) -> None:
        """Arm alarm away."""
        command = "full"
        if code is None:
            code = self._code
        if code:
            await self._hub.triggeralarm(command, code=code)
            self._attr_state = STATE_ALARM_ARMED_AWAY
            if self._hub.log_name:
                self._attr_changed_by = self._hub.log_name
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._isonline: str = self._hub.alarm_isonline
        self._attr_changed_by = self._hub.alarm_changed_by
        self._attr_state = ALARM_STATE_TO_HA_STATE[self._hub.alarm_state]
        self.async_write_ha_state()
