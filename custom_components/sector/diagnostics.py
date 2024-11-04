"""Diagnostics support for Sector Alarm integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import SectorAlarmConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SectorAlarmConfigEntry
):
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "data": coordinator.data,
        "entry": entry.as_dict(),
    }
