"""Sensor platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

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
    await coordinator.async_refresh()
    devices = coordinator.data.get("devices", {})
    entities = []

    for device in devices.values():
        serial_no = device["serial_no"]
        sensors = device.get("sensors", {})
        device_info = {
            "name": device.get("name", "Unknown Device"),
            "model": device.get("model", ""),
        }

        if "temperature" in sensors:
            entities.append(
                SectorAlarmTemperatureSensor(coordinator, serial_no, device_info)
            )
            _LOGGER.debug("Added temperature sensor for device %s", serial_no)

        if "humidity" in sensors:
            entities.append(
                SectorAlarmHumiditySensor(coordinator, serial_no, device_info)
            )
            _LOGGER.debug("Added humidity sensor for device %s", serial_no)

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No sensor entities to add.")


class SectorAlarmSensor(SectorAlarmBaseEntity, SensorEntity):
    """Base class for a Sector Alarm sensor."""

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        device_info: dict[str, Any],
        sensor_type: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor with description and device info."""
        super().__init__(coordinator, serial_no, device_info)
        self._sensor_type = sensor_type
        self.entity_description = description
        self._attr_unique_id = f"{serial_no}_{sensor_type}"
        self._attr_name = f"{sensor_type.capitalize()}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        return device["sensors"].get(self._sensor_type) if device else None


class SectorAlarmTemperatureSensor(SectorAlarmSensor):
    """Temperature sensor for Sector Alarm devices."""

    def __init__(self, coordinator, serial_no, device_info) -> None:
        super().__init__(
            coordinator,
            serial_no,
            device_info,
            "temperature",
            SensorEntityDescription(
                key="temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            ),
        )


class SectorAlarmHumiditySensor(SectorAlarmSensor):
    """Humidity sensor for Sector Alarm devices."""

    def __init__(self, coordinator, serial_no, device_info) -> None:
        super().__init__(
            coordinator,
            serial_no,
            device_info,
            "humidity",
            SensorEntityDescription(
                key="humidity",
                device_class=SensorDeviceClass.HUMIDITY,
                native_unit_of_measurement=PERCENTAGE,
            ),
        )
