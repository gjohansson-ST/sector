"""SECTOR ALARM INTEGRATION CONSTANTS FOR HOME ASSISTANT."""
from __future__ import annotations

import logging

from homeassistant.const import Platform

DOMAIN = "sector"

LOGGER = logging.getLogger(__package__)

API_URL = "https://mypagesapi.sectoralarm.net/api"

CONF_USERID = "userid"  # Kept for migration purpose
CONF_CODE_FORMAT = "code_format"
CONF_CODE = "code"
CONF_TEMP = "temp"
CONF_LOCK = "lock"
UPDATE_INTERVAL = "timesync"

MIN_SCAN_INTERVAL = 60


PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]
