"""Sector Alarm integration for Home Assistant."""

from __future__ import annotations

import logging
from math import e

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import AsyncTokenProvider, SectorAlarmAPI
from .const import CONF_PANEL_ID, PLATFORMS
from .coordinator import (
    SectorActionDataUpdateCoordinator,
    SectorAlarmConfigEntry,
    SectorCoordinatorType,
    SectorPanelInfoDataUpdateCoordinator,
    SectorSensorDataUpdateCoordinator,
)

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
            password=entry.data[CONF_PASSWORD],
        ),
    )

    panel_info_coordinator = SectorPanelInfoDataUpdateCoordinator(
        hass, entry, sector_api
    )
    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, entry, sector_api, panel_info_coordinator
    )
    sensor_coordinator = SectorSensorDataUpdateCoordinator(
        hass, entry, sector_api, panel_info_coordinator
    )

    await panel_info_coordinator.async_config_entry_first_refresh()
    await action_coordinator.async_config_entry_first_refresh()
    await sensor_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = {
        SectorCoordinatorType.PANEL_INFO: panel_info_coordinator,
        SectorCoordinatorType.ACTION_DEVICES: action_coordinator,
        SectorCoordinatorType.SENSOR_DEVICES: sensor_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SectorAlarmConfigEntry
) -> bool:
    """Unload a Sector Alarm config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
