"""Constants for the Sector Alarm integration."""

from enum import Enum
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
    DEVICE_COORDINATORS = "Device coordinators list key"
