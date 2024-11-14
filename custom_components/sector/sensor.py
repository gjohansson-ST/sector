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

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm sensors."""
    coordinator = entry.runtime_data
    devices: dict[str, dict[str, Any]] = coordinator.data.get("devices", {})
    entities: list[SectorAlarmSensor] = []

    for device in devices.values():
        serial_no = device["serial_no"]
        sensors = device.get("sensors", {})
        device_name = device.get("name", "Unknown Device")
        device_model = device.get("model", "")

        for description in SENSOR_TYPES:
            if description.key in sensors:
                entities.append(
                    SectorAlarmSensor(
                        coordinator, serial_no, description, device_name, device_model
                    )
                )
                _LOGGER.debug("Added temperature sensor for device %s", serial_no)

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No sensor entities to add.")


class SectorAlarmSensor(SectorAlarmBaseEntity, SensorEntity):
    """Base class for a Sector Alarm sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        entity_description: SensorEntityDescription,
        device_name: str,
        device_model: str | None,
    ) -> None:
        """Initialize the sensor with description and device info."""
        super().__init__(coordinator, serial_no, device_name, device_model)
        self.entity_description = entity_description
        self._attr_unique_id = f"{serial_no}_{entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        return device["sensors"].get(self.entity_description.key) if device else None
