"""Sector Alarm integration for Home Assistant."""
from __future__ import annotations

from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CODE,
    CONF_CODE_FORMAT,
    CONF_LOCK,
    CONF_PASSWORD,
    CONF_TEMP,
    CONF_USERID,
    DOMAIN,
    LOGGER,
    MIN_SCAN_INTERVAL,
    PLATFORMS,
    UPDATE_INTERVAL,
)
from .coordinator import SectorAlarmHub

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERID): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_CODE, default=""): cv.string,
                vol.Optional(CONF_CODE_FORMAT, default=6): cv.positive_int,
                vol.Optional(CONF_TEMP, default=True): cv.boolean,
                vol.Optional(CONF_LOCK, default=True): cv.boolean,
                vol.Required(UPDATE_INTERVAL, default=60): vol.All(
                    cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:

        new = {**entry.options}
        new[UPDATE_INTERVAL] = 60

        entry.options = {**new}

        new2 = {**entry.data}
        new2[CONF_CODE_FORMAT] = 6

        entry.data = {**new2}

        entry.version = 2

    LOGGER.info("Migration to version %s successful", entry.version)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sector Alarm as config entry."""
    hass.data.setdefault(DOMAIN, {})

    if UPDATE_INTERVAL not in entry.options:
        LOGGER.info(
            "Set 60 seconds as update_interval as default. Adjust in options for integration"
        )
        hass.config_entries.async_update_entry(entry, options={UPDATE_INTERVAL: 60})

    websession = async_get_clientsession(hass)

    api = SectorAlarmHub(
        entry.data[CONF_LOCK],
        entry.data[CONF_TEMP],
        entry.data[CONF_USERID],
        entry.data[CONF_PASSWORD],
        entry.options.get(UPDATE_INTERVAL, 60),
        websession=websession,
    )

    async def async_update_data() -> None:
        """Fetch data from api."""

        now = datetime.utcnow()
        hass.data[DOMAIN][entry.entry_id]["last_updated"] = now
        LOGGER.debug("UPDATE_INTERVAL = %s", {entry.options[UPDATE_INTERVAL]})
        LOGGER.debug(
            "last updated = %s", hass.data[DOMAIN][entry.entry_id]["last_updated"]
        )
        await api.fetch_info()

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="sector_api",
        update_method=async_update_data,
        update_interval=timedelta(seconds=entry.options[UPDATE_INTERVAL]),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "last_updated": datetime.utcnow() - timedelta(hours=2),
        "data_listener": [entry.add_update_listener(update_listener)],
    }

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "sa_hub_" + str(api.alarm_id))},
        manufacturer="Sector Alarm",
        name="Sector Hub",
        model="Hub",
        sw_version="master",
    )

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    controller: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    controller.update_interval = timedelta(seconds=entry.options.get(UPDATE_INTERVAL))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    for listener in hass.data[DOMAIN][entry.entry_id]["data_listener"]:
        listener()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    title = entry.title
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        LOGGER.debug("Unloaded entry for %s", title)
        return unload_ok
    return False
