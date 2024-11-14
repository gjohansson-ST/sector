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

POLLING_INTERVALS = {
        "Humidity": 120,
        "Doors and Windows": 30,
        "Leakage Detectors": 300,
        "Smoke Detectors": 300,
        "Cameras": 300,
        "Persons": 300,
        "Temperatures": 300,
        "Panel Status": 30,
        "Smartplug Status": 300,
        "Lock Status": 15,
        "Logs": 60,
}

DEFAULT_POLLING_INTERVAL = 300

CONF_PANEL_ID = "panel_id"
CONF_CODE_FORMAT = "code_format"
