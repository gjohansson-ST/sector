# descriptions.py
from dataclasses import dataclass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import EntityDescription

@dataclass
class GenericSensorEntityDescription(EntityDescription):
    """A generic entity description for multiple types of sensors."""
    device_class: str | None = None
    unit_of_measurement: str | None = None
    state_class: str | None = None
    icon: str | None = None
    # Additional properties for flexibility
