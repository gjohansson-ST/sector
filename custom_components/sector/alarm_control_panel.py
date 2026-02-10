"""Alarm Control Panel for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.exceptions import (
    ServiceValidationError,
    HomeAssistantError,
    ConfigEntryAuthFailed,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.sector.client import ApiError, AuthenticationError, LoginError
from custom_components.sector.const import CONF_IGNORE_QUICK_ARM, RUNTIME_DATA

from .coordinator import (
    DeviceRegistry,
    SectorDeviceDataUpdateCoordinator,
    SectorAlarmConfigEntry,
)
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
    entities: list[SectorAlarmControlPanel] = []
    coordinators: list[SectorDeviceDataUpdateCoordinator] = entry.runtime_data[
        RUNTIME_DATA.DEVICE_COORDINATORS
    ]

    for coordinator in coordinators:
        device_registry: DeviceRegistry = coordinator.data.get(
            "device_registry", DeviceRegistry()
        )
        devices: dict[str, dict[str, Any]] = (
            device_registry.fetch_devices_by_coordinator(coordinator.name)
        )
        for serial_no, device in devices.items():
            device_name: str = device["name"]
            device_model = device["model"]
            for entity_model in device.get("entities", {}).keys():
                if entity_model == "Alarm panel":
                    entities.append(
                        SectorAlarmControlPanel(
                            coordinator,
                            entry,
                            serial_no,
                            device_name,
                            device_model,
                            entity_model,
                        )
                    )
                    _LOGGER.debug("Added alarm panel for device %s", serial_no)

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.error("Found no Alarm Control panel to add, this should never happen")


class SectorAlarmControlPanel(
    SectorAlarmBaseEntity[SectorDeviceDataUpdateCoordinator], AlarmControlPanelEntity
):
    """
    Sector Alarm alarm control panel.

    To ensure UI responsiveness during arm/disarm operations, a custom pending state is used.
    This state is set immediately when an arm/disarm command is issued and cleared upon
    successful completion or failure of the operation.
    """

    _attr_name = None
    _attr_code_format = CodeFormat.NUMBER

    def __init__(
        self,
        coordinator: SectorDeviceDataUpdateCoordinator,
        config_entry: SectorAlarmConfigEntry,
        serial_no: str,
        device_name: str,
        device_model: str,
        entity_model: str,
    ) -> None:
        """Initialize the control panel."""
        super().__init__(
            coordinator, serial_no, device_name, device_model, entity_model
        )

        # Safe guard for reload scheduling
        self._reload_scheduled = False
        # Custom pending state to improve UI responsiveness during arm/disarm state changes
        self._pending_state: AlarmControlPanelState | None = None
        self._config_entry = config_entry
        self._ignore_quick_arm = config_entry.options[CONF_IGNORE_QUICK_ARM]
        self._attr_unique_id = f"{self._serial_no}_alarm_panel"
        self._attr_code_arm_required = not self._panel_quick_arm_property

        features = AlarmControlPanelEntityFeature.ARM_AWAY
        if self._panel_partial_arm_property:
            features |= AlarmControlPanelEntityFeature.ARM_HOME

        self._attr_supported_features = features
        _LOGGER.debug(
            "Initialized Sector Alarm Control Panel with ID %s", self._attr_unique_id
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""

        # If there's a pending state, show it instead
        if self._pending_state is not None:
            return self._pending_state

        # Map status code to the appropriate Home Assistant state
        status_code = self._panel_alarm_status_property
        mapped_state = ALARM_STATE_TO_HA_STATE.get(status_code)
        _LOGGER.debug(
            "Alarm status_code: %s, Mapped state: %s", status_code, mapped_state
        )
        return mapped_state

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if not self._is_online():
            raise HomeAssistantError("Failed to arm (full) alarm - alarm is offline")
        if not self._is_valid_arm_code(code):
            raise ServiceValidationError("Invalid code length")

        # Set pending state immediately, before API call, for better UI experience
        self._pending_state = AlarmControlPanelState.ARMING
        self.async_write_ha_state()

        try:
            try:
                await self.coordinator.sector_api.arm_system("full", code=code)
                await self.coordinator.async_request_refresh()
            except LoginError as err:
                raise ConfigEntryAuthFailed from err
            except AuthenticationError as err:
                raise HomeAssistantError(
                    "Failed to arm (full) alarm - authentication failed"
                ) from err
            except ApiError as err:
                raise HomeAssistantError(
                    "Failed to arm (full) alarm - API related error"
                ) from err
            except Exception as err:
                raise HomeAssistantError(
                    "Failed to arm (full) alarm - unexpected error"
                ) from err
        except Exception as err:
            # Clear pending state on failure, resets UI
            self._pending_state = None
            self.async_write_ha_state()
            raise err

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if not self._is_online():
            raise HomeAssistantError("Failed to arm (partial) alarm - alarm is offline")
        if not self._is_valid_arm_code(code):
            raise ServiceValidationError("Invalid code length")

        # Set pending state immediately, before API call, for better UI experience
        self._pending_state = AlarmControlPanelState.ARMING
        self.async_write_ha_state()

        try:
            try:
                await self.coordinator.sector_api.arm_system("partial", code=code)
                await self.coordinator.async_request_refresh()
            except LoginError as err:
                raise ConfigEntryAuthFailed from err
            except AuthenticationError as err:
                raise HomeAssistantError(
                    "Failed to arm (partial) alarm - authentication failed"
                ) from err
            except ApiError as err:
                raise HomeAssistantError(
                    "Failed to arm (partial) alarm - API related error"
                ) from err
            except Exception as err:
                raise HomeAssistantError(
                    "Failed to arm (partial) alarm - unexpected error"
                ) from err
        except Exception as err:
            # Clear pending state on failure, resets UI
            self._pending_state = None
            self.async_write_ha_state()
            raise err

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if not self._is_online():
            raise HomeAssistantError("Failed to disarm alarm - alarm is offline")
        if TYPE_CHECKING:
            assert code is not None
        if not self._is_valid_disarm_code(code):
            raise ServiceValidationError("Invalid code length")

        # Set pending state immediately, before API call, for better UI experience
        self._pending_state = AlarmControlPanelState.DISARMING
        self.async_write_ha_state()

        try:
            try:
                await self.coordinator.sector_api.disarm_system(code=code)
                await self.coordinator.async_request_refresh()
            except LoginError as err:
                raise ConfigEntryAuthFailed from err
            except AuthenticationError as err:
                raise HomeAssistantError(
                    "Failed to disarm alarm - authentication failed"
                ) from err
            except ApiError as err:
                raise HomeAssistantError(
                    "Failed to disarm alarm - API related error"
                ) from err
            except Exception as err:
                raise HomeAssistantError(
                    "Failed to disarm alarm - unexpected error"
                ) from err
        except Exception as err:
            # Clear pending state on failure, resets UI
            self._pending_state = None
            self.async_write_ha_state()
            raise err

    def _is_valid_arm_code(self, code: str | None) -> bool:
        quick_arm = not self._attr_code_arm_required
        if not code and quick_arm:
            return True

        code_length = self._panel_code_length_property
        if code_length == 0:
            return True
        return bool(code and len(code) == code_length)

    def _is_valid_disarm_code(self, code: str | None) -> bool:
        code_length = self._panel_code_length_property
        if code_length == 0:
            return True
        return bool(code and len(code) == code_length)

    def _is_online(self) -> bool:
        return self._panel_online_property

    @callback
    def _handle_coordinator_update(self) -> None:
        # Detect quick arming settings changes from API
        # If detected, force a reload so cards can adapt
        pin_required = not self._panel_quick_arm_property
        if pin_required == self._attr_code_arm_required:
            # Reset custom pending state
            self._pending_state = None
            super()._handle_coordinator_update()
        else:
            if not self._reload_scheduled:
                self._reload_scheduled = True
                _LOGGER.debug(
                    "Quick Arming property changed (%s → %s), reloading entry",
                    self._attr_code_arm_required,
                    pin_required,
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._config_entry.entry_id)
                )

    @property
    def _panel_quick_arm_property(self) -> bool:
        if self._ignore_quick_arm:
            return False

        alarm_panel = self.entity_data or {}
        return alarm_panel.get("panel_quick_arm", False)

    @property
    def _panel_partial_arm_property(self) -> bool:
        alarm_panel = self.entity_data or {}
        return alarm_panel.get("panel_partial_arm", False)

    @property
    def _panel_code_length_property(self) -> int:
        alarm_panel = self.entity_data or {}
        return alarm_panel.get("panel_code_length", 0)

    @property
    def _panel_online_property(self) -> bool:
        alarm_panel = self.entity_data or {}
        sensors: dict[str, Any] = alarm_panel.get("sensors", {})
        return sensors.get("online", False)

    @property
    def _panel_alarm_status_property(self) -> int:
        alarm_panel = self.entity_data or {}
        sensors: dict[str, Any] = alarm_panel.get("sensors", {})
        return sensors.get("alarm_status", 0)
