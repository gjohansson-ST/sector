"""Sector Alarm integration for Home Assistant."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.sector.endpoints import DataEndpointType

from .client import AsyncTokenProvider, SectorAlarmAPI
from .const import CONF_PANEL_ID, PLATFORMS, RUNTIME_DATA
from .coordinator import (
    DeviceRegistry,
    SectorDeviceDataUpdateCoordinator,
    SectorAlarmConfigEntry,
    SectorPanelInfoDataUpdateCoordinator,
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

    device_registry = DeviceRegistry()
    alarm_panel_device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        sector_api=sector_api,
        panel_info_coordinator=panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name="SectorAlarmPanelDeviceDataUpdateCoordinator",
        mandatory_endpoints={DataEndpointType.PANEL_STATUS},
        update_interval=timedelta(seconds=60),
    )
    smart_plug_device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        sector_api=sector_api,
        panel_info_coordinator=panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name="SectorSmartPlugDeviceDataUpdateCoordinator",
        optional_endpoints={DataEndpointType.SMART_PLUG_STATUS},
        update_interval=timedelta(seconds=60),
    )
    action_device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        sector_api=sector_api,
        panel_info_coordinator=panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name="SectorActionDeviceDataUpdateCoordinator",
        optional_endpoints={
            DataEndpointType.DOOR_AND_WINDOW,
            DataEndpointType.SMOKE_DETECTOR,
            DataEndpointType.LEAKAGE_DETECTOR,
            # DataEndpointType.CAMERAS, <-- broken, do not enable
        },
        update_interval=timedelta(seconds=60),
    )
    sensor_device_coordinators = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        sector_api=sector_api,
        panel_info_coordinator=panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name="SectorSensorDeviceDataUpdateCoordinator",
        optional_endpoints={
            DataEndpointType.HUMIDITY,
            DataEndpointType.TEMPERATURE,
            DataEndpointType.TEMPERATURE_LEGACY,
        },
        update_interval=timedelta(minutes=15),
    )

    await panel_info_coordinator.async_config_entry_first_refresh()
    await alarm_panel_device_coordinator.async_config_entry_first_refresh()
    await smart_plug_device_coordinator.async_config_entry_first_refresh()
    await action_device_coordinator.async_config_entry_first_refresh()
    await sensor_device_coordinators.async_config_entry_first_refresh()

    entry.runtime_data = {
        RUNTIME_DATA.DEVICE_COORDINATORS: [
            alarm_panel_device_coordinator,
            smart_plug_device_coordinator,
            action_device_coordinator,
            sensor_device_coordinators,
        ],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SectorAlarmConfigEntry
) -> bool:
    """Unload a Sector Alarm config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
