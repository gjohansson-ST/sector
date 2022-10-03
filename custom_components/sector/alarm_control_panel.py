"""Adds Alarm Panel for Sector integration."""
from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CODE, DOMAIN
from .coordinator import SectorDataUpdateCoordinator

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

    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    code: str | None = entry.options.get(CONF_CODE)

    async_add_entities(
        [SectorAlarmPanel(coordinator, code, key) for key in coordinator.data]
    )


class SectorAlarmPanel(
    CoordinatorEntity[SectorDataUpdateCoordinator], AlarmControlPanelEntity
):
    """Sector Alarm Panel."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        code: str | None,
        panel_id: str,
    ) -> None:
        """Initialize the Alarm panel."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        self._code: str | None = code
        self._displayname: str = self.coordinator.data[panel_id]["name"]
        self._attr_unique_id = f"sa_panel_{panel_id}"
        self._attr_changed_by = self.coordinator.data[panel_id]["changed_by"]
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
        )
        self._attr_code_arm_required = False
        self._attr_code_format = CodeFormat.NUMBER
        self._attr_state = ALARM_STATE_TO_HA_STATE[
            self.coordinator.data[panel_id]["alarmstatus"]
        ]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"sa_panel_{panel_id}")},
            name=f"Sector Alarmpanel {panel_id}",
            manufacturer="Sector Alarm",
            model="Alarmpanel",
            sw_version="master",
            via_device=(DOMAIN, f"sa_hub_{panel_id}"),
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Additional states for alarm panel."""
        return {
            "display_name": self._displayname,
        }

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm alarm home."""
        command = "partial"
        if code is None:
            code = self._code
        if code and len(code) == self.coordinator.data[self._panel_id]["codelength"]:
            await self.coordinator.triggeralarm(
                command, code=code, panel_id=self._panel_id
            )
            self._attr_state = STATE_ALARM_ARMED_HOME
            if self.coordinator.logname:
                self._attr_changed_by = self.coordinator.logname
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided or incorrect length")

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Arm alarm off."""
        command = "disarm"
        if code is None:
            code = self._code
        if code and len(code) == self.coordinator.data[self._panel_id]["codelength"]:
            await self.coordinator.triggeralarm(
                command, code=code, panel_id=self._panel_id
            )
            self._attr_state = STATE_ALARM_DISARMED
            if self.coordinator.logname:
                self._attr_changed_by = self.coordinator.logname
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided or incorrect length")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm alarm away."""
        command = "full"
        if code is None:
            code = self._code
        if code and len(code) == self.coordinator.data[self._panel_id]["codelength"]:
            await self.coordinator.triggeralarm(
                command, code=code, panel_id=self._panel_id
            )
            self._attr_state = STATE_ALARM_ARMED_AWAY
            if self.coordinator.logname:
                self._attr_changed_by = self.coordinator.logname
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided or incorrect length")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_changed_by = self.coordinator.data[self._panel_id].get("changed_by")
        if alarm_state := self.coordinator.data[self._panel_id].get("alarmstatus"):
            self._attr_state = ALARM_STATE_TO_HA_STATE[alarm_state]
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity available."""
        return True
