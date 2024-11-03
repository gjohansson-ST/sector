# sensor.py
"""Sensor platform for Sector integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfHumidity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfHumidity.PERCENTAGE,
        name="Humidity",
    ),
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        name="Temperature",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor platform."""

    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SectorSensor] = []

    # Set up sensors for panels
    for panel_data in coordinator.data.values():
        if 'smoke_sensor' in panel_data:
            for sensor in panel_data['smoke_sensor']:
                for description in SENSOR_TYPES:
                    if description.key in sensor:
                        entities.append(
                            SectorSensor(
                                coordinator=coordinator,
                                serial_no=sensor['SerialNo'],
                                sensor_data=sensor,
                                description=description,
                            )
                        )
        if 'temperature' in panel_data:
            for sensor in panel_data['temperature']:
                for description in SENSOR_TYPES:
                    if description.key in sensor:
                        entities.append(
                            SectorSensor(
                                coordinator=coordinator,
                                serial_no=sensor['SerialNo'],
                                sensor_data=sensor,
                                description=description,
                            )
                        )

    async_add_entities(entities)


class SectorSensor(CoordinatorEntity[SectorDataUpdateCoordinator], SensorEntity):
    """Representation of a Sector Alarm sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        sensor_data: dict,
        description: SensorEntityDescription,
    ) -> None:
        """Initiate the sensor."""
        super().__init__(coordinator)
        self._serial_no = serial_no
        self._sensor_data = sensor_data
        self.entity_description = description
        self._attr_unique_id = f"sa_sensor_{serial_no}_{description.key}"
        self._attr_native_value = self._sensor_data.get(description.key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"sa_sensor_{serial_no}")},
            name=sensor_data.get("Label", f"Sensor {serial_no}"),
            manufacturer="Sector Alarm",
            model="Sensor",
            sw_version="master",
            via_device=(DOMAIN, f"sa_hub_{serial_no}"),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._sensor_data.get(self.entity_description.key)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return entity available."""
        return True
