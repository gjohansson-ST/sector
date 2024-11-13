"""Binary sensor platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SectorAlarmConfigEntry
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sector Alarm binary sensors."""
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    devices: dict[str, Any] = coordinator.data.get("devices", {})
    entities: list[SectorAlarmBinarySensor] = []

    for device in devices.values():
        serial_no = device["serial_no"]
        sensors = device.get("sensors", {})
        device_info = {
            "name": device.get("name", "Unknown Device"),
            "model": device.get("model", ""),
        }

        if "low_battery" in sensors:
            entities.append(
                SectorAlarmLowBatterySensor(coordinator, serial_no, device_info)
            )
            _LOGGER.debug("Added low battery sensor for device %s", serial_no)

        if "closed" in sensors:
            entities.append(
                SectorAlarmClosedSensor(coordinator, serial_no, device_info)
            )
            _LOGGER.debug("Added closed sensor for device %s", serial_no)

        if "leak_detected" in sensors:
            entities.append(SectorAlarmLeakSensor(coordinator, serial_no, device_info))
            _LOGGER.debug("Added leak detected sensor for device %s", serial_no)

        if "alarm" in sensors:
            entities.append(SectorAlarmAlarmSensor(coordinator, serial_no, device_info))
            _LOGGER.debug("Added alarm sensor for device %s", serial_no)

    # Add panel online status sensor
    panel_status = coordinator.data.get("panel_status", {})
    panel_id = entry.data.get("panel_id")
    serial_no = panel_status.get("SerialNo") or panel_id
    entities.append(
        SectorAlarmPanelOnlineBinarySensor(
            coordinator,
            serial_no,
            "online",
            BinarySensorDeviceClass.CONNECTIVITY,
        )
    )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No binary sensor entities to add.")


class SectorAlarmBinarySensor(SectorAlarmBaseEntity, BinarySensorEntity):
    """Base class for a Sector Alarm binary sensor."""

    def __init__(
        self, coordinator, serial_no, device_info, sensor_type, device_class
    ) -> None:
        """Initialize the sensor with device info."""
        super().__init__(coordinator, serial_no, device_info)
        self._sensor_type = sensor_type
        self._attr_device_class = device_class
        self._attr_unique_id = f"{serial_no}_{sensor_type}"
        self._attr_name = f"{sensor_type.replace('_', ' ').capitalize()}"

    @property
    def is_on(self) -> bool:
        """Return True if the sensor is on."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            sensor_value = device["sensors"].get(self._sensor_type)
            return bool(sensor_value)
        return False


class SectorAlarmLowBatterySensor(SectorAlarmBinarySensor):
    """Binary sensor for detecting low battery status."""

    def __init__(self, coordinator, serial_no, device_info) -> None:
        super().__init__(
            coordinator,
            serial_no,
            device_info,
            "low_battery",
            BinarySensorDeviceClass.BATTERY,
        )


class SectorAlarmClosedSensor(SectorAlarmBinarySensor):
    """Binary sensor for detecting closed status of doors/windows."""

    def __init__(self, coordinator, serial_no, device_info) -> None:
        super().__init__(
            coordinator, serial_no, device_info, "closed", BinarySensorDeviceClass.DOOR
        )

    @property
    def is_on(self) -> bool:
        """Return True if the door/window is open (closed: False)."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        return not device["sensors"].get("closed", True) if device else False


class SectorAlarmLeakSensor(SectorAlarmBinarySensor):
    """Binary sensor for detecting leaks."""

    def __init__(self, coordinator, serial_no, device_info) -> None:
        super().__init__(
            coordinator,
            serial_no,
            device_info,
            "leak_detected",
            BinarySensorDeviceClass.MOISTURE,
        )


class SectorAlarmAlarmSensor(SectorAlarmBinarySensor):
    """Binary sensor for detecting alarms."""

    def __init__(self, coordinator, serial_no, device_info):
        super().__init__(
            coordinator, serial_no, device_info, "alarm", BinarySensorDeviceClass.SAFETY
        )


class SectorAlarmPanelOnlineBinarySensor(SectorAlarmBaseEntity, BinarySensorEntity):
    """Binary sensor for the Sector Alarm panel online status."""

    def __init__(self, coordinator, serial_no, sensor_type, device_class):
        super().__init__(coordinator, serial_no, {"name": "Sector Alarm Panel"})
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{serial_no}_{sensor_type}"
        self._attr_name = "Online"
        self._attr_device_class = device_class

    @property
    def is_on(self):
        """Return True if the panel is online."""
        panel_status = self.coordinator.data.get("panel_status", {})
        return panel_status.get("IsOnline", False)
