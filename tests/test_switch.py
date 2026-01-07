from unittest.mock import AsyncMock, MagicMock, Mock

from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import HomeAssistant
import pytest

from custom_components.sector.client import ApiError
from custom_components.sector.switch import SectorAlarmSwitch


async def test_switch_turn_on_is_optimistic(hass: HomeAssistant):
    # Prepare
    coordinator = MagicMock()
    coordinator.api.turn_on_smartplug = AsyncMock()
    coordinator.data = {"devices": {"ABC123": {"sensors": {"plug_status": "Off"}}}}

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
    coordinator.api.turn_on_smartplug.assert_awaited_once_with("plug_1")
    assert switch.is_on is True

async def test_switch_turn_off_is_optimistic(hass: HomeAssistant):
    # Prepare
    coordinator = MagicMock()
    coordinator.api.turn_off_smartplug = AsyncMock()
    coordinator.data = {"devices": {"ABC123": {"sensors": {"plug_status": "On"}}}}

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
    coordinator.api.turn_off_smartplug.assert_awaited_once_with("plug_1")
    assert switch.is_on is False

def test_coordinator_update_reconciles_state(hass):
    coordinator = MagicMock()
    coordinator.data = {"devices": {"ABC123": {"sensors": {"plug_status": "On"}}}}

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
    coordinator = MagicMock()
    coordinator.api.turn_on_smartplug = AsyncMock(side_effect=ApiError("boom"))
    coordinator.data = {"devices": {}}

    switch = SectorAlarmSwitch(
        coordinator=coordinator,
        plug_id="plug_1",
        serial_no="ABC123",
        name="Test Plug",
        model="Smart Plug",
    )

    # Act & Assert
    with pytest.raises(HomeAssistantError):
        await switch.async_turn_on()

async def test_turn_off_api_error_raises(hass):
    # Prepare
    coordinator = MagicMock()
    coordinator.api.turn_off_smartplug = AsyncMock(side_effect=ApiError("boom"))
    coordinator.data = {"devices": {}}

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