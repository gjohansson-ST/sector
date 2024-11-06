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
]

CATEGORY_MODEL_MAPPING = {
    "1": "Door/Window Sensor",
    "doors and windows": "Door/Window Sensor",
    "vibrationsensor": "Door/Window Sensor",
    "smoke detector": "Smoke Detector",
    "smoke detectors": "Smoke Detector",
    "smokedetectorsync": "Smoke Detector",
    "leakage detectors": "Leakage Detector",
    "temperatures": "Temperature Sensor",
    "humidity": "Humidity Sensor",
    "smartplug status": "Smart Plug",
    "lock status": "Lock",
    "cameras": "Camera",
    "camerapir": "Camera",
    "keypad": "Keypad",
}

CONF_PANEL_ID = "panel_id"
CONF_CODE_FORMAT = 6
