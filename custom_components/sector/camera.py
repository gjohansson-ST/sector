# camera.py

"""Camera platform for Sector Alarm integration."""
from __future__ import annotations

import logging

from homeassistant.components.camera import Camera
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
    """Set up Sector Alarm cameras."""
    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    devices = coordinator.data.get("devices", {})
    cameras = devices.get("cameras", [])
    entities = []

    for camera_data in cameras:
        entities.append(SectorAlarmCamera(coordinator, camera_data))

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No camera entities to add.")


class SectorAlarmCamera(CoordinatorEntity, Camera):
    """Representation of a Sector Alarm camera."""

    def __init__(self, coordinator: SectorDataUpdateCoordinator, camera_data: dict):
        """Initialize the camera."""
        super().__init__(coordinator)
        self._camera_data = camera_data
        self._serial_no = str(camera_data.get("SerialNo") or camera_data.get("Serial"))
        self._attr_unique_id = f"{self._serial_no}_camera"
        self._attr_name = camera_data.get("Label", "Sector Camera")
        _LOGGER.debug(f"Initialized camera with unique_id: {self._attr_unique_id}")

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        # Implement the method to retrieve an image from the camera
        image = await self.coordinator.api.get_camera_image(self._serial_no)
        return image

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_no)},
            name=self._attr_name,
            manufacturer="Sector Alarm",
#            model="Camera",
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return True
