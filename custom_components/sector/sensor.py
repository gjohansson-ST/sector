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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator

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


class SectorAlarmSensor(CoordinatorEntity[SectorDataUpdateCoordinator], SensorEntity):
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
        super().__init__(coordinator)
        self.entity_description = description
        self._serial_no = serial_no
        self._sensor_type = sensor_type
        self._device_info = device_info
        self._model = model
        self._attr_unique_id = f"{serial_no}_{sensor_type}"
        self._attr_name = f"{device_info['name']} {sensor_type.capitalize()}"
        _LOGGER.debug("Initialized sensor with unique_id: %s", self._attr_unique_id)

    @property
    def native_value(self):
        """Return the sensor value."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            value = device["sensors"].get(self._sensor_type)
            return value

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name=self._device_info["name"],
            manufacturer="Sector Alarm",
            model=self._model,
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "serial_number": self._serial_no,
        }
