from typing import Optional, TypedDict


class PanelStatus(TypedDict):
    IsOnline: bool
    Status: int


class Lock(TypedDict):
    Label: str
    Serial: str
    SerialNo: str
    BatteryLow: Optional[bool]
    Status: str


class SmartPlug(TypedDict):
    Id: str
    Label: str
    Serial: str
    SerialNo: str
    Status: str


class Temperature(TypedDict):
    Label: str
    SerialNo: str
    Serial: str
    Temperature: str


class LogRecord(TypedDict):
    User: str
    Channel: str
    Time: str
    EventType: str
    LockName: str


class LogRecords(TypedDict):
    Records: list[LogRecord]


class PanelInfo(TypedDict):
    PanelId: str
    Capabilities: list[str]
    PanelCodeLength: int
    QuickArmEnabled: bool
    CanPartialArm: bool
    Locks: list[Lock]
    Temperatures: list[Temperature]
    Smartplugs: list[SmartPlug]


class Component(TypedDict):
    SerialNo: str
    Label: str
    Name: str
    Type: str
    LowBattery: Optional[bool]
    Temperature: Optional[float]
    Humidity: Optional[float]


class Device(TypedDict):
    Label: str
    Name: str
    SerialString: str
    Type: str
    LowBattery: Optional[bool]
    Alarm: Optional[bool]
    Closed: Optional[bool]


class Place(TypedDict):
    Components: list[Component]


class Section(TypedDict):
    Places: list[Place]


class Room(TypedDict):
    Devices: list[Device]


class Floor(TypedDict):
    Rooms: list[Room]


class HouseCheck(TypedDict):
    Sections: list[Section]
    Floors: list[Floor]
