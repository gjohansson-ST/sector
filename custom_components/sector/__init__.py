"""Sector Alarm integration for Home Assistant."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CODE_FORMAT,
    CONF_LOCK,
    CONF_PASSWORD,
    CONF_TEMP,
    CONF_USERID,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    UPDATE_INTERVAL,
)
from .coordinator import SectorAlarmHub


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:

        new_options = {**entry.options}
        new_options[UPDATE_INTERVAL] = 60
        new_data = {**entry.data}
        new_data[CONF_CODE_FORMAT] = 6

        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options
        )

        entry.version = 2

    LOGGER.info("Migration to version %s successful", entry.version)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sector Alarm as config entry."""

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

        hass.data[DOMAIN][entry.entry_id]["last_updated"] = datetime.utcnow()
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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "last_updated": datetime.utcnow() - timedelta(hours=2),
    }

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "sa_hub_" + str(api.alarm_id))},
        manufacturer="Sector Alarm",
        name="Sector Hub",
        model="Hub",
        sw_version="master",
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    controller: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    controller.update_interval = timedelta(seconds=entry.options.get(UPDATE_INTERVAL))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return unload_ok
    return False
