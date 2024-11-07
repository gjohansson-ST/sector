"""Binary sensor platform for Sector Alarm integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity
from .const import BINARY_SENSOR_DESCRIPTIONS

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

        # Add each sensor entity based on available descriptions
        for description in BINARY_SENSOR_DESCRIPTIONS:
            if description.key in sensors:
                entities.append(
                    SectorAlarmBinarySensor(
                        coordinator,
                        serial_no,
                        device,
                        description,
                        device_model,
                    )
                )

    # Handle panel online status as another entity in the setup
    panel_status = coordinator.data.get("panel_status", {})
    panel_id = entry.data.get("panel_id")
    serial_no = panel_status.get("SerialNo") or panel_id
    if serial_no:  # Add panel status sensor if serial number is available
        entities.append(
            SectorAlarmBinarySensor(
                coordinator,
                serial_no,
                {"name": "Sector Alarm Panel"},
                next(
                    desc
                    for desc in SENSOR_DESCRIPTIONS
                    if desc.sensor_type == "online"
                ),
                "Alarm Panel",
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
        device_info: dict,
        description: BinarySensorEntityDescription
        model: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, serial_no, device_info, model)
        self.entity_description = description
        self._attr_unique_id = f"{serial_no}_{description.sensor_type}"

    @property
    def is_on(self) -> bool:
        """Return true if the sensor is on."""
        sensor_type = self.entity_description.key
	if sensor_type == "online":
            # Handle panel online status separately
            panel_status = self.coordinator.data.get("panel_status", {})
            return panel_status.get("IsOnline", False)

        # Handle regular device sensors
        device = self.coordinator.data.get("devices", {}).get(self._serial_no)
        if device:
            sensor_value = device["sensors"].get(self._sensor_type)
            if self._sensor_type == "closed":
                return not sensor_value  # Invert because "Closed": true means door is closed
            if self._sensor_type == "low_battery":
                return sensor_value
            if self._sensor_type == "alarm":
                return sensor_value
            return bool(sensor_value)
        return False
