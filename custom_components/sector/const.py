# const.py
"""Constants for the Sector Alarm integration."""

import logging

DOMAIN = "sector"
API_URL = "https://api.sectoralarm.com"

CONF_CODE_FORMAT = "code_format"
CONF_TEMP = "temperature_setting"

LOGGER = logging.getLogger(__package__)

DEFAULT_CODE_FORMAT = 6
PLATFORMS = ["lock", "alarm_control_panel", "sensor", "binary_sensor"]

# Device Types
DEVICE_TYPE_SMOKE_DETECTOR = "SmokeDetectorSync"
DEVICE_TYPE_CAMERA = "CameraPIR"
DEVICE_TYPE_VIBRATION_SENSOR = "VibrationSensor"
DEVICE_TYPE_KEYPAD = "Keypad"
DEVICE_TYPE_DOOR_WINDOW_SENSOR = "DoorWindowSensor"

# Alarm Constants
ARM_HOME = "arm_home"
ARM_AWAY = "arm_away"
DISARM = "disarm"
