"""Constants for the Sector Alarm integration."""

DOMAIN = "sector_alarm"
PLATFORMS = ["alarm_control_panel", "binary_sensor", "lock", "sensor", "switch", "camera"]

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

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_PANEL_ID = "panel_id"
CONF_PANEL_CODE = "panel_code"

LOGGER = "sector_alarm"
