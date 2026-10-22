"""Constants for the Sector Alarm integration."""

from enum import Enum, IntEnum

from homeassistant.const import Platform

DOMAIN = "sector"
PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.EVENT,
]

CONF_PANEL_ID = "panel_id"
CONF_IGNORE_QUICK_ARM = "ignore_quick_arm"


class RUNTIME_DATA(Enum):
    DEVICE_COORDINATORS = ("Device coordinators list key",)
    SECTOR_ALARM_API = "Sector Alarm API object key"


class AlarmStatus(IntEnum):
    """Known Sector Alarm panel status values."""

    DISARMED = 1
    ARMED_STAY = 2
    ARMED_AWAY = 3
