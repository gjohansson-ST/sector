"""Diagnostics support for Sector."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.sector.const import RUNTIME_DATA
from .coordinator import (
    DeviceRegistry,
    SectorDeviceDataUpdateCoordinator,
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
    coordinators: list[SectorDeviceDataUpdateCoordinator] = entry.runtime_data[
        RUNTIME_DATA.DEVICE_COORDINATORS
    ]

    if len(coordinators) == 0:
        return {}

    device_registry: DeviceRegistry = coordinators[0].data["device_registry"]
    return async_redact_data(
        device_registry.fetch_devices(),
        TO_REDACT,
    )
