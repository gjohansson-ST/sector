"""Alarm Control Panel for Sector Alarm integration."""

from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator

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


class SectorAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of the Sector Alarm control panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )

    def __init__(self, coordinator: SectorDataUpdateCoordinator) -> None:
        """Initialize the control panel."""
        super().__init__(coordinator)
        panel_status = coordinator.data.get("panel_status", {})
        self._serial_no = panel_status.get("SerialNo") or coordinator.entry.data.get(
            "panel_id"
        )
        self._attr_unique_id = f"{self._serial_no}_alarm_panel"
        self._attr_name = "Sector Alarm Panel"
        _LOGGER.debug(
            "Initialized alarm control panel with unique_id: %s", self._attr_unique_id
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

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        success = await self.coordinator.api.arm_system("total")
        if success:
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        success = await self.coordinator.api.arm_system("partial")
        if success:
            await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        success = await self.coordinator.api.disarm_system()
        if success:
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name="Sector Alarm Panel",
            manufacturer="Sector Alarm",
            model="Alarm Panel",
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "serial_number": self._serial_no,
        }
