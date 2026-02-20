"""Sensor platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.sector.const import RUNTIME_DATA

from .coordinator import (
    DeviceRegistry,
    SectorAlarmConfigEntry,
    SectorDeviceDataUpdateCoordinator,
)
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm sensors."""
    entities: list[SectorAlarmSensor] = []
    coordinators: list[SectorDeviceDataUpdateCoordinator] = entry.runtime_data[
        RUNTIME_DATA.DEVICE_COORDINATORS
    ]

    for coordinator in coordinators:
        device_registry: DeviceRegistry = coordinator.data.get(
            "device_registry", DeviceRegistry()
        )
        devices: dict[str, dict[str, Any]] = (
            device_registry.fetch_devices_by_coordinator(coordinator.name)
        )
        for serial_no, device in devices.items():
            device_name: str = device["name"]
            device_model = device["model"]
            for entity_model, entity in device.get("entities", {}).items():
                sensors = entity.get("sensors", {})

                for description in SENSOR_TYPES:
                    if description.key in sensors:
                        entities.append(
                            SectorAlarmSensor(
                                coordinator,
                                serial_no,
                                description,
                                device_name,
                                device_model,
                                entity_model,
                            )
                        )
                        _LOGGER.debug(
                            "Added temperature sensor for device %s", serial_no
                        )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No sensor entities to add.")


class SectorAlarmSensor(
    SectorAlarmBaseEntity[SectorDeviceDataUpdateCoordinator], SensorEntity
):
    """Base class for a Sector Alarm sensor."""

    def __init__(
        self,
        coordinator: SectorDeviceDataUpdateCoordinator,
        serial_no: str,
        entity_description: SensorEntityDescription,
        device_name: str,
        device_model: str,
        entity_model: str,
    ) -> None:
        """Initialize the sensor with description and device info."""
        super().__init__(
            coordinator, serial_no, device_name, device_model, entity_model
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{serial_no}_{entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        entity = self.entity_data or {}
        sensors: dict[str, Any] = entity.get("sensors", {})
        return sensors.get(self.entity_description.key)
