"""Alarm Control Panel for Sector Alarm integration."""
from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Sector Alarm control panel."""
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SectorAlarmControlPanel(coordinator)])


class SectorAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of the Sector Alarm control panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.DISARM
    )

    def __init__(self, coordinator: SectorDataUpdateCoordinator) -> None:
        """Initialize the control panel."""
        super().__init__(coordinator)
        panel_status = coordinator.data.get("panel_status", {})
        self._serial_no = panel_status.get("SerialNo") or coordinator.entry.data.get("panel_id")
        self._attr_unique_id = f"{self._serial_no}_alarm_panel"
        self._attr_name = "Sector Alarm Panel"
        LOGGER.debug(f"Initialized alarm control panel with unique_id: {self._attr_unique_id}")

    @property
    def state(self):
        """Return the state of the device."""
        status = self.coordinator.data.get("panel_status", {})
        status_code = status.get("ArmedStatus")
        if status_code == "Disarmed":
            return STATE_ALARM_DISARMED
        elif status_code == "PartiallyArmed":
            return STATE_ALARM_ARMED_HOME
        elif status_code == "Armed":
            return STATE_ALARM_ARMED_AWAY
        return None

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
