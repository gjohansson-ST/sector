from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.sector.api_model import (
    Component,
    PanelInfo,
    Temperature,
)
from custom_components.sector.client import APIResponse, LoginError
from custom_components.sector.coordinator import (
    SectorSensorDataUpdateCoordinator,
)
from custom_components.sector.endpoints import DataEndpointType

_PANEL_ID = "1234"

temperature: Temperature = {
    "Label": "Living Room",
    "Serial": "TEMP_SERIAL_LEGACY",
    "SerialNo": "TEMP_SERIAL_LEGACY",
    "Temperature": "22.5",
}

panel_info: PanelInfo = {
    "PanelId": "1234",
    "PanelCodeLength": 6,
    "QuickArmEnabled": True,
    "CanPartialArm": True,
    "Locks": [],
    "Smartplugs": [],
    "Temperatures": [temperature],
}

# HouseCheck
# Note that these test parameters are made up (logically based on the names)
# as the HouseCheck API is not fully understood
temperature_component: Component = {
    "SerialNo": "TEMP_SERIAL",
    "Serial": "TEMP_SERIAL",
    "Label": "Kitchen",
    "Name": "Kitchen Temperature",
    "Type": "Temperatures",
    "Temperature": 21.5,
    "Humidity": None,
    "Closed": None,
    "LowBattery": None,
    "BatteryLow": None,
    "Alarm": None,
}
humidity_component: Component = {
    "SerialNo": "HUM_SERIAL",
    "Serial": "HUM_SERIAL",
    "Label": "Kitchen",
    "Name": "Kitchen Humidity",
    "Type": "Humidity",
    "Humidity": 45.0,
    "Temperature": None,
    "Closed": None,
    "LowBattery": None,
    "BatteryLow": None,
    "Alarm": None,
}
door_and_window_detector_component: Component = {
    "SerialNo": "DOOR_SERIAL",
    "Serial": "DOOR_SERIAL",
    "Label": "Front Door",
    "Name": "Front Door Lock",
    "Type": "Doors and Windows",
    "Closed": True,
    "LowBattery": False,
    "BatteryLow": None,
    "Alarm": None,
    "Temperature": None,
    "Humidity": None,
}
smoke_detector_component: Component = {
    "SerialNo": "SMOKE_SERIAL",
    "Serial": "SMOKE_SERIAL",
    "Label": "Entrance Smoke Detector",
    "Name": "Entrance Smoke Detector Sensor",
    "Type": "Smoke Detector",
    "BatteryLow": False,
    "Alarm": False,
    "Closed": None,
    "LowBattery": None,
    "Temperature": None,
    "Humidity": None,
}
leakage_detector_component: Component = {
    "SerialNo": "LEAK_SERIAL",
    "Serial": "LEAK_SERIAL",
    "Label": "Bathroom leak detector",
    "Name": "Bathroom leak Sensor",
    "Type": "Leakage Detectors",
    "BatteryLow": False,
    "Alarm": False,
    "Closed": None,
    "LowBattery": None,
    "Temperature": None,
    "Humidity": None,
}


def _create_mock_config_entity() -> MockConfigEntry:
    return MockConfigEntry(
        domain="sector",
        title="Test Panel",
        data={"panel_id": _PANEL_ID, "username": "abc", "password": "xyz"},
        entry_id="test123",
    )


def _create_mock_sector_panel_info(panel_info: PanelInfo | None) -> AsyncMock:
    coordinator_mock = AsyncMock()
    coordinator_mock.data = {"panel_info": panel_info}
    return coordinator_mock


async def test_async_setup_should_calculate_supported_optional_endpoints_from_PanelInfo_and_HouseCheck(
    hass: HomeAssistant,
):
    # Prepare
    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.DOORS_AND_WINDOWS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [
                    {"Places": [{"Components": [door_and_window_detector_component]}]}
                ]
            },
        ),
        DataEndpointType.LEAKAGE_DETECTORS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [leakage_detector_component]}]}]
            },
        ),
        DataEndpointType.TEMPERATURES: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [temperature_component]}]}]
            },
        ),
        DataEndpointType.HUMIDITY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={"Floors": [{"Rooms": [{"Devices": [humidity_component]}]}]},
        ),
        DataEndpointType.SMOKE_DETECTORS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [smoke_detector_component]}]}]
            },
        ),
        DataEndpointType.CAMERAS: APIResponse(
            response_code=404, response_is_json=False, response_data=None
        ),
    }

    sensor_coordinator = SectorSensorDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act
    await sensor_coordinator._async_setup()

    # Assert
    # Redacted unsupported endpoints by Sector App
    assert sensor_coordinator._use_legacy_api
    assert sensor_coordinator._data_endpoints == {
        DataEndpointType.TEMPERATURES_LEGACY,
        # DataEndpointType.TEMPERATURES,
        DataEndpointType.HUMIDITY,
        # DataEndpointType.LEAKAGE_DETECTORS,
        # DataEndpointType.SMOKE_DETECTORS,
        DataEndpointType.DOORS_AND_WINDOWS,
    }


async def test_async_setup_should_not_use_legacy_api_temperatures_if_not_defined_in_PanelInfo(
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
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {}

    sensor_coordinator = SectorSensorDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act
    await sensor_coordinator._async_setup()

    # Assert
    assert not sensor_coordinator._use_legacy_api


async def test_async_setup_should_raise_UpdateFailed_when_none_PanelInfo(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_panel_info_coordinator = _create_mock_sector_panel_info(None)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    sensor_coordinator = SectorSensorDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act & Assert
    with pytest.raises(
        UpdateFailed,
        match=f"Failed to retrieve panel information for panel '{_PANEL_ID}' \\(no data returned from coordinator\\)",
    ):
        await sensor_coordinator._async_setup()


async def test_async_update_data_should_proccess_PanelInfo_and_HouseCheck_devices(
    hass: HomeAssistant,
):
    # Prepare
    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.TEMPERATURES_LEGACY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data=[temperature],
        ),
        DataEndpointType.DOORS_AND_WINDOWS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [
                    {"Places": [{"Components": [door_and_window_detector_component]}]}
                ]
            },
        ),
        DataEndpointType.LEAKAGE_DETECTORS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [leakage_detector_component]}]}]
            },
        ),
        DataEndpointType.TEMPERATURES: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [temperature_component]}]}]
            },
        ),
        DataEndpointType.HUMIDITY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={"Floors": [{"Rooms": [{"Devices": [humidity_component]}]}]},
        ),
        DataEndpointType.SMOKE_DETECTORS: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={
                "Sections": [{"Places": [{"Components": [smoke_detector_component]}]}]
            },
        ),
    }

    sensor_coordinator = SectorSensorDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act
    coordinator_data = await sensor_coordinator._async_update_data()

    # Assert
    assert "devices" in coordinator_data

    temp_legacy = coordinator_data["devices"]["TEMP_SERIAL_LEGACY"]
    assert temp_legacy["name"] == temperature["Label"]
    assert temp_legacy["serial_no"] == temperature["SerialNo"]
    assert temp_legacy["sensors"] == {"temperature": temperature["Temperature"]}
    assert temp_legacy["model"] == "Temperature Sensor (legacy)"
    assert "failed_update_count" not in temp_legacy

    temp = coordinator_data["devices"]["TEMP_SERIAL"]
    assert temp["name"] == temperature_component["Label"]
    assert temp["serial_no"] == temperature_component["SerialNo"]
    assert temp["sensors"] == {"temperature": temperature_component["Temperature"]}
    assert temp["model"] == "Temperature Sensor"
    assert "failed_update_count" not in temp

    humidity = coordinator_data["devices"]["HUM_SERIAL"]
    assert humidity["name"] == humidity_component["Label"]
    assert humidity["serial_no"] == humidity_component["SerialNo"]
    assert humidity["sensors"] == {"humidity": humidity_component["Humidity"]}
    assert humidity["model"] == "Humidity Sensor"
    assert "failed_update_count" not in humidity

    door = coordinator_data["devices"]["DOOR_SERIAL"]
    assert door["name"] == door_and_window_detector_component["Label"]
    assert door["serial_no"] == door_and_window_detector_component["SerialNo"]
    assert door["sensors"] == {
        "low_battery": door_and_window_detector_component.get("LowBattery"),
        "closed": door_and_window_detector_component.get("Closed"),
    }
    assert door["model"] == "Door/Window Sensor"
    assert "failed_update_count" not in door

    smoke = coordinator_data["devices"]["SMOKE_SERIAL"]
    assert smoke["name"] == smoke_detector_component["Label"]
    assert smoke["serial_no"] == smoke_detector_component["SerialNo"]
    assert smoke["sensors"] == {
        "alarm": smoke_detector_component.get("Alarm"),
        "low_battery": smoke_detector_component.get("BatteryLow"),
    }
    assert smoke["model"] == "Smoke Detector"
    assert "failed_update_count" not in smoke

    leakage = coordinator_data["devices"]["LEAK_SERIAL"]
    assert leakage["name"] == leakage_detector_component["Label"]
    assert leakage["serial_no"] == leakage_detector_component["SerialNo"]
    assert leakage["sensors"] == {
        "alarm": leakage_detector_component.get("Alarm"),
        "low_battery": leakage_detector_component.get("BatteryLow"),
    }
    assert leakage["model"] == "Leakage Detector"
    assert "failed_update_count" not in leakage


async def test_async_update_data_should_not_proccess_empty_or_failed_devices(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.TEMPERATURES: APIResponse(
            response_code=200, response_is_json=True, response_data=[]
        ),
        DataEndpointType.HUMIDITY: APIResponse(
            response_code=200, response_is_json=False, response_data=["some-response"]
        ),
        DataEndpointType.TEMPERATURES_LEGACY: APIResponse(
            response_code=404, response_is_json=True, response_data=[]
        ),
        DataEndpointType.SMOKE_DETECTORS: APIResponse(
            response_code=500, response_is_json=True, response_data=None
        ),
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    sensor_coordinator = SectorSensorDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act
    coordinator_data = await sensor_coordinator._async_update_data()

    # Assert
    assert "devices" in coordinator_data
    assert coordinator_data["devices"] == {}


async def test_async_update_data_should_count_failed_update_on_failure(
    hass: HomeAssistant,
):
    # Prepare
    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.TEMPERATURES_LEGACY: APIResponse(
            response_code=500,
            response_is_json=True,
            response_data=None,
        ),
        DataEndpointType.HUMIDITY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={"Floors": [{"Rooms": [{"Devices": [humidity_component]}]}]},
        ),
    }

    sensor_coordinator = SectorSensorDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )
    # Set previous data with one temperature sensor
    sensor_coordinator.data = {"devices": {}}
    sensor_coordinator.data["devices"]["TEMP_SERIAL_LEGACY"] = {
        "name": temperature["Label"],
        "serial_no": temperature["SerialNo"],
        "sensors": {
            "temperature": temperature["Temperature"],
        },
        "model": "Temperature Sensor (legacy)",
        "failed_update_count": 3
    }

    # Act
    coordinator_data = await sensor_coordinator._async_update_data()

    # Assert
    assert "devices" in coordinator_data

    temp_legacy = coordinator_data["devices"]["TEMP_SERIAL_LEGACY"]
    assert temp_legacy["name"] == temperature["Label"]
    assert temp_legacy["serial_no"] == temperature["SerialNo"]
    assert temp_legacy["sensors"] == {"temperature": temperature["Temperature"]}
    assert temp_legacy["model"] == "Temperature Sensor (legacy)"
    assert temp_legacy["failed_update_count"] == 4

    humidity = coordinator_data["devices"]["HUM_SERIAL"]
    assert humidity["name"] == humidity_component["Label"]
    assert humidity["serial_no"] == humidity_component["SerialNo"]
    assert humidity["sensors"] == {"humidity": humidity_component["Humidity"]}
    assert humidity["model"] == "Humidity Sensor"
    assert "failed_update_count" not in humidity

async def test_async_update_data_should_reset_count_failed_update_on_success(
    hass: HomeAssistant,
):
    # Prepare
    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.TEMPERATURES_LEGACY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data=[temperature],
        ),
        DataEndpointType.HUMIDITY: APIResponse(
            response_code=200,
            response_is_json=True,
            response_data={"Floors": [{"Rooms": [{"Devices": [humidity_component]}]}]},
        ),
    }

    sensor_coordinator = SectorSensorDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )
    # Set previous data with one temperature sensor
    sensor_coordinator.data = {"devices": {}}
    sensor_coordinator.data["devices"]["TEMP_SERIAL_LEGACY"] = {
        "name": temperature["Label"],
        "serial_no": temperature["SerialNo"],
        "sensors": {
            "temperature": temperature["Temperature"],
        },
        "model": "Temperature Sensor (legacy)",
        "failed_update_count": 3,
    }

    # Act
    coordinator_data = await sensor_coordinator._async_update_data()

    # Assert
    assert "devices" in coordinator_data

    temp_legacy = coordinator_data["devices"]["TEMP_SERIAL_LEGACY"]
    assert temp_legacy["name"] == temperature["Label"]
    assert temp_legacy["serial_no"] == temperature["SerialNo"]
    assert temp_legacy["sensors"] == {"temperature": temperature["Temperature"]}
    assert temp_legacy["model"] == "Temperature Sensor (legacy)"
    assert "failed_update_count" not in temp_legacy

    humidity = coordinator_data["devices"]["HUM_SERIAL"]
    assert humidity["name"] == humidity_component["Label"]
    assert humidity["serial_no"] == humidity_component["SerialNo"]
    assert humidity["sensors"] == {"humidity": humidity_component["Humidity"]}
    assert humidity["model"] == "Humidity Sensor"
    assert "failed_update_count" not in humidity

async def test_async_update_data_should_raise_ConfigEntryAuthFailed_exception_on_LoginError(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()
    mock_api.retrieve_all_data.side_effect = LoginError("Failed To Login User")

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    sensor_coordinator = SectorSensorDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act & Assert
    with pytest.raises(
        ConfigEntryAuthFailed,
        match="Failed To Login User",
    ):
        await sensor_coordinator._async_update_data()
