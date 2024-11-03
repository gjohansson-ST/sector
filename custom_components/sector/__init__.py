"""Sector Alarm integration for Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_CODE_FORMAT,
    CONF_TEMP,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    UPDATE_INTERVAL,
)
from .coordinator import SectorDataUpdateCoordinator


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        entry.version = 2

    if entry.version == 2:
        new_data2 = {
            CONF_USERNAME: entry.data[CONF_USERNAME],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
            CONF_TEMP: entry.data[CONF_TEMP],
        }
        new_options2 = {
            CONF_CODE_FORMAT: entry.options.get(CONF_CODE_FORMAT, 6),
        }
        if success := hass.config_entries.async_update_entry(
            entry,
            data=new_data2,
            options=new_options2,
            title=entry.data[CONF_USERNAME],
            unique_id=entry.data[CONF_USERNAME],
        ):
            entry.version = 3
            LOGGER.info("Migration to version %s successful", entry.version)
            return success
    return False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sector Alarm as config entry."""

    coordinator = SectorDataUpdateCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    for key, panel_data in coordinator.data.items():
        serial_id = panel_data.get("serial_id")
        if not serial_id:
            LOGGER.error("No serial_id found for panel %s, skipping device registration.", key)
            continue

        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, serial_id)},
            manufacturer="Sector Alarm",
            name=panel_data["name"],
            model="Hub",
            sw_version="master",
        )

    if entry.options.get(UPDATE_INTERVAL):
        new_options = entry.options.copy()
        new_options.pop(UPDATE_INTERVAL)
        hass.config_entries.async_update_entry(entry, options=new_options)
    if not entry.options.get(CONF_CODE_FORMAT):
        new_options = entry.options.copy()
        new_options[CONF_CODE_FORMAT] = 6
        hass.config_entries.async_update_entry(entry, options=new_options)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return unload_ok
    return False
