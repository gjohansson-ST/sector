"""Constants for Sector Alarm integration."""
from homeassistant.const import Platform
import logging

DOMAIN = "sector"
LOGGER = logging.getLogger(__package__)

API_URL = "https://mypagesapi.sectoralarm.net"

CONF_PANEL_ID = "panel_id"
CONF_PANEL_CODE = "panel_code"
UPDATE_INTERVAL = 60

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]
