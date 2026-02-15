"""Sector Alarm API endpoints."""

from enum import Enum

API_URL = "https://mypagesapi.sectoralarm.net"


class DataEndpointType(Enum):
    LOGS = "Logs", True, False
    PANEL_STATUS = "Alarm panel", True, False
    SMART_PLUG_STATUS = "Smart Plug", True, False
    LOCK_STATUS = "Smart Lock", True, False
    DOOR_AND_WINDOW = "Door/Window Sensor", True, True
    LEAKAGE_DETECTOR = "Leakage Detector", True, True
    SMOKE_DETECTOR = "Smoke Detector", True, True
    CAMERAS = "Camera", True, True
    HUMIDITY = "Humidity Sensor", False, True
    TEMPERATURE = "Temperature Sensor V2", False, True
    TEMPERATURE_LEGACY = "Temperature Sensor", False, False

    def __new__(cls, *args, **kwds):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, _: str, is_device: bool, is_house_check_endpoint: bool):
        self._is_device = is_device
        self._is_house_check_endpoint = is_house_check_endpoint

    def __str__(self):
        return self.value

    @property
    def is_device(self):
        return self._is_device

    @property
    def is_house_check_endpoint(self):
        return self._is_house_check_endpoint


class ActionEndpointType(Enum):
    LOGIN = "Login"
    UNLOCK = "Unlock"
    LOCK = "Lock"
    ARM = "Arm"
    PARTIAL_ARM = "Partial Arm"
    DISARM = "Disarm"
    TURN_OFF_SMART_PLUG = "Turn off Smart Plug"
    TURN_ON_SMART_PLUG = "Turn on Smart Plug"


class DataEndpoint:
    def __init__(self, type: DataEndpointType, method: str, uri: str) -> None:
        self._endpoint_type = type
        self._method = method
        self._uri = uri

    def __str__(self) -> str:
        return f"DataEndpoint(type={self._endpoint_type}, method={self._method}, uri={self._uri})"

    def __repr__(self) -> str:
        return (
            f"DataEndpoint(type={self._endpoint_type!r}, "
            f"method={self._method!r}, uri={self._uri!r})"
        )

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

    def __str__(self) -> str:
        return f"ActionEndpoint(type={self._endpoint_type}, method={self._method}, uri={self._uri})"

    def __repr__(self) -> str:
        return (
            f"ActionEndpoint(type={self._endpoint_type!r}, "
            f"method={self._method!r}, uri={self._uri!r})"
        )

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
        uri=f"{API_URL}/api/v2/panel/logs?panelid={{panelId}}&pageNumber=1&pageSize=5",
    ),
    DataEndpoint(
        type=DataEndpointType.PANEL_STATUS,
        method="GET",
        uri=f"{API_URL}/api/panel/GetPanelStatus?panelId={{panelId}}",
    ),
    DataEndpoint(
        type=DataEndpointType.SMART_PLUG_STATUS,
        method="GET",
        uri=f"{API_URL}/api/panel/GetSmartplugStatus?panelId={{panelId}}",
    ),
    DataEndpoint(
        type=DataEndpointType.LOCK_STATUS,
        method="GET",
        uri=f"{API_URL}/api/panel/GetLockStatus?panelId={{panelId}}",
    ),
    DataEndpoint(
        type=DataEndpointType.TEMPERATURE_LEGACY,
        method="GET",
        uri=f"{API_URL}/api/Panel/GetTemperatures?panelId={{panelId}}",
    ),
    DataEndpoint(
        type=DataEndpointType.TEMPERATURE,  # Seems not be used by Sector App
        method="POST",
        uri=f"{API_URL}/api/housecheck/temperatures",
    ),
    DataEndpoint(
        type=DataEndpointType.HUMIDITY,
        method="GET",
        uri=f"{API_URL}/api/housecheck/panels/{{panelId}}/humidity",
    ),
    DataEndpoint(
        type=DataEndpointType.DOOR_AND_WINDOW,
        method="POST",
        uri=f"{API_URL}/api/housecheck/doorsandwindows",
    ),
    DataEndpoint(
        type=DataEndpointType.LEAKAGE_DETECTOR,  # Seems not be used by Sector App
        method="POST",
        uri=f"{API_URL}/api/v2/housecheck/leakagedetectors",
    ),
    DataEndpoint(
        type=DataEndpointType.SMOKE_DETECTOR,  # Seems not be used by Sector App
        method="POST",
        uri=f"{API_URL}/api/v2/housecheck/smokedetectors",
    ),
    DataEndpoint(
        type=DataEndpointType.CAMERAS,  # Not yet supported
        method="GET",
        uri=f"{API_URL}/api/v2/housecheck/cameras/{{panelId}}",
    ),
}

ACTION_ENDPOINTS: set[ActionEndpoint] = {
    ActionEndpoint(
        type=ActionEndpointType.LOGIN, method="POST", uri=f"{API_URL}/api/Login/Login"
    ),
    ActionEndpoint(
        type=ActionEndpointType.UNLOCK, method="POST", uri=f"{API_URL}/api/Panel/Unlock"
    ),
    ActionEndpoint(
        type=ActionEndpointType.LOCK, method="POST", uri=f"{API_URL}/api/Panel/Lock"
    ),
    ActionEndpoint(
        type=ActionEndpointType.ARM, method="POST", uri=f"{API_URL}/api/Panel/Arm"
    ),
    ActionEndpoint(
        type=ActionEndpointType.PARTIAL_ARM,
        method="POST",
        uri=f"{API_URL}/api/Panel/PartialArm",
    ),
    ActionEndpoint(
        type=ActionEndpointType.DISARM, method="POST", uri=f"{API_URL}/api/Panel/Disarm"
    ),
    ActionEndpoint(
        type=ActionEndpointType.TURN_OFF_SMART_PLUG,
        method="POST",
        uri=f"{API_URL}/api/Panel/TurnOffSmartplug",
    ),
    ActionEndpoint(
        type=ActionEndpointType.TURN_ON_SMART_PLUG,
        method="POST",
        uri=f"{API_URL}/api/Panel/TurnOnSmartplug",
    ),
}


def fetch_data_endpoints(types: set[DataEndpointType]) -> set[DataEndpoint]:
    result: set[DataEndpoint] = {e for e in DATA_ENDPOINTS if e.type() in types}
    return result


def fetch_action_endpoint(type: ActionEndpointType) -> ActionEndpoint:
    for endpoint in ACTION_ENDPOINTS:
        if endpoint.type() == type:
            return endpoint
    raise NotImplementedError(f"Unsupported endpoint type {type}")
