from typing import Any
from unittest.mock import AsyncMock
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.sector.api_model import Lock, PanelInfo, SmartPlug, Temperature
from custom_components.sector.client import APIResponse, LoginError
from custom_components.sector.coordinator import SectorPanelInfoDataUpdateCoordinator

_PANEL_ID = "1234"


def _create_mock_config_entity() -> MockConfigEntry:
    return MockConfigEntry(
        domain="sector",
        title="Test Panel",
        data={"panel_id": _PANEL_ID, "username": "abc", "password": "xyz"},
        entry_id="test123",
    )


async def test_async_update_data_should_fetch_PanelInfo(
    hass: HomeAssistant,
):
    # Prepare
    lock: Lock = {
        "AutoLockEnabled": False,
        "Label": "Front Door",
        "Serial": "LOCK123",
        "SerialNo": "LOCK123",
        "Status": "lock",
        "BatteryLow": False,
        "LowBattery": False,
    }
    smart_plug: SmartPlug = {
        "Id": "plug_1",
        "Label": "Living Room Plug",
        "Serial": "PLUG123",
        "SerialNo": "PLUG123",
        "Status": "On",
    }
    temperature: Temperature = {
        "Label": "Living Room",
        "Serial": "TEMP123",
        "SerialNo": "TEMP123",
        "Temperature": "22.5",
    }
    panel_info: PanelInfo = {
        "PanelId": "1234",
        "Locks": [lock],
        "Smartplugs": [smart_plug],
        "Temperatures": [temperature],
    }

    mock_api = AsyncMock()
    mock_api.get_panel_info.return_value = APIResponse(
        response_code=200, response_is_json=True, response_data=panel_info
    )

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorPanelInfoDataUpdateCoordinator(hass, mock_entity, mock_api)

    # Act
    data: dict[str, Any] = await coordinator._async_update_data()

    # Assert
    assert data["panel_info"] == panel_info


async def test_async_update_data_should_raise_UpdateFailed_exception_on_http_failure(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()
    mock_api.get_panel_info.return_value = APIResponse(
        response_code=504, response_is_json=True, response_data="some-response"
    )

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorPanelInfoDataUpdateCoordinator(hass, mock_entity, mock_api)

    # Act & Assert
    with pytest.raises(
        UpdateFailed,
        match=f"Failed to retrieve panel information for panel '{_PANEL_ID}' \\(HTTP 504 - some-response\\)",
    ):
        await coordinator._async_update_data()


async def test_async_update_data_should_raise_UpdateFailed_exception_on_non_json_response(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()
    mock_api.get_panel_info.return_value = APIResponse(
        response_code=200, response_is_json=False, response_data="some-response"
    )

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorPanelInfoDataUpdateCoordinator(hass, mock_entity, mock_api)

    # Act & Assert
    with pytest.raises(
        UpdateFailed,
        match=f"Failed to retrieve panel information for panel '{_PANEL_ID}' \\(response data is not JSON 'some-response'\\)",
    ):
        await coordinator._async_update_data()


async def test_async_update_data_should_raise_UpdateFailed_exception_on_empty_response(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()
    mock_api.get_panel_info.return_value = APIResponse(
        response_code=200, response_is_json=True, response_data=None
    )

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorPanelInfoDataUpdateCoordinator(hass, mock_entity, mock_api)

    # Act & Assert
    with pytest.raises(
        UpdateFailed,
        match=f"Failed to retrieve panel information for panel '{_PANEL_ID}' \\(no data returned from API\\)",
    ):
        await coordinator._async_update_data()


async def test_async_update_data_should_raise_ConfigEntryAuthFailed_exception_on_LoginError(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()
    mock_api.get_panel_info.side_effect = LoginError("Failed To Login User")

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorPanelInfoDataUpdateCoordinator(hass, mock_entity, mock_api)

    # Act & Assert
    with pytest.raises(
        ConfigEntryAuthFailed,
        match="Failed To Login User",
    ):
        await coordinator._async_update_data()
