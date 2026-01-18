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
    Lock,
    LogRecords,
    PanelInfo,
    SmartPlug,
    Temperature,
    PanelStatus,
)
from custom_components.sector.client import APIResponse, ApiError, LoginError
from custom_components.sector.coordinator import (
    SectorActionDataUpdateCoordinator,
)
from custom_components.sector.endpoints import DataEndpointType

_PANEL_ID = "1234"


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


async def test_async_setup_should_calculate_supported_optional_endpoints_from_PanelInfo(
    hass: HomeAssistant,
):
    # Prepare
    lock: Lock = {
        "Label": "Front Door",
        "Serial": "LOCK123",
        "SerialNo": "LOCK123",
        "Status": "lock",
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
    }
    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act
    await action_coordinator._async_setup()

    # Assert
    assert action_coordinator._data_endpoints == {
        DataEndpointType.LOCK_STATUS,
        DataEndpointType.SMART_PLUG_STATUS,
        DataEndpointType.PANEL_STATUS,
        DataEndpointType.DOORS_AND_WINDOWS,
        DataEndpointType.LOGS,
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
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.DOORS_AND_WINDOWS: APIResponse(
            response_code=404,
            response_is_json=False,
            response_data=None,
        ),
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act
    await action_coordinator._async_setup()

    # Assert
    assert action_coordinator._data_endpoints == {
        DataEndpointType.PANEL_STATUS,
        DataEndpointType.LOGS,
    }


async def test_async_setup_should_raise_UpdateFailed_when_none_PanelInfo(
    hass: HomeAssistant,
):
    # Prepare
    mock_api = AsyncMock()

    mock_panel_info_coordinator = _create_mock_sector_panel_info(None)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act & Assert
    with pytest.raises(
        UpdateFailed,
        match=f"Failed to retrieve panel information for panel '{_PANEL_ID}' \\(no data returned from coordinator\\)",
    ):
        await action_coordinator._async_setup()


async def test_async_update_data_should_proccess_PanelInfo_and_HouseCheck_devices(
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
    }
    smart_plug: SmartPlug = {
        "Id": "plug_1",
        "Label": "Living Room Plug",
        "Serial": "PLUG_SERIAL",
        "SerialNo": "PLUG_SERIAL",
        "Status": "On",
    }
    smart_lock: Lock = {
        "Label": "Front Door",
        "Serial": "LOCK_SERIAL",
        "SerialNo": "LOCK_SERIAL",
        "Status": "lock",
    }
    alarm_panel: PanelStatus = {
        "IsOnline": True,
        "ReadyToArm": True,
        "Status": 1,
        "AnnexStatus": 0,
        "PanelTimeZoneOffset": 0,
        "StatusTime": "unused",
        "StatusTimeUtc": "unused",
        "TimeZoneName": "unused",
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

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.return_value = {
        DataEndpointType.SMART_PLUG_STATUS: APIResponse(
            response_code=200, response_is_json=True, response_data=[smart_plug]
        ),
        DataEndpointType.LOCK_STATUS: APIResponse(
            response_code=200, response_is_json=True, response_data=[smart_lock]
        ),
        DataEndpointType.PANEL_STATUS: APIResponse(
            response_code=200, response_is_json=True, response_data=alarm_panel
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
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act
    coordinator_data = await action_coordinator._async_update_data()

    # Assert
    assert "devices" in coordinator_data

    lock = coordinator_data["devices"]["LOCK_SERIAL"]
    assert lock["name"] == smart_lock["Label"]
    assert lock["serial_no"] == smart_lock["SerialNo"]
    assert lock["sensors"] == {
        "lock_status": smart_lock.get("Status"),
    }
    assert lock["model"] == "Smart Lock"

    plug = coordinator_data["devices"]["PLUG_SERIAL"]
    assert plug["name"] == smart_plug["Label"]
    assert plug["id"] == smart_plug["Id"]
    assert plug["serial_no"] == smart_plug["SerialNo"]
    assert plug["sensors"] == {"plug_status": smart_plug.get("Status")}
    assert plug["model"] == "Smart Plug"

    panel = coordinator_data["devices"]["alarm_panel"]
    assert panel["name"] == "Alarm Control Panel"
    assert panel["serial_no"] == _PANEL_ID
    assert panel["sensors"] == {
        "online": alarm_panel.get("IsOnline"),
        "alarm_status": alarm_panel.get("Status"),
    }
    assert panel["model"] == "Sector Alarm Control Panel"
    assert panel["panel_code_length"] == 4
    assert panel["panel_quick_arm"]
    assert not panel["panel_partial_arm"]

    door = coordinator_data["devices"]["DOOR_SERIAL"]
    assert door["name"] == door_and_window_detector_component["Label"]
    assert door["serial_no"] == door_and_window_detector_component["SerialNo"]
    assert door["sensors"] == {
        "low_battery": door_and_window_detector_component.get("LowBattery"),
        "closed": door_and_window_detector_component.get("Closed"),
    }
    assert door["model"] == "Door/Window Sensor"
    assert door["last_updated"]
    assert "failed_update_count" not in door


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
        "ReadyToArm": True,
        "Status": 1,
        "AnnexStatus": 0,
        "PanelTimeZoneOffset": 0,
        "StatusTime": "unused",
        "StatusTimeUtc": "unused",
        "TimeZoneName": "unused",
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

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )
    # Set previous data with one temperature sensor
    action_coordinator.data = {"devices": {}}
    action_coordinator.data["devices"]["PLUG_SERIAL"] = {
        "name": smart_plug["Label"],
        "id": smart_plug["Id"],
        "serial_no": smart_plug["SerialNo"],
        "sensors": {
            "plug_status": smart_plug["Status"],
        },
        "model": "Smart Plug",
        "failed_update_count": 3,
    }

    # Act
    coordinator_data = await action_coordinator._async_update_data()

    # Assert
    assert action_coordinator.is_healthy()
    assert "devices" in coordinator_data

    plug = coordinator_data["devices"]["PLUG_SERIAL"]
    assert plug["name"] == smart_plug["Label"]
    assert plug["id"] == smart_plug["Id"]
    assert plug["serial_no"] == smart_plug["SerialNo"]
    assert plug["sensors"] == {"plug_status": smart_plug.get("Status")}
    assert plug["model"] == "Smart Plug"
    assert plug["last_updated"]
    assert "failed_update_count" not in plug

    panel = coordinator_data["devices"]["alarm_panel"]
    assert panel["name"] == "Alarm Control Panel"
    assert panel["serial_no"] == _PANEL_ID
    assert panel["sensors"] == {
        "online": alarm_panel.get("IsOnline"),
        "alarm_status": alarm_panel.get("Status"),
    }
    assert panel["model"] == "Sector Alarm Control Panel"
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
    }

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.side_effect = ApiError("Failed To Call API")

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )
    action_coordinator._update_error_counter = 3
    # Act
    with pytest.raises(
        UpdateFailed,
        match="Failed To Call API",
    ):
        await action_coordinator._async_update_data()

    # Assert
    assert not action_coordinator.is_healthy()
    assert action_coordinator._update_error_counter == 4


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
        "ReadyToArm": True,
        "Status": 1,
        "AnnexStatus": 0,
        "PanelTimeZoneOffset": 0,
        "StatusTime": "unused",
        "StatusTimeUtc": "unused",
        "TimeZoneName": "unused",
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

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )
    # Set previous data with one temperature sensor
    action_coordinator.data = {"devices": {}}
    action_coordinator.data["devices"]["PLUG_SERIAL"] = {
        "name": smart_plug["Label"],
        "id": smart_plug["Id"],
        "serial_no": smart_plug["SerialNo"],
        "sensors": {
            "plug_status": smart_plug["Status"],
        },
        "model": "Smart Plug",
        "failed_update_count": 3,
    }

    # Act
    coordinator_data = await action_coordinator._async_update_data()

    # Assert
    assert "devices" in coordinator_data

    plug = coordinator_data["devices"]["PLUG_SERIAL"]
    assert plug["name"] == smart_plug["Label"]
    assert plug["id"] == smart_plug["Id"]
    assert plug["serial_no"] == smart_plug["SerialNo"]
    assert plug["sensors"] == {"plug_status": smart_plug.get("Status")}
    assert plug["model"] == "Smart Plug"
    assert plug["failed_update_count"] == 4

    panel = coordinator_data["devices"]["alarm_panel"]
    assert panel["name"] == "Alarm Control Panel"
    assert panel["serial_no"] == _PANEL_ID
    assert panel["sensors"] == {
        "online": alarm_panel.get("IsOnline"),
        "alarm_status": alarm_panel.get("Status"),
    }
    assert panel["model"] == "Sector Alarm Control Panel"
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

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act
    coordinator_data = await action_coordinator._async_update_data()

    # Assert
    assert "devices" in coordinator_data
    assert coordinator_data["devices"] == {}


async def test__async_update_data_should_proccess_log_events(
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
    smart_lock: Lock = {
        "Label": "ABC",
        "Serial": "LOCK_SERIAL",
        "SerialNo": "LOCK_SERIAL",
        "Status": "unlock",
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

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act
    coordinator_data = await action_coordinator._async_update_data()

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
    }

    mock_api = AsyncMock()
    mock_api.retrieve_all_data.side_effect = LoginError("Failed To Login User")

    mock_panel_info_coordinator = _create_mock_sector_panel_info(panel_info)
    mock_entity = _create_mock_config_entity()
    mock_entity.add_to_hass(hass)

    action_coordinator = SectorActionDataUpdateCoordinator(
        hass, mock_entity, mock_api, mock_panel_info_coordinator
    )

    # Act & Assert
    with pytest.raises(
        ConfigEntryAuthFailed,
        match="Failed To Login User",
    ):
        await action_coordinator._async_update_data()
