from typing import Any
from custom_components.sector.coordinator import DeviceRegistry


def test_device_registration():
    device_registry = DeviceRegistry()

    temperature_device: dict[str, Any] = {
        "serial_no": "12345",
        "name": "Some Leakage device",
        "model": "Leakage Detector",
        "entities": {
            "Temperature Sensor": {
                "name": "Some Temp sensor",
                "sensors": {
                    "temperature": "25",
                },
                "model": "Temperature Sensor",
            }
        },
    }
    leakage_device: dict[str, Any] = {
        "serial_no": "12345",
        "name": "Some Leakage device",
        "model": "Leakage Detector",
        "entities": {
            "Leakage Detector": {
                "name": "Some Leakage device",
                "sensors": {
                    "alarm": False,
                    "low_battery": False,
                },
                "model": "Leakage Detector",
            }
        },
    }
    device_registry.register_device(temperature_device)
    device_registry.register_device(leakage_device)
    devices = device_registry.fetch_devices()

    # Assert
    leakage_device = devices["12345"]
    leakage_entities = leakage_device["entities"]
    leakage_entity = leakage_entities["Leakage Detector"]
    temperature_entity = leakage_entities["Temperature Sensor"]

    assert leakage_device["serial_no"] == "12345"
    assert leakage_device["name"] == "Some Leakage device"
    assert leakage_device["model"] == "Leakage Detector"

    assert leakage_entity["name"] == "Some Leakage device"
    assert leakage_entity["model"] == "Leakage Detector"
    assert leakage_entity["sensors"] == {
        "alarm": False,
        "low_battery": False,
    }

    assert temperature_entity["name"] == "Some Temp sensor"
    assert temperature_entity["model"] == "Temperature Sensor"
    assert temperature_entity["sensors"] == {
        "temperature": "25",
    }

    device = device_registry.fetch_device("12345")
    assert device

def test_device_fetch_by_coordinator():
    device_registry = DeviceRegistry()

    temperature_device: dict[str, Any] = {
        "serial_no": "12345",
        "name": "Some Leakage device",
        "model": "Leakage Detector",
        "entities": {
            "Temperature Sensor": {
                "name": "Some Temp sensor",
                "sensors": {
                    "temperature": "25",
                },
                "model": "Temperature Sensor",
                "coordinator_name": "A",
            },
        },
    }
    leakage_device: dict[str, Any] = {
        "serial_no": "12345",
        "name": "Some Leakage device",
        "model": "Leakage Detector",
        "entities": {
            "Leakage Detector": {
                "name": "Some Leakage device",
                "sensors": {
                    "alarm": False,
                    "low_battery": False,
                },
                "model": "Leakage Detector",
                "coordinator_name": "B",
            }
        },
    }
    device_registry.register_device(temperature_device)
    device_registry.register_device(leakage_device)
    devices_coordinator_A = device_registry.fetch_devices_by_coordinator("A")
    devices_coordinator_B = device_registry.fetch_devices_by_coordinator("B")

    # Assert
    leakage_device = devices_coordinator_A["12345"]
    assert leakage_device["serial_no"] == "12345"
    assert leakage_device["name"] == "Some Leakage device"
    assert leakage_device["model"] == "Leakage Detector"
    leakage_device = devices_coordinator_B["12345"]
    assert leakage_device["serial_no"] == "12345"
    assert leakage_device["name"] == "Some Leakage device"
    assert leakage_device["model"] == "Leakage Detector"

    coordinator_A_entities = devices_coordinator_A["12345"]["entities"]
    coordinator_B_entities = devices_coordinator_B["12345"]["entities"]

    assert len(coordinator_A_entities) == 1
    assert len(coordinator_B_entities) == 1

    temperature_entity = coordinator_A_entities.get("Temperature Sensor")
    leakage_entity = coordinator_B_entities.get("Leakage Detector")
    assert temperature_entity
    assert leakage_entity

    assert temperature_entity["name"] == "Some Temp sensor"
    assert temperature_entity["model"] == "Temperature Sensor"
    assert temperature_entity["sensors"] == {
        "temperature": "25",
    }

    assert leakage_entity["name"] == "Some Leakage device"
    assert leakage_entity["model"] == "Leakage Detector"
    assert leakage_entity["sensors"] == {
        "alarm": False,
        "low_battery": False,
    }