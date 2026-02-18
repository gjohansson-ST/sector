from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.sector.client import ApiError
from custom_components.sector.const import RUNTIME_DATA
from custom_components.sector.coordinator import DeviceRegistry
from custom_components.sector.switch import async_setup_entry, SectorAlarmSwitch

_PANEL_ID = "1234"
_DEVICE_COORDINATOR_NAME = "device-coordinator"


def _create_mock_coordinator(devices: dict):
    device_registry = DeviceRegistry()
    for d in devices.values():
        device_registry.register_device(d)

    coordinator = MagicMock()
    coordinator.data = {"device_registry": device_registry}
    coordinator.async_request_refresh = AsyncMock()
    coordinator.sector_api = MagicMock()
    coordinator.sector_api.turn_on_smartplug = AsyncMock()
    coordinator.sector_api.turn_off_smartplug = AsyncMock()
    coordinator.name = _DEVICE_COORDINATOR_NAME
    return coordinator


def _create_mock_config_entity(code_format: int) -> MockConfigEntry:
    return MockConfigEntry(
        domain="sector",
        title="Test Panel",
        data={
            "panel_id": _PANEL_ID,
            "username": "abc",
            "password": "xyz",
        },
        entry_id="test123",
    )


def _create_device(serial: str, data: dict[str, Any]) -> dict[str, Any]:
    model: str = data["model"]
    return {
        "name": data["name"],
        "model": model,
        "serial_no": serial,
        "entities": {model: data},
    }


async def test_setup_creates_lock_entity(hass: HomeAssistant):
    # Prepare
    devices = {
        "SERIAL_123": _create_device(
            "SERIAL_123",
            {
                "name": "Entrance Switch",
                "id": "ID_1",
                "sensors": {"plug_status": "On"},
                "model": "Smart Plug",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
        "SERIAL_321": _create_device(
            "SERIAL_321",
            {
                "name": "Bedroom Switch",
                "id": "ID_2",
                "sensors": {"plug_status": "Off"},
                "model": "Smart Plug",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
        "OTHER": _create_device(
            "OTHER",
            {
                "name": "Back Switch",
                "sensors": {"plug_status": "Off"},
                "model": "Dumb Plug",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }

    coordinator = _create_mock_coordinator(devices)
    entry = _create_mock_config_entity(6)
    entry.runtime_data = {RUNTIME_DATA.DEVICE_COORDINATORS: [coordinator]}

    entities = []

    def async_add_entities(new_entities, update_before_add=False):
        entities.extend(new_entities)

    # Act
    await async_setup_entry(hass, entry, async_add_entities)

    # Assert
    assert len(entities) == 2
    entrance_switch: SectorAlarmSwitch = entities[0]
    bedroom_switch: SectorAlarmSwitch = entities[1]

    assert entrance_switch.unique_id == "SERIAL_123_switch"
    assert entrance_switch._serial_no == "SERIAL_123"
    assert entrance_switch._device_name == "Entrance Switch"
    assert entrance_switch._device_model == "Smart Plug"

    assert bedroom_switch.unique_id == "SERIAL_321_switch"
    assert bedroom_switch._serial_no == "SERIAL_321"
    assert bedroom_switch._device_name == "Bedroom Switch"
    assert bedroom_switch._device_model == "Smart Plug"


async def test_is_on_missing_status():
    devices = {
        "ABC123": _create_device(
            "ABC123",
            {
                "name": "Test Plug",
                "id": "plug_1",
                "sensors": {"plug_status": None},
                "model": "Smart Plug",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        device_name="Test Plug",
        device_model="Smart Plug",
        entity_model="Smart Plug",
    )
    assert switch.is_on is False


async def test_is_on_case_insensitive():
    devices = {
        "ABC123": _create_device(
            "ABC123",
            {
                "name": "Test Plug",
                "id": "plug_1",
                "sensors": {"plug_status": "ON"},
                "model": "Smart Plug",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        device_name="Test Plug",
        device_model="Smart Plug",
        entity_model="Smart Plug",
    )
    assert switch.is_on is True


async def test_switch_turn_on_is_optimistic(hass: HomeAssistant):
    # Prepare
    devices = {
        "ABC123": _create_device(
            "ABC123",
            {
                "name": "Test Plug",
                "id": "plug_1",
                "sensors": {"plug_status": "Off"},
                "model": "Smart Plug",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        device_name="Test Plug",
        device_model="Smart Plug",
        entity_model="Smart Plug",
    )

    switch.async_write_ha_state = Mock()

    # Act
    await switch.async_turn_on()

    # Assert
    coordinator.sector_api.turn_on_smartplug.assert_awaited_once_with("plug_1")
    assert switch.is_on is True


async def test_switch_turn_off_is_optimistic(hass: HomeAssistant):
    # Prepare
    devices = {
        "ABC123": _create_device(
            "ABC123",
            {
                "name": "Test Plug",
                "id": "plug_1",
                "sensors": {"plug_status": "On"},
                "model": "Smart Plug",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        device_name="Test Plug",
        device_model="Smart Plug",
        entity_model="Smart Plug",
    )

    switch.async_write_ha_state = Mock()

    # Act
    await switch.async_turn_off()

    # Assert
    coordinator.sector_api.turn_off_smartplug.assert_awaited_once_with("plug_1")
    assert switch.is_on is False


async def test_coordinator_update_reconciles_state(hass):
    # prepare
    devices = {
        "ABC123": _create_device(
            "ABC123",
            {
                "name": "Test Plug",
                "id": "plug_1",
                "sensors": {"plug_status": "On"},
                "model": "Smart Plug",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "last_updated": "",
            },
        ),
    }
    coordinator = _create_mock_coordinator(devices)

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        device_name="Test Plug",
        device_model="Smart Plug",
        entity_model="Smart Plug",
    )
    switch.async_write_ha_state = Mock()

    # Act
    switch._attr_is_on = False
    switch._handle_coordinator_update()

    # Assert
    assert switch._attr_is_on is None
    assert switch.is_on is True


async def test_turn_on_api_error_raises(hass: HomeAssistant):
    # Prepare
    coordinator = _create_mock_coordinator({})
    coordinator.sector_api.turn_on_smartplug = AsyncMock(side_effect=ApiError("boom"))

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        device_name="Test Plug",
        device_model="Smart Plug",
        entity_model="Smart Plug",
    )

    switch.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await switch.async_turn_on()


async def test_turn_off_api_error_raises(hass):
    # Prepare
    coordinator = _create_mock_coordinator({})
    coordinator.sector_api.turn_off_smartplug = AsyncMock(side_effect=ApiError("boom"))

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        device_name="Test Plug",
        device_model="Smart Plug",
        entity_model="Smart Plug",
    )

    switch.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await switch.async_turn_off()
