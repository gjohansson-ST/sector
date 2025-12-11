"""Sector Alarm integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import AsyncTokenProvider, SectorAlarmAPI
from .const import PLATFORMS, CONF_PANEL_ID
from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SectorAlarmConfigEntry) -> bool:
    """Set up Sector Alarm from a config entry."""
    client_session = async_get_clientsession(hass)
    sector_api = SectorAlarmAPI(
        client_session=client_session,
        panel_id=entry.data[CONF_PANEL_ID],
        token_provider=AsyncTokenProvider(
            client_session=client_session,
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD]
        )
    )

    coordinator = SectorDataUpdateCoordinator(hass, entry, sector_api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

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


async def async_migrate_entry(
        hass: HomeAssistant, entry: SectorAlarmConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version < 4:
        _LOGGER.error(
            "Migration is not supported, please remove the integration and add it again"
        )
        return False

    return True
