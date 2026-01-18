from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.sector.coordinator import (
    SectorBaseDataUpdateCoordinator,
)
from custom_components.sector.entity import _FAILED_UPDATE_LIMIT, SectorAlarmBaseEntity

_PANEL_ID = "1234"


def _create_mock_config_entity() -> MockConfigEntry:
    return MockConfigEntry(
        domain="sector",
        title="Test Panel",
        data={"panel_id": _PANEL_ID, "username": "abc", "password": "xyz"},
        entry_id="test123",
    )

async def test_available_should_return_true_when_nothing_specified(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorBaseDataUpdateCoordinator(
        hass,
        mock_entity,
        mock_api,
        "some_coordinator_name",
        timedelta(seconds=30),
    )
    coordinator.data = {"devices": {"DEVICE_ID": {}}}

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        device_id="DEVICE_ID",
        serial_no="SERIAL123",
        device_name="Test Device",
        device_model="Model X",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert is_available

async def test_available_should_return_true_when_coordinator_is_healthy(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorBaseDataUpdateCoordinator(
        hass,
        mock_entity,
        mock_api,
        "some_coordinator_name",
        timedelta(seconds=30),
    )
    coordinator.data = {"devices": {"DEVICE_ID": {}}}
    coordinator._update_error_counter = (
        0  # Simulate healthy coordinator with no erros
    )
    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        device_id="DEVICE_ID",
        serial_no="SERIAL123",
        device_name="Test Device",
        device_model="Model X",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert is_available

async def test_available_should_return_true_when_device_last_updated_has_not_reached_limit(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorBaseDataUpdateCoordinator(
        hass,
        mock_entity,
        mock_api,
        "some_coordinator_name",
        timedelta(seconds=30),
    )
    coordinator.data = {
        "devices": {
            "DEVICE_ID": {
                "last_updated": "2099-01-01T00:00:00+00:00",
            }
        }
    }

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        device_id="DEVICE_ID",
        serial_no="SERIAL123",
        device_name="Test Device",
        device_model="Model X",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert is_available

async def test_available_should_return_true_when_device_has_not_reached_failed_update_limit(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorBaseDataUpdateCoordinator(
        hass,
        mock_entity,
        mock_api,
        "some_coordinator_name",
        timedelta(seconds=30),
    )
    coordinator.data = {
        "devices": {
            "DEVICE_ID": {
                "failed_update_count": _FAILED_UPDATE_LIMIT - 1,
            }
        }
    }

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        device_id="DEVICE_ID",
        serial_no="SERIAL123",
        device_name="Test Device",
        device_model="Model X",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert is_available

async def test_available_should_return_false_when_no_device(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorBaseDataUpdateCoordinator(
        hass,
        mock_entity,
        mock_api,
        "some_coordinator_name",
        timedelta(seconds=30),
    )
    coordinator.data = {"devices": {"DEVICE_ID_OTHER": {}}}

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        device_id="DEVICE_ID",
        serial_no="SERIAL123",
        device_name="Test Device",
        device_model="Model X",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert not is_available

async def test_available_should_return_false_when_coordinator_is_not_healthy(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorBaseDataUpdateCoordinator(
        hass,
        mock_entity,
        mock_api,
        "some_coordinator_name",
        timedelta(seconds=30),
    )
    coordinator.data = {
        "devices": {
            "DEVICE_ID": {}
        }
    }
    coordinator._update_error_counter = (
        100  # Simulate unhealthy coordinator with a lot of errors
    )
    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        device_id="DEVICE_ID",
        serial_no="SERIAL123",
        device_name="Test Device",
        device_model="Model X",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert not is_available


async def test_available_should_return_false_when_device_has_reached_failed_update_limit(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorBaseDataUpdateCoordinator(
        hass,
        mock_entity,
        mock_api,
        "some_coordinator_name",
        timedelta(seconds=30),
    )
    coordinator.data = {
        "devices": {
            "DEVICE_ID": {
                "failed_update_count": _FAILED_UPDATE_LIMIT,
            }
        }
    }

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        device_id="DEVICE_ID",
        serial_no="SERIAL123",
        device_name="Test Device",
        device_model="Model X",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert not is_available

async def test_available_should_return_false_when_device_last_updated_has_reached_limit(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    coordinator = SectorBaseDataUpdateCoordinator(
        hass,
        mock_entity,
        mock_api,
        "some_coordinator_name",
        timedelta(seconds=30),
    )
    coordinator.data = {
        "devices": {
            "DEVICE_ID": {
                "last_updated": "2000-01-01T00:00:00+00:00",
            }
        }
    }

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        device_id="DEVICE_ID",
        serial_no="SERIAL123",
        device_name="Test Device",
        device_model="Model X",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert not is_available