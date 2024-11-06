"""Alarm Control Panel for Sector Alarm integration."""

from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)

ALARM_STATE_TO_HA_STATE = {
    3: STATE_ALARM_ARMED_AWAY,
    2: STATE_ALARM_ARMED_HOME,
    1: STATE_ALARM_DISARMED,
    0: STATE_ALARM_PENDING,
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

    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )
    _attr_code_arm_required = True
    _attr_code_format = CodeFormat.NUMBER

    def __init__(self, coordinator: SectorDataUpdateCoordinator) -> None:
        """Initialize the control panel."""
        panel_status = coordinator.data.get("panel_status", {})
        serial_no = panel_status.get("SerialNo") or coordinator.config_entry.data.get(
            "panel_id"
        )
        super().__init__(
            coordinator, serial_no, {"name": "Sector Alarm Panel"}, "Alarm Panel"
        )

        self._attr_unique_id = f"{self._serial_no}_alarm_panel"
        _LOGGER.debug(
            "Code requirement flags set for %s: arm_required=True",
            self._attr_unique_id,
        )

    @property
    def state(self):
        """Return the state of the device."""
        status = self.coordinator.data.get("panel_status", {})
        if status.get("IsOnline", False) is False:
            return "offline"
        # Get the status code from the panel data
        status_code = status.get("Status", 0)
        # Map the status code to the appropriate Home Assistant state
        mapped_state = ALARM_STATE_TO_HA_STATE.get(status_code, STATE_ALARM_PENDING)
        _LOGGER.debug(
            "Alarm status_code: %s, Mapped state: %s", status_code, mapped_state
        )
        return mapped_state

    async def async_alarm_arm_away(self, code: str | None = None):
        """Send arm away command."""
        is_valid = self._is_valid_code(code)
        _LOGGER.debug("Arm away requested. Code: %s, Is valid: %s", code, is_valid)
        if not is_valid:
            raise ServiceValidationError("Provided code not of the correct length")
        success = await self.coordinator.api.arm_system("total", code=code)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_home(self, code: str | None = None):
        """Send arm home command."""
        is_valid = self._is_valid_code(code)
        _LOGGER.debug("Arm home requested. Code: %s, Is valid: %s", code, is_valid)
        if not is_valid:
            raise ServiceValidationError("Provided code not of the correct length")
        success = await self.coordinator.api.arm_system("partial", code=code)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code: str | None = None):
        """Send disarm command."""
        is_valid = self._is_valid_code(code)
        _LOGGER.debug("Disarm requested. Code: %s, Is valid: %s", code, is_valid)
        if not is_valid:
            raise ServiceValidationError("Provided code not of the correct length")
        success = await self.coordinator.api.disarm_system(code=code)
        if success:
            await self.coordinator.async_request_refresh()

    def _is_valid_code(self, code: str) -> bool:
        expected_length = self.coordinator.code_format
        if not code:
            return False
        is_valid = bool(code and len(code) == expected_length)
        _LOGGER.debug(
            "Validating code. Received code: %s, Expected length: %d, Is valid: %s",
            code,
            expected_length,
            is_valid,
        )
        return is_valid
