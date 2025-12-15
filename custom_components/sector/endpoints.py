"""Sector Alarm API endpoints."""
from enum import Enum

API_URL = "https://mypagesapi.sectoralarm.net"

class DataEndpointType(Enum):
    LOGS = "Logs"
    PANEL_STATUS = "Panel Status"
    SMART_PLUG_STATUS = "Smart Plug Status",
    LOCK_STATUS = "Lock Status",
    HUMIDITY = "Humidity",
    DOORS_AND_WINDOWS = "Doors and Windows",
    LEAKAGE_DETECTORS = "Leakage Detectors",
    SMOKE_DETECTORS = "Smoke Detectors",
    CAMERAS = "Cameras",
    TEMPERATURES = "Temperatures",
    TEMPERATURES_LEGACY = "Temperatures"

class ActionEndpointType(Enum):
    LOGIN = "Login",
    LOGOUT = "Logout",
    UNLOCK = "Unlock",
    LOCK = "Lock",
    ARM = "Arm",
    PARTIAL_ARM = "Partial Arm",
    DISARM = "Disarm",
    TURN_OFF_SMART_PLUG = "Turn off Smart Plug",
    TURN_ON_SMART_PLUG = "Turn on Smart Plug"

OPTIONAL_DATA_ENDPOINT_TYPES = {
    # via HouseCheck API
    DataEndpointType.TEMPERATURES,
    DataEndpointType.HUMIDITY,
    DataEndpointType.LEAKAGE_DETECTORS,
    DataEndpointType.SMOKE_DETECTORS,
    DataEndpointType.DOORS_AND_WINDOWS,
    DataEndpointType.CAMERAS,
    # via legacy
    DataEndpointType.TEMPERATURES_LEGACY,
    DataEndpointType.LOCK_STATUS,
    DataEndpointType.SMART_PLUG_STATUS,
}

MANDATORY_DATA_ENDPOINT_TYPES = {
    DataEndpointType.PANEL_STATUS,
    DataEndpointType.LOGS
}

class DataEndpoint:
    def __init__(self, type: DataEndpointType, method: str, uri: str) -> None:
        self._endpoint_type = type
        self._method = method
        self._uri = uri

    def __str__(self):
        return f"DataEndpoint(endpoint_type={self._endpoint_type}, method={self._method}, uri={self._uri})"

    def uri(self, panel_id: str) -> str:
        return self._uri.format(panelId=panel_id)

    def method(self) -> str:
        return self._method

    def type(self) -> DataEndpointType:
        return self._endpoint_type

class ActionEndpoint:
    def __init__(self, type: ActionEndpointType, method: str, uri: str) -> None:
        self._endpoint_type = type
        self._method = method
        self._uri = uri

    def __str__(self):
        return f"ActionEndpoint(endpoint_type={self._endpoint_type}, method={self._method}, uri={self._uri})"

    def uri(self) -> str:
        return self._uri

    def method(self) -> str:
        return self._method

    def type(self) -> ActionEndpointType:
        return self._endpoint_type

DATA_ENDPOINTS: set[DataEndpoint] = {
    DataEndpoint(
        type=DataEndpointType.LOGS,
        method="GET",
        uri=f"{API_URL}/api/v2/panel/logs?panelid={{panelId}}&pageNumber=1&pageSize=5"
    ),
    DataEndpoint(
        type=DataEndpointType.PANEL_STATUS,
        method="GET",
        uri=f"{API_URL}/api/panel/GetPanelStatus?panelId={{panelId}}"
    ),
    DataEndpoint(
        type=DataEndpointType.SMART_PLUG_STATUS,
        method="GET",
        uri=f"{API_URL}/api/panel/GetSmartplugStatus?panelId={{panelId}}"
    ),
    DataEndpoint(
        type=DataEndpointType.LOCK_STATUS,
        method="GET",
        uri=f"{API_URL}/api/panel/GetLockStatus?panelId={{panelId}}"
    ),
    DataEndpoint(
        type=DataEndpointType.TEMPERATURES_LEGACY,
        method="GET",
        uri=f"{API_URL}/api/Panel/GetTemperatures?panelId={{panelId}}"
    ),
    DataEndpoint(
        type=DataEndpointType.TEMPERATURES,
        method="POST",
        uri=f"{API_URL}/api/v2/housecheck/temperatures"
    ),
    DataEndpoint(
        type=DataEndpointType.HUMIDITY,
        method="GET",
        uri=f"{API_URL}/api/housecheck/panels/{{panelId}}/humidity"
    ),
    DataEndpoint(
        type=DataEndpointType.DOORS_AND_WINDOWS,
        method="POST",
        uri=f"{API_URL}/api/v2/housecheck/doorsandwindows"
    ),
    DataEndpoint(
        type=DataEndpointType.LEAKAGE_DETECTORS,
        method="POST",
        uri=f"{API_URL}/api/v2/housecheck/leakagedetectors"
    ),
    DataEndpoint(
        type=DataEndpointType.SMOKE_DETECTORS,
        method="POST",
        uri=f"{API_URL}/api/v2/housecheck/smokedetectors"
    ),
    DataEndpoint(
        type=DataEndpointType.CAMERAS,
        method="GET",
        uri=f"{API_URL}/api/v2/housecheck/cameras/{{panelId}}"
    )
}

ACTION_ENDPOINTS: set[ActionEndpoint] = {
    ActionEndpoint(
        type=ActionEndpointType.LOGIN,
        method="POST",
        uri=f"{API_URL}/api/Login/Login"
    ),
    ActionEndpoint(
        type=ActionEndpointType.LOGOUT,
        method="POST",
        uri=f"{API_URL}/api/Login/Logout"
    ),
    ActionEndpoint(
        type=ActionEndpointType.UNLOCK,
        method="POST",
        uri=f"{API_URL}/api/Panel/Unlock"
    ),
    ActionEndpoint(
        type=ActionEndpointType.LOCK,
        method="POST",
        uri=f"{API_URL}/api/Panel/Lock"
    ),
    ActionEndpoint(
        type=ActionEndpointType.ARM,
        method="POST",
        uri=f"{API_URL}/api/Panel/Arm"
    ),
    ActionEndpoint(
        type=ActionEndpointType.PARTIAL_ARM,
        method="POST",
        uri=f"{API_URL}/api/Panel/PartialArm"
    ),
    ActionEndpoint(
        type=ActionEndpointType.DISARM,
        method="POST",
        uri=f"{API_URL}/api/Panel/Disarm"
    ),
    ActionEndpoint(
        type=ActionEndpointType.TURN_OFF_SMART_PLUG,
        method="POST",
        uri=f"{API_URL}/api/Panel/TurnOffSmartplug"
    ),
    ActionEndpoint(
        type=ActionEndpointType.TURN_ON_SMART_PLUG,
        method="POST",
        uri=f"{API_URL}/api/Panel/TurnOnSmartplug"
    )
}

def fetch_data_endpoints(types: set[DataEndpointType]) -> set[DataEndpoint]:
    result: set[DataEndpoint] = {e for e in DATA_ENDPOINTS if e.type() in types}
    return result

def fetch_action_endpoint(type: ActionEndpointType) -> ActionEndpoint:
    for endpoint in ACTION_ENDPOINTS:
        if endpoint.type() == type:
            return endpoint
    raise NotImplementedError(f"Unsupported endpoint type {type}")