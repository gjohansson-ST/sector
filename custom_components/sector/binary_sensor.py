"""Binary sensor platform for Sector Alarm integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Sector Alarm binary sensors."""
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    devices = coordinator.data.get("devices", {})
    entities = []

    # Add device sensors
    for device in devices.values():
        serial_no = device["serial_no"]
        sensors = device.get("sensors", {})

        if "closed" in sensors:
            entities.append(
                SectorAlarmBinarySensor(
                    coordinator, serial_no, "closed", device, BinarySensorDeviceClass.DOOR
                )
            )
        if "low_battery" in sensors:
            entities.append(
                SectorAlarmBinarySensor(
                    coordinator,
                    serial_no,
                    "low_battery",
                    device,
                    BinarySensorDeviceClass.BATTERY,
                )
            )

    # Add panel online status sensor
    panel_status = coordinator.data.get("panel_status", {})
    panel_id = coordinator.entry.data.get("panel_id")
    serial_no = panel_status.get("SerialNo") or panel_id  # Use panel_id if SerialNo not available
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


class SectorAlarmBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Sector Alarm binary sensor."""

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        sensor_type: str,
        device_info: dict,
        device_class: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._serial_no = serial_no
        self._sensor_type = sensor_type
        self._device_info = device_info
        self._attr_unique_id = f"{serial_no}_{sensor_type}"
        self._attr_name = f"{device_info['name']} {sensor_type.replace('_', ' ').capitalize()}"
        self._attr_device_class = device_class
        _LOGGER.debug(f"Initialized binary sensor with unique_id: {self._attr_unique_id}")

    @property
    def is_on(self):
        """Return true if the sensor is on."""
        device = self.coordinator.data["devices"].get(self._serial_no)
        if device:
            sensor_value = device["sensors"].get(self._sensor_type)
            if self._sensor_type == "closed":
                return not sensor_value  # Invert because "Closed": true means door is closed
            return sensor_value
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name=self._device_info["name"],
            manufacturer="Sector Alarm",
            model="Sensor",
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True


class SectorAlarmPanelOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of the Sector Alarm panel online status."""

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        sensor_type: str,
        device_class: str,
    ) -> None:
        """Initialize the panel online binary sensor."""
        super().__init__(coordinator)
        self._serial_no = serial_no
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{serial_no}_{sensor_type}"
        self._attr_name = "Panel Online"
        self._attr_device_class = device_class
        _LOGGER.debug(f"Initialized panel online sensor with unique_id: {self._attr_unique_id}")

    @property
    def is_on(self):
        """Return true if the panel is online."""
        panel_status = self.coordinator.data.get("panel_status", {})
        return panel_status.get("IsOnline", False)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name="Sector Alarm Panel",
            manufacturer="Sector Alarm",
            model="Alarm Panel",
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True
