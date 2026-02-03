from typing import Optional, TypedDict

class PanelStatus(TypedDict):
    IsOnline: bool
    StatusTime: str
    StatusTimeUtc: str
    PanelTimeZoneOffset: int
    TimeZoneName: str
    Status: int
    AnnexStatus: int
    ReadyToArm: bool

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
    PanelCodeLength: int
    QuickArmEnabled: bool
    CanPartialArm: bool
    Locks: list[Lock]
    Temperatures: list[Temperature]
    Smartplugs: list[SmartPlug]

class Component(TypedDict):
    SerialNo: str
    Serial: str
    Label: str
    Name: str
    Type: str
    Closed: Optional[bool]
    LowBattery: Optional[bool]
    BatteryLow: Optional[bool]
    Alarm: Optional[bool]
    Temperature: Optional[float]
    Humidity: Optional[float]

class Place(TypedDict):
    Components: list[Component]

class Section(TypedDict):
    Places: list[Place]

class HouseCheck(TypedDict):
    Sections: list[Section]