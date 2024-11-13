"""Diagnostics support for Sector."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator

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
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return async_redact_data(coordinator.data, TO_REDACT)
