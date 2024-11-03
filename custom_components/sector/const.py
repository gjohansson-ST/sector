# const.py
"""Constants for the Sector Alarm integration."""

import logging

DOMAIN = "sector"
API_URL = "https://mypagesapi.sectoralarm.net/api"
UPDATE_INTERVAL = 60  # Update interval for the coordinator (in seconds)

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
DEVICE_TYPE_LEAKAGE_DETECTOR = "LeakageDetector"
DEVICE_TYPE_PANEL = "Panel"

# Alarm Constants
ARM_HOME = "arm_home"
ARM_AWAY = "arm_away"
DISARM = "disarm"

# Sensor Constants
SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_BATTERY = "battery"
SENSOR_TYPE_STATUS = "status"

# Platform Specific Constants
LOCK_UNLOCK = "unlock"
LOCK_LOCK = "lock"

# Logger Setup
LOGGER.setLevel(logging.DEBUG)
