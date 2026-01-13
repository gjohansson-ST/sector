"""Diagnostics support for Sector."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .coordinator import (
    SectorCoordinatorType,
)

TO_REDACT = {
    "AuthorizationToken",
    "CellPhone",
    "CustomerNo",
    "DefaultPanelId",
    "DeviceId",
    "FirstName",
    "Id",
    "Key",
    "LastName",
    "LegalOwnerName",
    "PanelId",
    "PersonId",
    "RemoteControlSerialNumber",
    "Serial",
    "SerialNo",
    "SerialString",
    "User",
    "UserName",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Sensibo config entry."""
    coordinator_action: DataUpdateCoordinator = entry.runtime_data[
        SectorCoordinatorType.ACTION_DEVICES
    ]
    coordinator_sensor: DataUpdateCoordinator = entry.runtime_data[
        SectorCoordinatorType.SENSOR_DEVICES
    ]
    return async_redact_data(
        {
            SectorCoordinatorType.ACTION_DEVICES.name: coordinator_action.data,
            SectorCoordinatorType.SENSOR_DEVICES.name: coordinator_sensor.data,
        },
        TO_REDACT,
    )
