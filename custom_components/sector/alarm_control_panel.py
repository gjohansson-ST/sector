"""Alarm Control Panel for Sector Alarm integration."""

from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import (
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)

ALARM_STATE_TO_HA_STATE = {
    3: AlarmControlPanelState.ARMED_AWAY,
    2: AlarmControlPanelState.ARMED_HOME,
    1: AlarmControlPanelState.DISARMED,
    0: STATE_UNKNOWN,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Sector Alarm control panel."""
    coordinator = entry.runtime_data
    async_add_entities([SectorAlarmControlPanel(coordinator)])


class SectorAlarmControlPanel(SectorAlarmBaseEntity, AlarmControlPanelEntity):
    """Representation of the Sector Alarm control panel."""

    _attr_name = "Sector Alarm Control Panel"
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )
    _attr_code_arm_required = True
    _attr_code_format = CodeFormat.NUMBER

    def __init__(self, coordinator: SectorDataUpdateCoordinator) -> None:
        """Initialize the control panel."""
        panel_status = coordinator.data.get("panel_status", {})
        serial_no = panel_status.get("SerialNo") or coordinator.config_entry.data.get("panel_id")
        super().__init__(coordinator, serial_no, {"name": "Sector Alarm Panel"})

        self._attr_unique_id = f"{self._serial_no}_alarm_panel"
        _LOGGER.debug("Initialized Sector Alarm Control Panel with ID %s", self._attr_unique_id)

    @property
    def alarm_state(self):
        """Return the state of the device."""
        status = self.coordinator.data.get("panel_status", {})
        if not status.get("IsOnline", True):
            return None

        # Map status code to the appropriate Home Assistant state
        status_code = status.get("Status", 0)
        mapped_state = ALARM_STATE_TO_HA_STATE.get(status_code)
        _LOGGER.debug(
            "Alarm status_code: %s, Mapped state: %s", status_code, mapped_state
        )
        return mapped_state

    async def async_alarm_arm_away(self, code: str | None = None):
        """Send arm away command."""
        if not self._is_valid_code(code):
            raise ServiceValidationError("Invalid code length")
        _LOGGER.debug("Arming away with code: %s", code)
        if await self.coordinator.api.arm_system("total", code=code):
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_home(self, code: str | None = None):
        """Send arm home command."""
        if not self._is_valid_code(code):
            raise ServiceValidationError("Invalid code length")
        _LOGGER.debug("Arming home with code: %s", code)
        if await self.coordinator.api.arm_system("partial", code=code):
            await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code: str | None = None):
        """Send disarm command."""
        if not self._is_valid_code(code):
            raise ServiceValidationError("Invalid code length")
        _LOGGER.debug("Disarming with code: %s", code)
        if await self.coordinator.api.disarm_system(code=code):
            await self.coordinator.async_request_refresh()

    def _is_valid_code(self, code: str) -> bool:
        return bool(code and len(code) == self.coordinator.code_format)
