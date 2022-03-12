"""SECTOR ALARM INTEGRATION CONSTANTS FOR HOME ASSISTANT."""
from __future__ import annotations

import logging

DOMAIN = "sector"

LOGGER = logging.getLogger(__package__)

API_URL = "https://mypagesapi.sectoralarm.net/api"

CONF_USERID = "userid"
CONF_PASSWORD = "password"
CONF_CODE_FORMAT = "code_format"
CONF_CODE = "code"
CONF_TEMP = "temp"
CONF_LOCK = "lock"
UPDATE_INTERVAL = "timesync"

MIN_SCAN_INTERVAL = 30


PLATFORMS = ["alarm_control_panel", "lock", "sensor", "switch"]
