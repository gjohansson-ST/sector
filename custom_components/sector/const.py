"""Constants for the Sector Alarm integration."""
from datetime import timedelta
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

# Default scan interval for data updates
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
# Config entry key for user‑defined scan interval
CONFIG_SCAN_INTERVAL = "scan_interval"

# New constants for scan interval handling
# Duplicate block removed – definitions moved above


class RUNTIME_DATA(Enum):
    DEVICE_COORDINATORS = "Device coordinators list key"
