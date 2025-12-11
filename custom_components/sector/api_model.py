from typing import TypedDict


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
    AutoLockEnabled: bool
    Label: str
    Serial: str
    SerialNo: str
    Status: str
    BatteryLow: bool # unsure if valid
    LowBattery: bool # unsure if valid

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
    UserTranslationKey: str
    Time: str
    EventType: str
    LockName: str

class LogRecords(TypedDict):
    Records: list[LogRecord]

class PanelInfo(TypedDict):
    PanelId: str
    Locks: list[Lock]
    Temperatures: list[Temperature]
    Smartplugs: list[SmartPlug]

class Component(TypedDict):
    SerialNo: str
    Serial: str
    Label: str
    Name: str
    Type: str
    Closed: bool
    LowBattery: bool
    BatteryLow: bool
    Alarm: bool
    Temperature: float
    Humidity: float

class Place(TypedDict):
    Components: list[Component]

class Section(TypedDict):
    Places: list[Place]

class HouseCheck(TypedDict):
    Sections: list[Section]