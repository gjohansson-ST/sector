"""Constants for the Sector Alarm integration."""
from __future__ import annotations

import logging

from homeassistant.const import Platform

DOMAIN = "sector_alarm"
LOGGER = logging.getLogger(__package__)

CONF_PANEL_ID = "panel_id"
CONF_PANEL_CODE = "panel_code"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]
