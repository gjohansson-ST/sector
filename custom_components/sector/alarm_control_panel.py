"""Alarm Control Panel for Sector Alarm integration."""
from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Sector Alarm control panel."""
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SectorAlarmControlPanel(coordinator)])


class SectorAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of the Sector Alarm control panel."""

    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.ARM_HOME

    def __init__(self, coordinator: SectorDataUpdateCoordinator) -> None:
        """Initialize the control panel."""
        super().__init__(coordinator)
        self._attr_name = "Sector Alarm Panel"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_alarm_panel"

    @property
    def state(self):
        """Return the state of the device."""
        status = self.coordinator.data.get("panel_status", {})
        status_code = status.get("Status")
        if status_code == 3:
            return STATE_ALARM_ARMED_AWAY
        elif status_code == 2:
            return STATE_ALARM_ARMED_HOME
        elif status_code == 1:
            return STATE_ALARM_DISARMED
        return None

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.actions_manager.arm_system, "full"
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.actions_manager.arm_system, "partial"
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.actions_manager.disarm_system
        )
        if success:
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "sector_alarm_panel")},
            name="Sector Alarm Panel",
            manufacturer="Sector Alarm",
            model="Alarm Panel",
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True
