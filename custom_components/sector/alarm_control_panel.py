"""Alarm Control Panel for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ServiceValidationError,
    HomeAssistantError,
    ConfigEntryAuthFailed,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.sector.client import ApiError, AuthenticationError, LoginError

from .const import CONF_CODE_FORMAT
from .coordinator import (
    SectorActionDataUpdateCoordinator,
    SectorAlarmConfigEntry,
    SectorCoordinatorType,
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
    coordinator = cast(
        SectorActionDataUpdateCoordinator,
        entry.runtime_data[SectorCoordinatorType.ACTION_DEVICES],
    )
    async_add_entities([SectorAlarmControlPanel(coordinator)])


class SectorAlarmControlPanel(
    SectorAlarmBaseEntity[SectorActionDataUpdateCoordinator], AlarmControlPanelEntity
):
    """Representation of the Sector Alarm control panel."""

    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )
    _attr_code_arm_required = True
    _attr_code_format = CodeFormat.NUMBER

    def __init__(self, coordinator: SectorActionDataUpdateCoordinator) -> None:
        """Initialize the control panel."""
        super().__init__(
            coordinator,
            coordinator.panel_id,
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
        devices: dict[str, Any] = self.coordinator.data.get("devices", {})
        alarm_panel: dict[str, Any] = devices.get("alarm_panel", {})
        sensors: dict[str, Any] = alarm_panel.get("sensors", {})

        status_code = sensors.get("alarm_status", 0)
        online_status = sensors.get("online", False)

        if not online_status:
            return None

        # Map status code to the appropriate Home Assistant state
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

        try:
            await self.coordinator.api.arm_system("full", code=code)
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

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if TYPE_CHECKING:
            assert code is not None
        if not self._is_valid_code(code):
            raise ServiceValidationError("Invalid code length")

        try:
            await self.coordinator.api.arm_system("partial", code=code)
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

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if TYPE_CHECKING:
            assert code is not None
        if not self._is_valid_code(code):
            raise ServiceValidationError("Invalid code length")

        try:
            await self.coordinator.api.disarm_system(code=code)
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

    def _is_valid_code(self, code: str) -> bool:
        code_format = self.coordinator.sector_config_entry.options[CONF_CODE_FORMAT]
        return bool(code and len(code) == code_format)
