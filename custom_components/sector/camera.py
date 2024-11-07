# camera.py

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
):
    """Set up Sector Alarm cameras."""
    # Access coordinator directly by entry.entry_id
    coordinator: SectorDataUpdateCoordinator = entry.runtime_data
    devices = coordinator.data.get("devices", {})
    cameras = devices.get("cameras", [])
    entities = [SectorAlarmCamera(coordinator, camera_data) for camera_data in cameras]

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No camera entities to add.")


class SectorAlarmCamera(SectorAlarmBaseEntity, Camera):
    """Representation of a Sector Alarm camera."""

    _attr_name = None

    def __init__(self, coordinator: SectorDataUpdateCoordinator, camera_data: dict):
        """Initialize the camera."""
        self._camera_data = camera_data
        serial_no = str(camera_data.get("SerialNo") or camera_data.get("Serial"))
        name = camera_data.get("Label", "Sector Camera")
        super().__init__(coordinator, serial_no, {"name": name}, "Camera")
        Camera.__init__(self)
        self._attr_unique_id = f"{self._serial_no}_camera"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ):
        """Return a still image response from the camera."""
        # Implement the method to retrieve an image from the camera
        image = await self.coordinator.api.get_camera_image(self._serial_no)
        return image
