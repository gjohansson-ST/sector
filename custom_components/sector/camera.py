"""Camera platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm cameras."""
    entities = []
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
                if entity_model == "Camera":
                    entities.append(
                        SectorAlarmCamera(
                            coordinator, serial_no, device_name, device_model
                        )
                    )
                    _LOGGER.debug(
                        "Added camera entity with serial: %s and name: %s",
                        serial_no,
                        device_name,
                    )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No camera entities to add.")


class SectorAlarmCamera(
    SectorAlarmBaseEntity[SectorDeviceDataUpdateCoordinator], Camera
):
    """Representation of a Sector Alarm camera."""

    _attr_name = None

    def __init__(
        self,
        coordinator: SectorDeviceDataUpdateCoordinator,
        serial_no: str,
        device_name: str,
        device_model: str,
    ) -> None:
        """Initialize the camera entity with device info."""
        super().__init__(
            coordinator, serial_no, device_name, device_model, device_model
        )
        Camera.__init__(self)
        self._attr_unique_id = f"{self._serial_no}_camera"
        _LOGGER.debug(
            "SECTOR_CAMERA: Initialized camera entity for device %s",
            self._attr_unique_id,
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        _LOGGER.debug(
            "SECTOR_CAMERA: Requesting image for device %s", self._attr_unique_id
        )
        image = await self.coordinator.sector_api.get_camera_image(self._serial_no)
        return image
