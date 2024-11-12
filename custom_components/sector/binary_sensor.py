"""Binary sensor platform for Sector Alarm integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up Sector Alarm binary sensors."""
    coordinator = entry.runtime_data
    devices = coordinator.data.get("devices", {})
    entities = []

    for device in devices.values():
        serial_no = device["serial_no"]
        sensors = device.get("sensors", {})
        device_type = device.get("type", "")
        device_model = device.get("model", "")

        _LOGGER.debug(
            "Adding binary sensor %s as model '%s' with type '%s'",
            serial_no,
            device_model,
            device_type,
        )

        if "closed" in sensors:
            entities.append(
                SectorAlarmBinarySensor(
                    coordinator,
                    serial_no,
                    "closed",
                    device,
                    BinarySensorDeviceClass.DOOR,
                    device_model,
                )
            )
        if "low_battery" in sensors:
            _LOGGER.debug(
                "Adding battery to %s as  model '%s' with type '%s'",
                serial_no,
                device_model,
                device_type,
            )
            entities.append(
                SectorAlarmBinarySensor(
                    coordinator,
                    serial_no,
                    "low_battery",
                    device,
                    BinarySensorDeviceClass.BATTERY,
                    device_model,
                )
            )
        else:
            _LOGGER.warning(
                "No low_battery sensor found for device %s (%s). Confirmed sensors: %s",
                serial_no,
                device_model,
                sensors,
            )
        if "leak_detected" in sensors:
            entities.append(
                SectorAlarmBinarySensor(
                    coordinator,
                    serial_no,
                    "leak_detected",
                    device,
                    BinarySensorDeviceClass.MOISTURE,
                    device_model,
                )
            )
        if "alarm" in sensors:
            entities.append(
                SectorAlarmBinarySensor(
                    coordinator,
                    serial_no,
                    "alarm",
                    device,
                    BinarySensorDeviceClass.SAFETY,
                    device_model,
                )
            )

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
    """Representation of a Sector Alarm binary sensor."""

    def __init__(
            self,
            coordinator: SectorDataUpdateCoordinator,
            serial_no: str,
            sensor_type: str,
            device_info: dict,
            device_class: BinarySensorDeviceClass,
            model: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, serial_no, device_info, model)
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{serial_no}_{sensor_type}"
        self._attr_name = f"{sensor_type.replace('_', ' ').capitalize()}"
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool:
        """Return true if the sensor is on."""
        device = self.coordinator.data.get("devices", {}).get(self._serial_no)
        if device:
            sensor_value = device["sensors"].get(self._sensor_type)
            if self._sensor_type == "closed":
                return (
                    not sensor_value
                )  # Invert because "Closed": true means door is closed
            if self._sensor_type == "low_battery":
                return sensor_value
            if self._sensor_type == "alarm":
                return sensor_value
            return bool(sensor_value)
        return False


class SectorAlarmPanelOnlineBinarySensor(SectorAlarmBaseEntity, BinarySensorEntity):
    """Representation of the Sector Alarm panel online status."""

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        sensor_type: str,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialize the panel online binary sensor."""
        super().__init__(
            coordinator, serial_no, {"name": "Sector Alarm Panel"}, "Alarm Panel"
        )
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{serial_no}_{sensor_type}"
        self._attr_name = "Online"
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool:
        """Return true if the panel is online."""
        panel_status = self.coordinator.data.get("panel_status", {})
        return panel_status.get("IsOnline", False)
