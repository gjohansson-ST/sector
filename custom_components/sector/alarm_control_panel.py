"""Alarm Control Panel for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CODE_FORMAT, CONF_PANEL_ID
from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)

ALARM_STATE_TO_HA_STATE = {
    3: AlarmControlPanelState.ARMED_AWAY,
    2: AlarmControlPanelState.ARMED_HOME,
    1: AlarmControlPanelState.DISARMED,
    0: None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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
        super().__init__(
            coordinator,
            coordinator.config_entry.data[CONF_PANEL_ID],
            "Sector Alarm Panel",
            "Alarm panel",
        )

        self._attr_unique_id = f"{self._serial_no}_alarm_panel"
        _LOGGER.debug(
            "Initialized Sector Alarm Control Panel with ID %s", self._attr_unique_id
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
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

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if TYPE_CHECKING:
            assert code is not None
        if not self._is_valid_code(code):
            raise ServiceValidationError("Invalid code length")
        _LOGGER.debug("Arming away with code: %s", code)
        if await self.coordinator.api.arm_system("total", code=code):
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if TYPE_CHECKING:
            assert code is not None
        if not self._is_valid_code(code):
            raise ServiceValidationError("Invalid code length")
        _LOGGER.debug("Arming home with code: %s", code)
        if await self.coordinator.api.arm_system("partial", code=code):
            await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if TYPE_CHECKING:
            assert code is not None
        if not self._is_valid_code(code):
            raise ServiceValidationError("Invalid code length")
        _LOGGER.debug("Disarming with code: %s", code)
        if await self.coordinator.api.disarm_system(code=code):
            await self.coordinator.async_request_refresh()

    def _is_valid_code(self, code: str) -> bool:
        code_format = self.coordinator.config_entry.options[CONF_CODE_FORMAT]
        return bool(code and len(code) == code_format)
