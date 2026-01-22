"""Constants for the Sector Alarm integration."""

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
