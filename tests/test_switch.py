from unittest.mock import AsyncMock, MagicMock, Mock

from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)


from custom_components.sector.client import ApiError
from custom_components.sector.coordinator import SectorCoordinatorType
from custom_components.sector.switch import async_setup_entry, SectorAlarmSwitch

_PANEL_ID = "1234"


def _create_mock_coordinator(devices: dict):
    coordinator = MagicMock()
    coordinator.data = {"devices": devices}
    coordinator.async_request_refresh = AsyncMock()
    coordinator.sector_api = MagicMock()
    coordinator.sector_api.turn_on_smartplug = AsyncMock()
    coordinator.sector_api.turn_off_smartplug = AsyncMock()
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


async def test_setup_creates_lock_entity(hass: HomeAssistant):
    # Prepare
    devices = {
        "SERIAL_123": {
            "name": "Entrance Switch",
            "serial_no": "SERIAL_123",
            "id": "ID_1",
            "sensors": {"plug_status": "On"},
            "model": "Smart Plug",
            "last_updated": "",
        },
        "SERIAL_321": {
            "name": "Bedroom Switch",
            "serial_no": "SERIAL_321",
            "id": "ID_2",
            "sensors": {"plug_status": "Off"},
            "model": "Smart Plug",
            "last_updated": "",
        },
        "OTHER": {
            "name": "Back Switch",
            "serial_no": "SERIAL_321",
            "sensors": {"plug_status": "Off"},
            "model": "Dumb Plug",
            "last_updated": "",
        },
    }

    coordinator = _create_mock_coordinator(devices)
    entry = _create_mock_config_entity(6)
    entry.runtime_data = {SectorCoordinatorType.ACTION_DEVICES: coordinator}

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
    assert entrance_switch._device_id == "SERIAL_123"
    assert entrance_switch.device_name == "Entrance Switch"
    assert entrance_switch.device_model == "Smart Plug"

    assert bedroom_switch.unique_id == "SERIAL_321_switch"
    assert bedroom_switch._device_id == "SERIAL_321"
    assert bedroom_switch.device_name == "Bedroom Switch"
    assert bedroom_switch.device_model == "Smart Plug"

async def test_is_on_missing_status():
    coordinator = _create_mock_coordinator(
        {"ABC123": {"sensors": {"plug_status": None}}}
    )

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        name="Test Plug",
        model="Smart Plug",
    )
    assert switch.is_on is False

async def test_is_on_case_insensitive():
    coordinator = _create_mock_coordinator(
        {"ABC123": {"sensors": {"plug_status": "ON"}}}
    )

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        name="Test Plug",
        model="Smart Plug",
    )
    assert switch.is_on is True

async def test_switch_turn_on_is_optimistic(hass: HomeAssistant):
    # Prepare
    coordinator = _create_mock_coordinator(
        {"ABC123": {"sensors": {"plug_status": "Off"}}}
    )

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        name="Test Plug",
        model="Smart Plug",
    )

    switch.async_write_ha_state = Mock()

    # Act
    await switch.async_turn_on()

    # Assert
    coordinator.sector_api.turn_on_smartplug.assert_awaited_once_with("plug_1")
    assert switch.is_on is True


async def test_switch_turn_off_is_optimistic(hass: HomeAssistant):
    # Prepare
    coordinator = _create_mock_coordinator(
        {"ABC123": {"sensors": {"plug_status": "On"}}}
    )

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        name="Test Plug",
        model="Smart Plug",
    )

    switch.async_write_ha_state = Mock()

    # Act
    await switch.async_turn_off()

    # Assert
    coordinator.sector_api.turn_off_smartplug.assert_awaited_once_with("plug_1")
    assert switch.is_on is False

async def test_coordinator_update_reconciles_state(hass):
    coordinator = _create_mock_coordinator(
        {"ABC123": {"sensors": {"plug_status": "On"}}}
    )

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        name="Test Plug",
        model="Smart Plug",
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
        name="Test Plug",
        model="Smart Plug",
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
        name="Test Plug",
        model="Smart Plug",
    )

    switch.async_write_ha_state = Mock()

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await switch.async_turn_off()
