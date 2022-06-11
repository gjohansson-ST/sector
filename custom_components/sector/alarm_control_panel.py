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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
    code: str | None = entry.options.get(CONF_CODE)

    async_add_entities(
        [
            SectorAlarmPanel(sector_hub, coordinator, code, key)
            for key in sector_hub.data
        ]
    )


class SectorAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Sector Alarm Panel."""

    def __init__(
        self,
        hub: SectorAlarmHub,
        coordinator: DataUpdateCoordinator,
        code: str | None,
        panel_id: str,
    ) -> None:
        """Initialize the Alarm panel."""
        self._hub = hub
        self._panel_id = panel_id
        super().__init__(coordinator)
        self._code: str | None = code
        self._displayname: str = self._hub.data[panel_id]["name"]
        self._attr_name = f"Sector Alarmpanel {panel_id}"
        self._attr_unique_id = f"sa_panel_{panel_id}"
        self._attr_changed_by = self._hub.data[panel_id]["changed_by"]
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
        )
        self._attr_code_arm_required = False
        self._attr_code_format = CodeFormat.NUMBER
        self._attr_state = ALARM_STATE_TO_HA_STATE[
            self._hub.data[panel_id]["alarmstatus"]
        ]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"sa_panel_{self._panel_id}")},
            "name": f"Sector Alarmpanel {self._panel_id}",
            "manufacturer": "Sector Alarm",
            "model": "Alarmpanel",
            "sw_version": "master",
            "via_device": (DOMAIN, f"sa_hub_{self._panel_id}"),
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Additional states for alarm panel."""
        return {
            "display_name": self._displayname,
            "is_online": self._hub.data[self._panel_id]["online"],
            "arm_ready": self._hub.data[self._panel_id]["arm_ready"],
        }

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm alarm home."""
        command = "partial"
        if code is None:
            code = self._code
        if code and len(code) == self._hub.data[self._panel_id]["codelength"]:
            await self._hub.triggeralarm(command, code=code, panel_id=self._panel_id)
            self._attr_state = STATE_ALARM_ARMED_HOME
            if self._hub.logname:
                self._attr_changed_by = self._hub.logname
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided or incorrect length")

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Arm alarm off."""
        command = "disarm"
        if code is None:
            code = self._code
        if code and len(code) == self._hub.data[self._panel_id]["codelength"]:
            await self._hub.triggeralarm(command, code=code, panel_id=self._panel_id)
            self._attr_state = STATE_ALARM_DISARMED
            if self._hub.logname:
                self._attr_changed_by = self._hub.logname
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided or incorrect length")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm alarm away."""
        command = "full"
        if code is None:
            code = self._code
        if code and len(code) == self._hub.data[self._panel_id]["codelength"]:
            await self._hub.triggeralarm(command, code=code, panel_id=self._panel_id)
            self._attr_state = STATE_ALARM_ARMED_AWAY
            if self._hub.logname:
                self._attr_changed_by = self._hub.logname
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided or incorrect length")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_changed_by = self._hub.data[self._panel_id]["changed_by"]
        self._attr_state = ALARM_STATE_TO_HA_STATE[
            self._hub.data[self._panel_id]["alarmstatus"]
        ]
        self.async_write_ha_state()
