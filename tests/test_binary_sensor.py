import pytest
from unittest.mock import Mock

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant

from custom_components.sector.binary_sensor import (
    async_setup_entry,
    SectorAlarmBinarySensor,
    SectorAlarmClosedSensor,
    SectorAlarmPanelOnlineBinarySensor,
)
from custom_components.sector.const import RUNTIME_DATA
from custom_components.sector.coordinator import DeviceRegistry

_DEVICE_COORDINATOR_NAME = "device-coordinator"

@pytest.fixture
def coordinator():
    coordinator = Mock(spec=DataUpdateCoordinator)
    device_registry = DeviceRegistry()
    device_registry.register_device(
        {
            "serial_no": "SERIAL1",
            "name": "Front Door",
            "model": "Door/Window Sensor",
            "entities": {
                "Door/Window Sensor": {
                    "model": "Door/Window Sensor",
                    "coordinator_name": _DEVICE_COORDINATOR_NAME,
                    "sensors": {
                        "closed": True,
                        "low_battery": False,
                    },
                },
            },
        }
    )
    device_registry.register_device(
        {
            "serial_no": "SERIAL500",
            "name": "Alarm Control Panel",
            "model": "Alarm Panel",
            "entities": {
                "Alarm Panel": {
                    "model": "Alarm Panel",
                    "coordinator_name": _DEVICE_COORDINATOR_NAME,
                    "sensors": {
                        "online": True,
                    },
                },
            },
        }
    )
    coordinator.data = {"device_registry": device_registry}
    coordinator.name = _DEVICE_COORDINATOR_NAME
    return coordinator


@pytest.fixture
def entry(coordinator):
    entry = Mock()
    entry.runtime_data = {
        RUNTIME_DATA.DEVICE_COORDINATORS: [coordinator],
    }
    return entry


async def test_async_setup_entry_adds_entities(hass: HomeAssistant, entry, coordinator):
    # Prepare
    entities = []

    def async_add_entities(new_entities, update_before_add=False):
        entities.extend(new_entities)

    # Act
    await async_setup_entry(hass, entry, async_add_entities)

    # Assert
    assert len(entities) == 3

    assert any(isinstance(e, SectorAlarmClosedSensor) for e in entities)
    assert any(isinstance(e, SectorAlarmBinarySensor) for e in entities)
    assert any(isinstance(e, SectorAlarmPanelOnlineBinarySensor) for e in entities)


def test_binary_sensor_is_on(coordinator):
    # Prepare & Act
    entity = SectorAlarmBinarySensor(
        coordinator=coordinator,
        serial_no="SERIAL1",
        entity_description=Mock(key="low_battery"),
        device_name="Front Door",
        device_model="Door/Window Sensor",
        entity_model="Door/Window Sensor",
    )

    # Assert
    assert entity.is_on is False


def test_closed_sensor_inverts_value(coordinator):
    # Prepare & Act
    entity = SectorAlarmClosedSensor(
        coordinator=coordinator,
        serial_no="SERIAL1",
        entity_description=Mock(key="closed"),
        device_name="Front Door",
        device_model="Door/Window Sensor",
        entity_model="Door/Window Sensor",
    )
    device_registry: DeviceRegistry = coordinator.data["device_registry"]

    # Assert
    assert entity.is_on is False

    # Flip to open
    device = device_registry.fetch_device("SERIAL1")
    device["entities"]["Door/Window Sensor"]["sensors"]["closed"] = False
    device_registry.register_device(device)
    assert entity.is_on is True


def test_closed_sensor_none_returns_none(coordinator):
    # Prepare & Act
    device_registry: DeviceRegistry = coordinator.data["device_registry"]
    device = device_registry.fetch_device("SERIAL1")
    device["entities"]["Door/Window Sensor"]["sensors"]["closed"] = None
    device_registry.register_device(device)

    entity = SectorAlarmClosedSensor(
        coordinator=coordinator,
        serial_no="SERIAL1",
        entity_description=Mock(key="closed"),
        device_name="Front Door",
        device_model="Door/Window Sensor",
        entity_model="Door/Window Sensor",
    )

    # Assert
    assert entity.is_on is None


def test_panel_online_sensor(coordinator):
    # Prepare & Act
    entity = SectorAlarmPanelOnlineBinarySensor(
        coordinator=coordinator,
        serial_no="SERIAL500",
        entity_description=Mock(key="online"),
        device_name="Panel",
        device_model="Alarm Panel",
        entity_model="Alarm Panel",
    )

    # Assert
    assert entity.is_on is True


async def test_async_setup_entry_no_entities(hass: HomeAssistant):
    # Prepare
    device_registry = DeviceRegistry()
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.data = {"device_registry": device_registry}
    coordinator.name = _DEVICE_COORDINATOR_NAME

    entry = Mock()
    entry.runtime_data = {RUNTIME_DATA.DEVICE_COORDINATORS: [coordinator]}

    add = Mock()

    # Act
    await async_setup_entry(hass, entry, add)

    # Assert
    add.assert_not_called()