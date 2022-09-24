"""Sector Alarm integration for Home Assistant."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CODE_FORMAT,
    CONF_TEMP,
    CONF_USERID,
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

        new_data = {**entry.data, CONF_CODE_FORMAT: 6}
        new_options = {**entry.options, UPDATE_INTERVAL: 60}

        if hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options
        ):
            entry.version = 2

    if entry.version == 2:
        username = (
            entry.data[CONF_USERNAME]
            if entry.data.get(CONF_USERNAME)
            else entry.data[CONF_USERID]
        )
        new_data2 = {
            CONF_USERNAME: username,
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
            CONF_TEMP: entry.data[CONF_TEMP],
        }
        new_options2 = {
            UPDATE_INTERVAL: entry.options.get(UPDATE_INTERVAL),
            CONF_CODE: entry.options.get(CONF_CODE),
            CONF_CODE_FORMAT: entry.options.get(CONF_CODE_FORMAT),
        }
        if new_options2[CONF_CODE] == "":
            new_options2[CONF_CODE] = None
        if success := hass.config_entries.async_update_entry(
            entry,
            data=new_data2,
            options=new_options2,
            title=username,
            unique_id=username,
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

    for key in coordinator.data:
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"sa_hub_{key}")},
            manufacturer="Sector Alarm",
            name="Sector Hub",
            model="Hub",
            sw_version="master",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    controller: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    controller.update_interval = timedelta(
        seconds=entry.options.get(UPDATE_INTERVAL, 60)
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return unload_ok
    return False
