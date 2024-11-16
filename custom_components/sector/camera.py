"""Camera platform for Sector Alarm integration."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SectorAlarmConfigEntry, SectorDataUpdateCoordinator
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm cameras."""
    coordinator: SectorDataUpdateCoordinator = entry.runtime_data
    devices = coordinator.data.get("devices", {})
    cameras = devices.get("cameras", [])
    entities = []

    for camera_data in cameras:
        serial_no = str(camera_data.get("SerialNo") or camera_data.get("Serial"))
        device_name = camera_data.get("Label", "Sector Camera")
        entities.append(
            SectorAlarmCamera(coordinator, serial_no, device_name, "Camera")
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


class SectorAlarmCamera(SectorAlarmBaseEntity, Camera):
    """Representation of a Sector Alarm camera."""

    _attr_name = None

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        serial_no: str,
        device_name: str,
        device_model: str | None,
    ) -> None:
        """Initialize the camera entity with device info."""
        super().__init__(coordinator, serial_no, device_name, device_model)
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
        image = await self.coordinator.api.get_camera_image(self._serial_no)
        return image
