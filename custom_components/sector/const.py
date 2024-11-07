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
CONF_CODE_FORMAT = "code_format"

BINARY_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="closed",
        name="Closed",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    BinarySensorEntityDescription(
        key="low_battery",
        name="Battery",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    BinarySensorEntityDescription(
        key="leak_detected",
        name="Leak Detected",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    BinarySensorEntityDescription(
        key="alarm",
        name="Alarm",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
)
