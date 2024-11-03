"""Diagnostics support for Sector Alarm integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
):
    """Return diagnostics for a config entry."""
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    diagnostics_data = {
        "config_entry": {
            "title": config_entry.title,
            "data": {
                "email": config_entry.data.get("email"),
                "panel_id": config_entry.data.get("panel_id"),
            },
        },
        "data": coordinator.data,
    }
    return diagnostics_data
