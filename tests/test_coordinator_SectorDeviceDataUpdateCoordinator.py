from typing import Any
from unittest.mock import AsyncMock, Mock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.sector.api_model import (
    Component,
    Device,
    Lock,
    LogRecords,
    PanelInfo,
    SmartPlug,
    Temperature,
    PanelStatus,
)
from custom_components.sector.client import APIResponse, ApiError, LoginError
from custom_components.sector.coordinator import (
    DeviceRegistry,
    SectorDeviceDataUpdateCoordinator,
)
from custom_components.sector.endpoints import DataEndpointType

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


def _create_mock_sector_panel_info(panel_info: PanelInfo | None) -> Mock:
    coordinator_mock = Mock()
    coordinator_mock.data = {"panel_info": panel_info}
    return coordinator_mock


async def test_async_setup_should_calculate_supported_optional_endpoints(
    hass: HomeAssistant,
):
    # Prepare
    lock: Lock = {
        "Label": "Front Door",
        "Serial": "LOCK123",
        "SerialNo": "LOCK123",
        "Status": "lock",
        "BatteryLow": True,
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
        "PanelCodeLength": 6,
        "QuickArmEnabled": True,
        "CanPartialArm": True,
        "Locks": [lock],
        "Smartplugs": [smart_plug],
        "Temperatures": [temperature],
        "Capabilities": [],
    }
    door_and_window_detector_component: Device = {
        "SerialString": "DOOR_SERIAL",
        "Label": "Front Door",
        "Name": "Front Door Lock",
        "Type": "Doors and Windows",
        "LowBattery": False,
        "Alarm": False,
        "Closed": True,
    }
    temperature_component: Component = {
        "SerialNo": "TEMP_SERIAL",
        "Label": "Kitchen",
        "Name": "Kitchen Temperature",
        "Type": "Temperatures",
        "Temperature": 21.5,
        "Humidity": None,
        "LowBattery": False,
    }
    humidity_component: Component = {
        "SerialNo": "HUM_SERIAL",
        "Label": "Kitchen",
        "Name": "Kitchen Humidity",
        "Type": "Humidity",
        "Humidity": 45.0,
        "Temperature": None,
        "LowBattery": False,
    }
    smoke_detector_component: Device = {
        "SerialString": "SMOKE_SERIAL",
        "Label": "Entrance Smoke Detector",
        "Name": "Entrance Smoke Detector Sensor",
        "Type": "Smoke Detector",
        "Alarm": False,
        "LowBattery": False,
        "Closed": None,
    }
    leakage_detector_component: Device = {
        "SerialString": "LEAK_SERIAL",
        "Label": "Bathroom leak detector",
        "Name": "Bathroom leak Sensor",
        "Type": "Leakage Detectors",
        "Alarm": False,
        "LowBattery": False,
        "Closed": None,
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.DOOR_AND_WINDOW: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [
                    {"Rooms": [{"Devices": [door_and_window_detector_component]}]}
                ],
            },
        ),
        DataEndpointType.SMOKE_DETECTOR: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [{"Rooms": [{"Devices": [smoke_detector_component]}]}],
            },
        ),
        DataEndpointType.LEAKAGE_DETECTOR: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [{"Rooms": [{"Devices": [leakage_detector_component]}]}],
            },
        ),
        DataEndpointType.TEMPERATURE: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [temperature_component]}]}],
            },
        ),
        DataEndpointType.HUMIDITY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [humidity_component]}]}],
            },
        ),
        DataEndpointType.CAMERAS: APIResponse(
            response_code=404,
            response_is_json=False,
            response_data=None,
        ),
    }

    device_registry = DeviceRegistry()
    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )

    # Act
    await device_coordinator._async_setup()

    # Assert
    assert device_coordinator._data_endpoints == {
        DataEndpointType.PANEL_STATUS,
        DataEndpointType.LOCK_STATUS,
        DataEndpointType.SMART_PLUG_STATUS,
        DataEndpointType.DOOR_AND_WINDOW,
        DataEndpointType.SMOKE_DETECTOR,
        DataEndpointType.LEAKAGE_DETECTOR,
        # DataEndpointType.CAMERAS, <---- not yet supported
        DataEndpointType.HUMIDITY,
        DataEndpointType.TEMPERATURE,
        # DataEndpointType.LOGS, <--- disabled for now TODO repair events
    }


async def test_async_setup_should_calculate_supported_optional_endpoints_legacy(
    hass: HomeAssistant,
):
    # Prepare
    lock: Lock = {
        "Label": "Front Door",
        "Serial": "LOCK123",
        "SerialNo": "LOCK123",
        "Status": "lock",
        "BatteryLow": True,
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
        "PanelCodeLength": 6,
        "QuickArmEnabled": True,
        "CanPartialArm": True,
        "Locks": [lock],
        "Smartplugs": [smart_plug],
        "Temperatures": [temperature],
        "Capabilities": ["UseLegacyHomeScreen"],
    }
    door_and_window_detector_component: Device = {
        "SerialString": "DOOR_SERIAL",
        "Label": "Front Door",
        "Name": "Front Door Lock",
        "Type": "Doors and Windows",
        "LowBattery": False,
        "Alarm": False,
        "Closed": True,
    }
    temperature_component: Component = {
        "SerialNo": "TEMP_SERIAL",
        "Label": "Kitchen",
        "Name": "Kitchen Temperature",
        "Type": "Temperatures",
        "Temperature": 21.5,
        "Humidity": None,
        "LowBattery": False,
    }
    humidity_component: Component = {
        "SerialNo": "HUM_SERIAL",
        "Label": "Kitchen",
        "Name": "Kitchen Humidity",
        "Type": "Humidity",
        "Humidity": 45.0,
        "Temperature": None,
        "LowBattery": False,
    }
    smoke_detector_component: Device = {
        "SerialString": "SMOKE_SERIAL",
        "Label": "Entrance Smoke Detector",
        "Name": "Entrance Smoke Detector Sensor",
        "Type": "Smoke Detector",
        "Alarm": False,
        "LowBattery": False,
        "Closed": None,
    }
    leakage_detector_component: Device = {
        "SerialString": "LEAK_SERIAL",
        "Label": "Bathroom leak detector",
        "Name": "Bathroom leak Sensor",
        "Type": "Leakage Detectors",
        "Alarm": False,
        "LowBattery": False,
        "Closed": None,
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.DOOR_AND_WINDOW: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [
                    {"Rooms": [{"Devices": [door_and_window_detector_component]}]}
                ],
            },
        ),
        DataEndpointType.SMOKE_DETECTOR: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [{"Rooms": [{"Devices": [smoke_detector_component]}]}],
            },
        ),
        DataEndpointType.LEAKAGE_DETECTOR: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [{"Rooms": [{"Devices": [leakage_detector_component]}]}],
            },
        ),
        DataEndpointType.TEMPERATURE: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [temperature_component]}]}],
            },
        ),
        DataEndpointType.HUMIDITY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [humidity_component]}]}],
            },
        ),
        DataEndpointType.CAMERAS: APIResponse(
            response_code=404,
            response_is_json=False,
            response_data=None,
        ),
    }
    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )

    # Act
    await device_coordinator._async_setup()

    # Assert
    assert device_coordinator._data_endpoints == {
        DataEndpointType.PANEL_STATUS,
        DataEndpointType.LOCK_STATUS,
        DataEndpointType.SMART_PLUG_STATUS,
        DataEndpointType.TEMPERATURE_LEGACY,
        # DataEndpointType.LOGS, <--- disabled for now TODO repair events
    }


async def test_async_setup_should_keep_mandatory_endpoints_from_empty_PanelInfo(
    hass: HomeAssistant,
):
    # Prepare
    panel_info: PanelInfo = {
        "PanelId": "1234",
        "PanelCodeLength": 6,
        "QuickArmEnabled": True,
        "CanPartialArm": True,
        "Locks": [],
        "Smartplugs": [],
        "Temperatures": [],
        "Capabilities": ["UseLegacyHomeScreen"],
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {}

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )

    # Act
    await device_coordinator._async_setup()

    # Assert
    assert device_coordinator._data_endpoints == {
        DataEndpointType.PANEL_STATUS,
        # DataEndpointType.LOGS, <--- disabled for now TODO repair events
    }


async def test_async_setup_should_raise_UpdateFailed_when_none_PanelInfo(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_panel_info_coordinator = _create_mock_sector_panel_info(None)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )

    # Act & Assert
    with pytest.raises(
        UpdateFailed,
        match=f"Failed to retrieve panel information for panel '{_PANEL_ID}' \\(no data returned from coordinator\\)",
    ):
        await device_coordinator._async_setup()


async def test_async_update_data_should_proccess_PanelInfo_and_HouseCheck_devices(
    hass: HomeAssistant,
):
    # Prepare
    panel_status: PanelStatus = {
        "Status": 1,
        "IsOnline": True,
    }
    lock: Lock = {
        "Label": "Front Door",
        "Serial": "LOCK123",
        "SerialNo": "LOCK123",
        "Status": "lock",
        "BatteryLow": True,
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
        "PanelCodeLength": 6,
        "QuickArmEnabled": True,
        "CanPartialArm": False,
        "Locks": [lock],
        "Smartplugs": [smart_plug],
        "Temperatures": [temperature],
        "Capabilities": [],
    }
    door_and_window_detector_component: Device = {
        "SerialString": "DOOR_SERIAL",
        "Label": "Front Door",
        "Name": "Front Door Lock",
        "Type": "Doors and Windows",
        "LowBattery": False,
        "Alarm": False,
        "Closed": True,
    }
    smoke_detector_component: Device = {
        "SerialString": "SMOKE_SERIAL",
        "Label": "Entrance Smoke Detector",
        "Name": "Entrance Smoke Detector Sensor",
        "Type": "Smoke Detector",
        "Alarm": False,
        "LowBattery": False,
        "Closed": None,
    }
    temperature_component_smoke: Component = {
        "SerialNo": "SMOKE_SERIAL",
        "Label": "Entrance Temperature",
        "Name": "Entrance Temperature",
        "Type": "Temperatures",
        "Temperature": 21.5,
        "Humidity": None,
        "LowBattery": False,
    }
    humidity_component_smoke: Component = {
        "SerialNo": "SMOKE_SERIAL",
        "Label": "Entrance Humidity",
        "Name": "Entrance Humidity",
        "Type": "Humidity",
        "Humidity": 45.0,
        "Temperature": None,
        "LowBattery": False,
    }
    leakage_detector_component: Device = {
        "SerialString": "LEAK_SERIAL",
        "Label": "Bathroom leak detector",
        "Name": "Bathroom leak Sensor",
        "Type": "Leakage Detectors",
        "Alarm": False,
        "LowBattery": False,
        "Closed": None,
    }
    temperature_component_leakage: Component = {
        "SerialNo": "LEAK_SERIAL",
        "Label": "Bathroom Temperature",
        "Name": "Bathroom Temperature",
        "Type": "Temperatures",
        "Temperature": 19.5,
        "Humidity": None,
        "LowBattery": False,
    }
    humidity_component_leakage: Component = {
        "SerialNo": "LEAK_SERIAL",
        "Label": "Bathroom Humidity",
        "Name": "Bathroom Humidity",
        "Type": "Humidity",
        "Humidity": 34.0,
        "Temperature": None,
        "LowBattery": False,
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.PANEL_STATUS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data=panel_status,
        ),
        DataEndpointType.LOCK_STATUS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data=[lock],
        ),
        DataEndpointType.SMART_PLUG_STATUS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data=[smart_plug],
        ),
        DataEndpointType.DOOR_AND_WINDOW: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [
                    {"Rooms": [{"Devices": [door_and_window_detector_component]}]}
                ],
            },
        ),
        DataEndpointType.SMOKE_DETECTOR: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [{"Rooms": [{"Devices": [smoke_detector_component]}]}],
            },
        ),
        DataEndpointType.LEAKAGE_DETECTOR: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [{"Rooms": [{"Devices": [leakage_detector_component]}]}],
            },
        ),
        DataEndpointType.TEMPERATURE: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [
                    {
                        "Places": [
                            {
                                "Components": [
                                    temperature_component_leakage,
                                    temperature_component_smoke,
                                ]
                            }
                        ]
                    }
                ],
            },
        ),
        DataEndpointType.HUMIDITY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [
                    {
                        "Places": [
                            {
                                "Components": [
                                    humidity_component_leakage,
                                    humidity_component_smoke,
                                ]
                            }
                        ]
                    }
                ],
            },
        ),
        DataEndpointType.CAMERAS: APIResponse(
            response_code=404,
            response_is_json=False,
            response_data=None,
        ),
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )

    # Act
    coordinator_data = await device_coordinator._async_update_data()

    # Assert
    assert "device_registry" in coordinator_data
    device_registry: DeviceRegistry = coordinator_data["device_registry"]
    devices: dict[str, Any] = device_registry.fetch_devices()

    # Locks
    lock_device = devices["LOCK123"]
    lock_entitites = lock_device["entities"]
    lock_entity = lock_entitites["Smart Lock"]

    assert len(lock_entitites.keys()) == 1
    assert lock_device["name"] == lock["Label"]
    assert lock_device["serial_no"] == lock["SerialNo"]
    assert lock_device["model"] == "Smart Lock"

    assert lock_entity["name"] == lock["Label"]
    assert lock_entity["model"] == "Smart Lock"
    assert lock_entity["last_updated"]
    assert "failed_update_count" not in lock_entity
    assert lock_entity["sensors"] == {"low_battery": True, "lock_status": "lock"}
    assert lock_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME

    # Plugs
    plug_device = devices["PLUG123"]
    plug_entities = plug_device["entities"]
    plug_entity = plug_entities["Smart Plug"]

    assert len(plug_entities.keys()) == 1
    assert plug_device["name"] == smart_plug["Label"]
    assert plug_device["serial_no"] == smart_plug["SerialNo"]
    assert plug_device["model"] == "Smart Plug"

    assert plug_entity["name"] == smart_plug["Label"]
    assert plug_entity["model"] == "Smart Plug"
    assert plug_entity["id"] == smart_plug["Id"]
    assert plug_entity["last_updated"]
    assert "failed_update_count" not in plug_entity
    assert plug_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert plug_entity["sensors"] == {"plug_status": smart_plug.get("Status")}

    # Alarm Panel
    alarm_device = devices["1234"]
    alarm_entities = alarm_device["entities"]
    alarm_entity = alarm_entities["Alarm panel"]

    assert len(alarm_entities.keys()) == 1
    assert alarm_device["name"] == "Alarm Control Panel"
    assert alarm_device["serial_no"] == _PANEL_ID
    assert alarm_device["model"] == "Alarm panel"

    assert alarm_entity["name"] == "Alarm Control Panel"
    assert alarm_entity["model"] == "Alarm panel"
    assert alarm_entity["panel_code_length"] == 6
    assert alarm_entity["panel_quick_arm"]
    assert not alarm_entity["panel_partial_arm"]
    assert alarm_entity["last_updated"]
    assert "failed_update_count" not in alarm_entity
    assert alarm_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert alarm_entity["sensors"] == {
        "online": panel_status.get("IsOnline"),
        "alarm_status": panel_status.get("Status"),
    }

    # Door / Windows
    door_device = devices["DOOR_SERIAL"]
    door_entities = door_device["entities"]
    door_entity = door_entities["Door/Window Sensor"]

    assert len(door_entities.keys()) == 1
    assert door_device["name"] == door_and_window_detector_component["Label"]
    assert (
        door_device["serial_no"] == door_and_window_detector_component["SerialString"]
    )
    assert door_device["model"] == "Door/Window Sensor"

    assert door_entity["name"] == door_and_window_detector_component["Label"]
    assert door_entity["model"] == "Door/Window Sensor"
    assert door_entity["last_updated"]
    assert "failed_update_count" not in door_entity
    assert door_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert door_entity["sensors"] == {
        "low_battery": door_and_window_detector_component.get("LowBattery"),
        "alarm": door_and_window_detector_component.get("Alarm"),
        "closed": door_and_window_detector_component.get("Closed"),
    }

    # Smoke Detector
    smoke_device = devices["SMOKE_SERIAL"]
    smoke_entities = smoke_device["entities"]
    smoke_entity = smoke_entities["Smoke Detector"]

    assert len(smoke_entities.keys()) == 3
    assert smoke_device["name"] == smoke_detector_component["Label"]
    assert smoke_device["serial_no"] == smoke_detector_component["SerialString"]
    assert smoke_device["model"] == "Smoke Detector"

    assert smoke_entity["name"] == smoke_detector_component["Label"]
    assert smoke_entity["model"] == "Smoke Detector"
    assert smoke_entity["last_updated"]
    assert "failed_update_count" not in smoke_entity
    assert smoke_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert smoke_entity["sensors"] == {
        "low_battery": smoke_detector_component.get("LowBattery"),
        "alarm": smoke_detector_component.get("Alarm"),
    }

    # Temperature Sensor
    temperature_entity = smoke_entities["Temperature Sensor V2"]

    assert temperature_entity["name"] == temperature_component_smoke["Label"]
    assert temperature_entity["model"] == "Temperature Sensor V2"
    assert temperature_entity["last_updated"]
    assert "failed_update_count" not in temperature_entity
    assert temperature_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert temperature_entity["sensors"] == {
        "low_battery": temperature_component_smoke.get("LowBattery"),
        "temperature": temperature_component_smoke.get("Temperature"),
    }

    # Humidity Sensor
    humidity_entity = smoke_entities["Humidity Sensor"]

    assert humidity_entity["name"] == humidity_component_smoke["Name"]
    assert humidity_entity["model"] == "Humidity Sensor"
    assert humidity_entity["last_updated"]
    assert "failed_update_count" not in humidity_entity
    assert humidity_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert humidity_entity["sensors"] == {
        "low_battery": humidity_component_smoke.get("LowBattery"),
        "humidity": humidity_component_smoke.get("Humidity"),
    }

    # Leakage Detector
    leakage_device = devices["LEAK_SERIAL"]
    leakage_entities = leakage_device["entities"]
    leakage_entity = leakage_entities["Leakage Detector"]

    assert len(leakage_entities.keys()) == 3
    assert leakage_device["name"] == leakage_detector_component["Label"]
    assert leakage_device["serial_no"] == leakage_detector_component["SerialString"]
    assert leakage_device["model"] == "Leakage Detector"

    assert leakage_entity["name"] == leakage_detector_component["Label"]
    assert leakage_entity["model"] == "Leakage Detector"
    assert leakage_entity["last_updated"]
    assert "failed_update_count" not in leakage_entity
    assert leakage_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert leakage_entity["sensors"] == {
        "low_battery": leakage_detector_component.get("LowBattery"),
        "alarm": leakage_detector_component.get("Alarm"),
    }

    # Temperature Sensor
    temperature_entity = leakage_entities["Temperature Sensor V2"]

    assert temperature_entity["name"] == temperature_component_leakage["Label"]
    assert temperature_entity["model"] == "Temperature Sensor V2"
    assert temperature_entity["last_updated"]
    assert "failed_update_count" not in temperature_entity
    assert temperature_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert temperature_entity["sensors"] == {
        "low_battery": temperature_component_leakage.get("LowBattery"),
        "temperature": temperature_component_leakage.get("Temperature"),
    }

    # Humidity Sensor
    humidity_entity = leakage_entities["Humidity Sensor"]

    assert humidity_entity["name"] == humidity_component_leakage["Name"]
    assert humidity_entity["model"] == "Humidity Sensor"
    assert humidity_entity["last_updated"]
    assert "failed_update_count" not in humidity_entity
    assert humidity_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert humidity_entity["sensors"] == {
        "low_battery": humidity_component_leakage.get("LowBattery"),
        "humidity": humidity_component_leakage.get("Humidity"),
    }


async def test_async_update_data_should_override_device_if_endpoint_is_device(
    hass: HomeAssistant,
):
    # Prepare
    panel_status: PanelStatus = {
        "Status": 1,
        "IsOnline": True,
    }
    panel_info: PanelInfo = {
        "PanelId": "1234",
        "PanelCodeLength": 6,
        "QuickArmEnabled": True,
        "CanPartialArm": False,
        "Locks": [],
        "Smartplugs": [],
        "Temperatures": [],
        "Capabilities": [],
    }

    leakage_detector_component: Device = {
        "SerialString": "LEAK_SERIAL",
        "Label": "Bathroom leak detector",
        "Name": "Bathroom leak Sensor",
        "Type": "Leakage Detectors",
        "Alarm": False,
        "LowBattery": False,
        "Closed": None,
    }
    temperature_component_leakage: Component = {
        "SerialNo": "LEAK_SERIAL",
        "Label": "Bathroom Temperature",
        "Name": "Bathroom Temperature",
        "Type": "Temperatures",
        "Temperature": 19.5,
        "Humidity": None,
        "LowBattery": False,
    }
    humidity_component_leakage: Component = {
        "SerialNo": "LEAK_SERIAL",
        "Label": "Bathroom Humidity",
        "Name": "Bathroom Humidity",
        "Type": "Humidity",
        "Humidity": 34.0,
        "Temperature": None,
        "LowBattery": False,
    }

    # Intentionally retrun non devices results first, so that they are proccessed first
    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.PANEL_STATUS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data=panel_status,
        ),
        DataEndpointType.TEMPERATURE: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [
                    {
                        "Places": [
                            {
                                "Components": [
                                    temperature_component_leakage,
                                ]
                            }
                        ]
                    }
                ],
            },
        ),
        DataEndpointType.HUMIDITY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [
                    {
                        "Places": [
                            {
                                "Components": [
                                    humidity_component_leakage,
                                ]
                            }
                        ]
                    }
                ],
            },
        ),
        DataEndpointType.LEAKAGE_DETECTOR: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Floors": [{"Rooms": [{"Devices": [leakage_detector_component]}]}],
            },
        ),
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )

    # Act
    coordinator_data = await device_coordinator._async_update_data()

    # Assert
    assert "device_registry" in coordinator_data
    device_registry: DeviceRegistry = coordinator_data["device_registry"]
    devices: dict[str, Any] = device_registry.fetch_devices()

    # Leakage Detector
    leakage_device = devices["LEAK_SERIAL"]
    leakage_entities = leakage_device["entities"]
    leakage_entity = leakage_entities["Leakage Detector"]

    assert len(leakage_entities.keys()) == 3
    assert leakage_device["name"] == leakage_detector_component["Label"]
    assert leakage_device["serial_no"] == leakage_detector_component["SerialString"]
    assert leakage_device["model"] == "Leakage Detector"

    assert leakage_entity["name"] == leakage_detector_component["Label"]
    assert leakage_entity["model"] == "Leakage Detector"
    assert leakage_entity["last_updated"]
    assert "failed_update_count" not in leakage_entity
    assert leakage_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert leakage_entity["sensors"] == {
        "low_battery": leakage_detector_component.get("LowBattery"),
        "alarm": leakage_detector_component.get("Alarm"),
    }

    # Temperature Sensor
    temperature_entity = leakage_entities["Temperature Sensor V2"]

    assert temperature_entity["name"] == temperature_component_leakage["Label"]
    assert temperature_entity["model"] == "Temperature Sensor V2"
    assert temperature_entity["last_updated"]
    assert "failed_update_count" not in temperature_entity
    assert temperature_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert temperature_entity["sensors"] == {
        "low_battery": temperature_component_leakage.get("LowBattery"),
        "temperature": temperature_component_leakage.get("Temperature"),
    }

    # Humidity Sensor
    humidity_entity = leakage_entities["Humidity Sensor"]

    assert humidity_entity["name"] == humidity_component_leakage["Name"]
    assert humidity_entity["model"] == "Humidity Sensor"
    assert humidity_entity["last_updated"]
    assert "failed_update_count" not in humidity_entity
    assert humidity_entity["coordinator_name"] == _DEVICE_COORDINATOR_NAME
    assert humidity_entity["sensors"] == {
        "low_battery": humidity_component_leakage.get("LowBattery"),
        "humidity": humidity_component_leakage.get("Humidity"),
    }


async def test_async_update_data_should_reset_count_failed_update_on_success(
    hass: HomeAssistant,
):
    # Prepare
    panel_info: PanelInfo = {
        "PanelId": "1234",
        "PanelCodeLength": 4,
        "QuickArmEnabled": True,
        "CanPartialArm": False,
        "Locks": [],
        "Smartplugs": [],
        "Temperatures": [],
        "Capabilities": [],
    }
    smart_plug: SmartPlug = {
        "Id": "plug_1",
        "Label": "Living Room Plug",
        "Serial": "PLUG_SERIAL",
        "SerialNo": "PLUG_SERIAL",
        "Status": "On",
    }
    alarm_panel: PanelStatus = {
        "IsOnline": True,
        "Status": 1,
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.SMART_PLUG_STATUS: APIResponse(
            response_code=200, response_is_json=True, response_data=[smart_plug]
        ),
        DataEndpointType.PANEL_STATUS: APIResponse(
            response_code=200, response_is_json=True, response_data=alarm_panel
        ),
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    # Set previous data with one temperature sensor
    device: dict[str, Any] = {}
    device = {
        "serial_no": smart_plug["SerialNo"],
        "entities": {
            "Smart Plug": {
                "name": smart_plug["Label"],
                "id": smart_plug["Id"],
                "sensors": {
                    "plug_status": smart_plug["Status"],
                },
                "model": "Smart Plug",
                "failed_update_count": 3,
            }
        },
    }
    device_registry.register_device(device)
    device_coordinator.data = {"device_registry": device_registry}

    # Act
    coordinator_data = await device_coordinator._async_update_data()

    # Assert
    assert device_coordinator.is_healthy()
    assert "device_registry" in coordinator_data
    device_registry: DeviceRegistry = coordinator_data["device_registry"]
    devices: dict[str, Any] = device_registry.fetch_devices()

    plug = devices["PLUG_SERIAL"]["entities"]["Smart Plug"]
    assert plug["name"] == smart_plug["Label"]
    assert plug["id"] == smart_plug["Id"]
    assert plug["sensors"] == {"plug_status": smart_plug.get("Status")}
    assert plug["model"] == "Smart Plug"
    assert plug["last_updated"]
    assert "failed_update_count" not in plug

    panel = devices["1234"]["entities"]["Alarm panel"]
    assert panel["name"] == "Alarm Control Panel"
    assert panel["sensors"] == {
        "online": alarm_panel.get("IsOnline"),
        "alarm_status": alarm_panel.get("Status"),
    }
    assert panel["model"] == "Alarm panel"
    assert panel["panel_code_length"] == 4
    assert panel["panel_quick_arm"]
    assert not panel["panel_partial_arm"]
    assert panel["last_updated"]
    assert "failed_update_count" not in panel


async def test_async_update_data_should_increment_coordinator_update_error_counter_on_exception_failure(
    hass: HomeAssistant,
):
    # Prepare
    panel_info: PanelInfo = {
        "PanelId": "1234",
        "PanelCodeLength": 6,
        "QuickArmEnabled": True,
        "CanPartialArm": True,
        "Locks": [],
        "Smartplugs": [],
        "Temperatures": [],
        "Capabilities": [],
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.side_effect = ApiError("Failed To Call API")

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    device_coordinator._update_error_counter = 3
    # Act
    with pytest.raises(
        UpdateFailed,
        match="Failed To Call API",
    ):
        await device_coordinator._async_update_data()

    # Assert
    assert not device_coordinator.is_healthy()
    assert device_coordinator._update_error_counter == 4


async def test_async_update_data_should_count_failed_update_on_failure(
    hass: HomeAssistant,
):
    # Prepare
    panel_info: PanelInfo = {
        "PanelId": "1234",
        "PanelCodeLength": 4,
        "QuickArmEnabled": True,
        "CanPartialArm": False,
        "Locks": [],
        "Smartplugs": [],
        "Temperatures": [],
        "Capabilities": [],
    }
    smart_plug: SmartPlug = {
        "Id": "plug_1",
        "Label": "Living Room Plug",
        "Serial": "PLUG_SERIAL",
        "SerialNo": "PLUG_SERIAL",
        "Status": "On",
    }
    alarm_panel: PanelStatus = {
        "IsOnline": True,
        "Status": 1,
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.SMART_PLUG_STATUS: APIResponse(
            response_code=200, response_is_json=False, response_data=None
        ),
        DataEndpointType.PANEL_STATUS: APIResponse(
            response_code=200, response_is_json=True, response_data=alarm_panel
        ),
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )
    # Set previous data with one temperature sensor
    device: dict[str, Any] = {}
    device = {
        "serial_no": smart_plug["SerialNo"],
        "entities": {
            "Smart Plug": {
                "name": smart_plug["Label"],
                "id": smart_plug["Id"],
                "sensors": {
                    "plug_status": smart_plug["Status"],
                },
                "model": "Smart Plug",
                "failed_update_count": 3,
            }
        },
    }
    device_registry.register_device(device)
    device_coordinator.data = {"device_registry": device_registry}

    # Act
    coordinator_data = await device_coordinator._async_update_data()

    # Assert
    assert "device_registry" in coordinator_data
    device_registry: DeviceRegistry = coordinator_data["device_registry"]
    devices: dict[str, Any] = device_registry.fetch_devices()

    plug = devices["PLUG_SERIAL"]["entities"]["Smart Plug"]
    assert plug["name"] == smart_plug["Label"]
    assert plug["id"] == smart_plug["Id"]
    assert plug["sensors"] == {"plug_status": smart_plug.get("Status")}
    assert plug["model"] == "Smart Plug"
    assert plug["failed_update_count"] == 4

    panel = devices["1234"]["entities"]["Alarm panel"]
    assert panel["name"] == "Alarm Control Panel"
    assert panel["sensors"] == {
        "online": alarm_panel.get("IsOnline"),
        "alarm_status": alarm_panel.get("Status"),
    }
    assert panel["model"] == "Alarm panel"
    assert panel["panel_code_length"] == 4
    assert panel["panel_quick_arm"]
    assert not panel["panel_partial_arm"]
    assert "failed_update_count" not in panel


async def test_async_update_data_should_not_proccess_empty_or_failed_PanelInfo_devices(
    hass: HomeAssistant,
):
    # Prepare
    panel_info: PanelInfo = {
        "PanelId": "1234",
        "PanelCodeLength": 6,
        "QuickArmEnabled": True,
        "CanPartialArm": True,
        "Locks": [],
        "Smartplugs": [],
        "Temperatures": [],
        "Capabilities": [],
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.SMART_PLUG_STATUS: APIResponse(
            response_code=200, response_is_json=True, response_data=[]
        ),
        DataEndpointType.LOCK_STATUS: APIResponse(
            response_code=200, response_is_json=False, response_data=["some-response"]
        ),
        DataEndpointType.PANEL_STATUS: APIResponse(
            response_code=500, response_is_json=True, response_data=None
        ),
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )

    # Act
    coordinator_data = await device_coordinator._async_update_data()

    # Assert
    assert "device_registry" in coordinator_data
    device_registry: DeviceRegistry = coordinator_data["device_registry"]
    assert device_registry.fetch_devices() == {}


async def test_async_update_data_should_proccess_log_events(
    hass: HomeAssistant,
):
    # Prepare
    panel_info: PanelInfo = {
        "PanelId": "1234",
        "PanelCodeLength": 6,
        "QuickArmEnabled": True,
        "CanPartialArm": True,
        "Locks": [],
        "Smartplugs": [],
        "Temperatures": [],
        "Capabilities": [],
    }
    smart_lock: Lock = {
        "Label": "ABC",
        "Serial": "LOCK_SERIAL",
        "SerialNo": "LOCK_SERIAL",
        "Status": "unlock",
        "BatteryLow": False,
    }
    log_records: LogRecords = {
        "Records": [
            {
                "User": "Kod",
                "Channel": "App",
                "Time": "2025-12-13T23:31:03Z",
                "EventType": "armed",
                "LockName": "",
            },
            {
                "User": "Kod",
                "Channel": "App",
                "Time": "2025-12-13T23:30:44Z",
                "EventType": "disarmed",
                "LockName": "",
            },
            {
                "User": "Kod",
                "Channel": "App",
                "Time": "2025-12-13T23:29:42Z",
                "EventType": "armed",
                "LockName": "",
            },
            {
                "User": "Kod",
                "Channel": "App",
                "Time": "2025-12-13T23:25:13Z",
                "EventType": "unlock",
                "LockName": "ABC",
            },
            {
                "User": "Kod",
                "Channel": "App",
                "Time": "2025-10-19T01:49:40Z",
                "EventType": "lock",
                "LockName": "ABC",
            },
        ]
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.LOCK_STATUS: APIResponse(
            response_code=200, response_is_json=True, response_data=[smart_lock]
        ),
        DataEndpointType.LOGS: APIResponse(
            response_code=200, response_is_json=True, response_data=log_records
        ),
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )

    # Act
    coordinator_data = await device_coordinator._async_update_data()

    # Assert
    assert "logs" in coordinator_data

    # TODO, re-write log event proccess an add assert


async def test_async_update_data_should_raise_ConfigEntryAuthFailed_exception_on_LoginError(
    hass: HomeAssistant,
):
    # Prepare
    panel_info: PanelInfo = {
        "PanelId": "1234",
        "PanelCodeLength": 6,
        "QuickArmEnabled": True,
        "CanPartialArm": True,
        "Locks": [],
        "Smartplugs": [],
        "Temperatures": [],
        "Capabilities": [],
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.side_effect = LoginError("Failed To Login User")

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    device_registry = DeviceRegistry()
    device_coordinator = SectorDeviceDataUpdateCoordinator(
        hass=hass,
        entry=mock_entity,
        sector_api=mock_api,
        panel_info_coordinator=mock_panel_info_coordinator,
        device_registry=device_registry,
        coordinator_name=_DEVICE_COORDINATOR_NAME,
        optional_endpoints=_OPTIONAL_ENDPOINTS,
        mandatory_endpoints=_MANDATORY_ENDPOINTS,
    )

    # Act & Assert
    with pytest.raises(
        ConfigEntryAuthFailed,
        match="Failed To Login User",
    ):
        await device_coordinator._async_update_data()
