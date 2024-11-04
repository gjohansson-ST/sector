"""Constants for the Sector Alarm integration."""

DOMAIN = "sector_alarm"
PLATFORMS = ["alarm_control_panel", "binary_sensor", "lock", "sensor", "switch", "camera"]

CATEGORY_MODEL_MAPPING = {
    "Doors and Windows": "Door/Window Sensor",
    "VibrationSensor": "Door/Window Sensor",
    "Smoke Detectors": "Smoke Detector",
    "SmokeDetectorSync": "Smoke Detector",
    "Leakage Detectors": "Leakage Detector",
    "Temperatures": "Temperature Sensor",
    "Humidity": "Humidity Sensor",
    "Smartplug Status": "Smart Plug",
    "Lock Status": "Lock",
    "Cameras": "Camera",
    "Keypad": "Keypad",
}

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_PANEL_ID = "panel_id"
CONF_PANEL_CODE = "panel_code"

LOGGER = "sector_alarm"
