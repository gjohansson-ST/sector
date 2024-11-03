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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
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
    async_add_entities([SectorAlarmPanel(coordinator, key) for key in coordinator.data])


class SectorAlarmPanel(
    CoordinatorEntity[SectorDataUpdateCoordinator], AlarmControlPanelEntity
):
    """Sector Alarm Panel."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        panel_id: str,
    ) -> None:
        """Initialize the Alarm panel."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        panel_data = self.coordinator.data[panel_id]
        self._serial_id = panel_data.get("serial_id")
        self._displayname: str = panel_data["name"]
        self._attr_unique_id = f"sa_panel_{self._serial_id}"
        self._attr_changed_by = panel_data["changed_by"]
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
        )
        self._attr_code_arm_required = True
        self._attr_code_format = CodeFormat.NUMBER
        self._attr_state = ALARM_STATE_TO_HA_STATE[
            panel_data["alarmstatus"]
        ]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._serial_id)},
            name=f"Sector Alarmpanel {self._serial_id}",
            manufacturer="Sector Alarm",
            model="Alarmpanel",
            sw_version="master",
            via_device=(DOMAIN, self._serial_id),
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
        """Disarm the alarm."""
        command = "disarm"
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
        panel_data = self.coordinator.data[self._panel_id]
        self._attr_changed_by = panel_data.get("changed_by")
        if alarm_state := panel_data.get("alarmstatus"):
            self._attr_state = ALARM_STATE_TO_HA_STATE[alarm_state]
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return entity available."""
        return True
