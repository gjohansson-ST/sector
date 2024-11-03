"""Binary Sensor platform for Sector integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator

SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Online",
    ),
    BinarySensorEntityDescription(
        key="arm_ready",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Arm Ready",
        icon="mdi:shield-home",
    ),
    BinarySensorEntityDescription(
        key="closed",
        device_class=BinarySensorDeviceClass.DOOR,
        name="Closed",
    ),
    BinarySensorEntityDescription(
        key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        name="Battery Low",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)
LOCK_TYPES: BinarySensorEntityDescription = BinarySensorEntityDescription(
    key="autolock",
    entity_category=EntityCategory.DIAGNOSTIC,
    name="Autolock Enabled",
    icon="mdi:shield-home",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensor platform."""

    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SectorBinarySensor] = []

    for panel, panel_data in coordinator.data.items():
        # Add door and window sensors
        if "doors_and_windows" in panel_data:
            for sensor_id, sensor_data in panel_data["doors_and_windows"].items():
                sensor_name = sensor_data.get("name", "Unnamed Sensor")
                sensor_type = sensor_data.get("type", "Unknown Sensor Type")

                device_info = DeviceInfo(
                    identifiers={(DOMAIN, f"sa_device_{panel}_{sensor_id}")},
                    name=f"{sensor_name} on Panel {panel}",
                    manufacturer="Sector Alarm",
                    model=sensor_type,
                    sw_version="master",
                    via_device=(DOMAIN, f"sa_hub_{panel}"),
                )

                for description in SENSOR_TYPES:
                    if description.key in ["closed", "low_battery"]:
                        entities.append(
                            SectorBinarySensor(
                                coordinator=coordinator,
                                panel_id=panel,
                                sensor_id=sensor_id,
                                lock_id=None,
                                autolock=None,
                                name=f"{sensor_name} ({description.name})",
                                description=description,
                                device_info=device_info,
                            )
                        )

        # Add lock sensors
        if "lock" in panel_data:
            for lock, lock_data in panel_data["lock"].items():
                lock_name = lock_data.get("name", "Unnamed Lock")

                device_info = DeviceInfo(
                    identifiers={(DOMAIN, f"sa_lock_{panel}_{lock}")},
                    name=f"{lock_name} on Panel {panel}",
                    manufacturer="Sector Alarm",
                    model="Lock",
                    sw_version="master",
                    via_device=(DOMAIN, f"sa_hub_{panel}"),
                )

                entities.append(
                    SectorBinarySensor(
                        coordinator=coordinator,
                        panel_id=panel,
                        sensor_id=None,
                        lock_id=lock,
                        autolock=lock_data.get("autolock"),
                        name=f"{lock_name} ({LOCK_TYPES.name})",
                        description=LOCK_TYPES,
                        device_info=device_info,
                    )
                )

    async_add_entities(entities)


class SectorBinarySensor(
    CoordinatorEntity[SectorDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Sector Binary Sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        panel_id: str,
        sensor_id: str | None,
        lock_id: str | None,
        autolock: bool | None,
        name: str,
        description: BinarySensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initiate Binary Sensor."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        self._sensor_id = sensor_id
        self._lock_id = lock_id
        self.entity_description = description
        self._attr_unique_id = f"sa_bs_{panel_id}_{sensor_id or lock_id or 'panel'}"
        self._attr_is_on = autolock if lock_id else False
        self._attr_name = name
        self._attr_device_info = device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data[self._panel_id]

        # Handle updates for door and window sensors
        if self._sensor_id:
            door_window_data = self.coordinator.data[self._panel_id]["doors_and_windows"].get(
                self._sensor_id, {}
            )
            if self.entity_description.key == "closed":
                self._attr_is_on = door_window_data.get("Closed", True)
            elif self.entity_description.key == "low_battery":
                self._attr_is_on = door_window_data.get("LowBattery", False)

        # Handle panel-level sensors
        elif self.entity_description.key == "online":
            self._attr_is_on = data.get("online")
        elif self.entity_description.key == "arm_ready":
            self._attr_is_on = data.get("arm_ready")

        # Handle lock sensors
        if self._lock_id:
            if locks := data.get("lock"):
                lock_data = locks.get(self._lock_id)
                if lock_data:
                    self._attr_is_on = lock_data.get("autolock", False)

        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True
