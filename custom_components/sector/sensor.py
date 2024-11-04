"""Sensor platform for Sector Alarm integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sector Alarm sensors."""
    coordinator = entry.runtime_data
    devices = coordinator.data.get("devices", {})
    entities = []

    for device in devices.values():
        serial_no = device["serial_no"]
        sensors = device.get("sensors", {})
        device_type = device.get("type", "")
        device_model = device.get("model", "")

        _LOGGER.debug(
            "Adding device %s as model '%s' with type '%s'",
            serial_no,
            device_model,
            device_type,
        )

        if "temperature" in sensors:
            _LOGGER.debug(
                "Adding temperature sensor for device %s with sensors: %s",
                serial_no,
                sensors,
            )
            entities.append(
                SectorAlarmSensor(
                    coordinator,
                    serial_no,
                    "temperature",
                    device,
                    SensorEntityDescription(
                        key="temperature",
                        device_class=SensorDeviceClass.TEMPERATURE,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    ),
                    model=device_model,
                )
            )
        if "humidity" in sensors:
            _LOGGER.debug(
                "Adding humidity sensor for device %s with sensors: %s",
                serial_no,
                sensors,
            )
            entities.append(
                SectorAlarmSensor(
                    coordinator,
                    serial_no,
                    "humidity",
                    device,
                    SensorEntityDescription(
                        key="humidity",
                        device_class=SensorDeviceClass.HUMIDITY,
                        native_unit_of_measurement=PERCENTAGE,
                    ),
                    model=device_model,
                )
            )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No sensor entities to add.")


class SectorAlarmSensor(SectorAlarmBaseEntity, SensorEntity):
    """Representation of a Sector Alarm sensor."""

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        sensor_type: str,
        device_info: dict,
        description: SensorEntityDescription,
        model: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial_no, device_info, model)
        self.entity_description = description
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{serial_no}_{sensor_type}"
        self._attr_name = f"{sensor_type.capitalize()}"

    @property
    def native_value(self):
        """Return the sensor value."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            value = device["sensors"].get(self._sensor_type)
            return value
