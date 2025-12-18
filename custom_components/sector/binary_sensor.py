"""Binary sensor platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .coordinator import SectorAlarmConfigEntry, SectorCoordinatorType
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="low_battery",
        name="Low battery",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    BinarySensorEntityDescription(
        key="closed",
        name="Closed",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    BinarySensorEntityDescription(
        key="leak_detected",
        name="Leak detected",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    BinarySensorEntityDescription(
        key="alarm",
        name="Alarm",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    BinarySensorEntityDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm binary sensors."""
    coordinator_action: DataUpdateCoordinator = entry.runtime_data[
        SectorCoordinatorType.ACTION_DEVICES
    ]
    coordinator_sensor: DataUpdateCoordinator = entry.runtime_data[
        SectorCoordinatorType.SENSOR_DEVICES
    ]

    _proccess_coordinator(coordinator_action, async_add_entities)
    _proccess_coordinator(coordinator_sensor, async_add_entities)


def _proccess_coordinator(
    coordinator: DataUpdateCoordinator, async_add_entities: AddEntitiesCallback
):
    devices: dict[str, Any] = coordinator.data.get("devices", {})
    entities: list[
        SectorAlarmBinarySensor
        | SectorAlarmPanelOnlineBinarySensor
        | SectorAlarmClosedSensor
    ] = []

    for device in devices.values():
        serial_no = device["serial_no"]
        sensors = device.get("sensors", {})
        device_name = device.get("name", "Unknown Device")
        device_model = device.get("model", "")

        for description in BINARY_SENSOR_TYPES:
            if description.key not in sensors:
                continue

            if description.key == "online":
                entities.append(
                    SectorAlarmPanelOnlineBinarySensor(
                        coordinator,
                        serial_no,
                        description,
                        device_name,
                        device_model,
                    )
                )

            elif description.key == "closed":
                entities.append(
                    SectorAlarmClosedSensor(
                        coordinator,
                        serial_no,
                        description,
                        device_name,
                        device_model,
                    )
                )
                _LOGGER.debug("Added closed sensor for device %s", serial_no)

            else:
                entities.append(
                    SectorAlarmBinarySensor(
                        coordinator, serial_no, description, device_name, device_model
                    )
                )
                _LOGGER.debug(
                    "Added %s sensor for device %s", description.name, serial_no
                )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No binary sensor entities to add.")


class SectorAlarmBinarySensor(SectorAlarmBaseEntity, BinarySensorEntity):
    """Base class for a Sector Alarm binary sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        serial_no: str,
        entity_description: BinarySensorEntityDescription,
        device_name: str,
        device_model: str,
    ) -> None:
        """Initialize the sensor with device info."""
        super().__init__(coordinator, serial_no, device_name, device_model)
        self.entity_description = entity_description
        self._sensor_type = entity_description.key
        self._attr_unique_id = f"{serial_no}_{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return True if the sensor is on."""
        device: dict = self.coordinator.data["devices"].get(self._serial_no, {})
        sensors = device.get("sensors", {})
        return sensors.get(self._sensor_type, None)


class SectorAlarmClosedSensor(SectorAlarmBinarySensor):
    """Binary sensor for detecting closed status of doors/windows."""

    @property
    def is_on(self) -> bool:
        """Return True if the door/window is open (closed: False)."""
        device: dict = self.coordinator.data["devices"].get(self._serial_no, {})
        sensors = device.get("sensors", {})
        return sensors.get("closed", None)


class SectorAlarmPanelOnlineBinarySensor(SectorAlarmBinarySensor, BinarySensorEntity):
    """Binary sensor for the Sector Alarm panel online status."""

    @property
    def is_on(self):
        """Return True if the panel is online."""
        device: dict = self.coordinator.data["devices"].get("alarm_panel", {})
        sensors = device.get("sensors", {})
        return sensors.get("online", None)
