from typing import Any
import pytest
from unittest.mock import Mock

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.sector.const import RUNTIME_DATA
from custom_components.sector.sensor import async_setup_entry, SectorAlarmSensor
from custom_components.sector.coordinator import DeviceRegistry

_DEVICE_COORDINATOR_NAME = "device-coordinator"

@pytest.fixture
def coordinator():
    devices: dict[str, Any] = {
        "serial_no": "SERIAL1",
        "name": "Smoke Detector Entrance",
        "model": "Smoke Detector",
        "entities": {
            "Humidity Sensor": {
                "name": "My Humidity Sensor A",
                "model": "Humidity Sensor",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "sensors": {
                    "humidity": 45,
                },
            },
            "Temperature Sensor": {
                "name": "My Temperature Sensor A",
                "model": "Temperature Sensor",
                "coordinator_name": _DEVICE_COORDINATOR_NAME,
                "sensors": {
                    "temperature": 25,
                },
            },
        },
    }

    device_registry = DeviceRegistry()
    device_registry.register_device(devices)
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.data = {"device_registry": device_registry}
    coordinator.name = _DEVICE_COORDINATOR_NAME
    return coordinator


@pytest.fixture
def entry(coordinator):
    entry = Mock()
    entry.runtime_data = {RUNTIME_DATA.DEVICE_COORDINATORS: [coordinator]}
    return entry


async def test_async_setup_entry_adds_sensors(hass: HomeAssistant, entry, coordinator):
    entities = []

    def async_add_entities(new_entities, update_before_add=False):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, async_add_entities)

    assert len(entities) == 2

    temp: SectorAlarmSensor = next(
        e for e in entities if e._entity_description.key == "temperature"
    )
    hum: SectorAlarmSensor = next(
        e for e in entities if e._entity_description.key == "humidity"
    )

    assert temp._entity_description.device_class == SensorDeviceClass.TEMPERATURE
    assert (
        temp._entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    )
    assert temp.unique_id == "SERIAL1_temperature"
    assert temp.native_value == 25

    assert hum._entity_description.device_class == SensorDeviceClass.HUMIDITY
    assert hum._entity_description.native_unit_of_measurement == PERCENTAGE
    assert hum.unique_id == "SERIAL1_humidity"
    assert hum.native_value == 45


def test_native_value_none_when_missing(coordinator):
    device_registry: DeviceRegistry = coordinator.data["device_registry"]
    device = device_registry.fetch_device("SERIAL1")
    device["entities"]["Temperature Sensor"]["sensors"].pop("temperature")
    device_registry.register_device(device)

    entity = SectorAlarmSensor(
        coordinator=coordinator,
        serial_no="SERIAL1",
        entity_description=Mock(key="temperature"),
        device_name="Smoke Detector Entrance",
        device_model="Smoke Detector",
        entity_model="Temperature Sensor",
    )

    assert entity.native_value is None


async def test_async_setup_entry_no_entities(hass: HomeAssistant):
    device_registry = DeviceRegistry()
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.data = {"device_registry": device_registry}
    coordinator.name = _DEVICE_COORDINATOR_NAME

    entry = Mock()
    entry.runtime_data = {RUNTIME_DATA.DEVICE_COORDINATORS: [coordinator]}

    add = Mock()

    await async_setup_entry(hass, entry, add)

    add.assert_not_called()
