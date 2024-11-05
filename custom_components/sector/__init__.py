"""Sector Alarm integration for Home Assistant."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS, DOMAIN
from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: SectorAlarmConfigEntry) -> bool:
    """Set up Sector Alarm from a config entry."""
    coordinator = SectorDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_listener(
    hass: HomeAssistant, entry: SectorAlarmConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: SectorAlarmConfigEntry
) -> bool:
    """Unload a Sector Alarm config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
