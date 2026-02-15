from unittest.mock import AsyncMock, Mock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.sector.coordinator import (
    DeviceRegistry,
    SectorDeviceDataUpdateCoordinator,
)
from custom_components.sector.endpoints import DataEndpointType
from custom_components.sector.entity import _FAILED_UPDATE_LIMIT, SectorAlarmBaseEntity

_PANEL_ID = "1234"
_DEVICE_COORDINATOR_NAME = "device-coordinator"

_MANDATORY_ENDPOINTS = {DataEndpointType.PANEL_STATUS}
_OPTIONAL_ENDPOINTS = {
    DataEndpointType.LOCK_STATUS,
    DataEndpointType.SMART_PLUG_STATUS,
    DataEndpointType.DOOR_AND_WINDOW,
    DataEndpointType.SMOKE_DETECTOR,
    DataEndpointType.LEAKAGE_DETECTOR,
    DataEndpointType.CAMERAS,
    DataEndpointType.HUMIDITY,
    DataEndpointType.TEMPERATURE,
    DataEndpointType.TEMPERATURE_LEGACY,
}


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

    device_registry = DeviceRegistry()
    device_registry.register_device(
        {
            "serial_no": "DEVICE_ID",
            "entities": {"Model Y": {}, "coordinator_name": _DEVICE_COORDINATOR_NAME},
        }
    )
    coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=Mock(),
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    coordinator.data = {"device_registry": device_registry}

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        serial_no="DEVICE_ID",
        device_name="Test Device",
        device_model="Model X",
        entity_model="Model Y",
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

    device_registry = DeviceRegistry()
    device_registry.register_device(
        {"serial_no": "DEVICE_ID", "entities": {"Model Y": {}}}
    )
    coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=Mock(),
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    coordinator.data = {"device_registry": device_registry}

    coordinator._update_error_counter = 0  # Simulate healthy coordinator with no erros
    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        serial_no="DEVICE_ID",
        device_name="Test Device",
        device_model="Model X",
        entity_model="Model Y",
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

    device_registry = DeviceRegistry()
    device_registry.register_device(
        {
            "serial_no": "DEVICE_ID",
            "entities": {
                "Model Y": {
                    "last_updated": "2099-01-01T00:00:00+00:00",
                }
            },
        }
    )
    coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=Mock(),
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    coordinator.data = {"device_registry": device_registry}

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        serial_no="DEVICE_ID",
        device_name="Test Device",
        device_model="Model X",
        entity_model="Model Y",
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

    device_registry = DeviceRegistry()
    device_registry.register_device(
        {
            "serial_no": "DEVICE_ID",
            "entities": {
                "Model Y": {
                    "failed_update_count": _FAILED_UPDATE_LIMIT - 1,
                }
            },
        }
    )
    coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=Mock(),
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    coordinator.data = {"device_registry": device_registry}

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        serial_no="DEVICE_ID",
        device_name="Test Device",
        device_model="Model X",
        entity_model="Model Y",
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

    device_registry = DeviceRegistry()
    device_registry.register_device(
        {
            "serial_no": "DEVICE_ID_OTHER",
            "entities": {"Model Y": {}},
        }
    )
    coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=Mock(),
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    coordinator.data = {"device_registry": device_registry}

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        serial_no="DEVICE_ID",
        device_name="Test Device",
        device_model="Model X",
        entity_model="Model Y",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert not is_available


async def test_available_should_return_false_when_no_entity(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_registry.register_device(
        {
            "serial_no": "DEVICE_ID",
            "entities": {"Model K": {}},
        }
    )
    coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=Mock(),
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    coordinator.data = {"device_registry": device_registry}

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        serial_no="DEVICE_ID",
        device_name="Test Device",
        device_model="Model X",
        entity_model="Model Y",
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

    device_registry = DeviceRegistry()
    device_registry.register_device(
        {
            "serial_no": "DEVICE_ID",
            "entities": {"Model Y": {}},
        }
    )
    coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=Mock(),
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    coordinator.data = {"device_registry": device_registry}
    coordinator._update_error_counter = (
        100  # Simulate unhealthy coordinator with a lot of errors
    )
    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        serial_no="DEVICE_ID",
        device_name="Test Device",
        device_model="Model X",
        entity_model="Model Y",
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

    device_registry = DeviceRegistry()
    device_registry.register_device(
        {
            "serial_no": "DEVICE_ID",
            "entities": {
                "Model Y": {
                    "failed_update_count": _FAILED_UPDATE_LIMIT,
                }
            },
        }
    )
    coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=Mock(),
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    coordinator.data = {"device_registry": device_registry}

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        serial_no="DEVICE_ID",
        device_name="Test Device",
        device_model="Model X",
        entity_model="Model Y",
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

    device_registry = DeviceRegistry()
    device_registry.register_device(
        {
            "serial_no": "DEVICE_ID",
            "entities": {
                "Model Y": {
                    "last_updated": "2000-01-01T00:00:00+00:00",
                }
            },
        }
    )
    coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=Mock(),
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    coordinator.data = {"device_registry": device_registry}

    entity = SectorAlarmBaseEntity(
        coordinator=coordinator,
        serial_no="DEVICE_ID",
        device_name="Test Device",
        device_model="Model X",
        entity_model="Model Y",
    )

    # Act
    is_available: bool = entity.available

    # Assert
    assert not is_available
