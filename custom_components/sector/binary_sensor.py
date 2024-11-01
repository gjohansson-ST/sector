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
from homeassistant.helpers.entity import EntityCategory
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
        name="Arm ready",
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
    name="Autolock enabled",
    icon="mdi:shield-home",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensor platform."""

    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SectorBinarySensor] = []

    for panel in coordinator.data:
        for description in SENSOR_TYPES:
            entities.append(
                SectorBinarySensor(
                    coordinator=coordinator,
                    panel_id=panel,
                    lock_id=None,
                    autolock=None,
                    description=description,
                )
            )
    for panel, panel_data in coordinator.data.items():
        if "lock" in panel_data:
            for lock, lock_data in panel_data["lock"].items():
                entities.append(
                    SectorBinarySensor(
                        coordinator=coordinator,
                        panel_id=panel,
                        lock_id=lock,
                        autolock=lock_data.get("autolock"),
                        description=LOCK_TYPES,
                    )
                )

    async_add_entities(entities)


class SectorBinarySensor(
    CoordinatorEntity[SectorDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Binary Sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        panel_id: str,
        lock_id: str | None,
        autolock: bool | None,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initiate Binary Sensor."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        self._lock_id = lock_id
        self.entity_description = description
        self._attr_unique_id = f"sa_bs_{panel_id}_{str(lock_id)}"
        self._attr_is_on = autolock if lock_id else False
        if lock_id:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"sa_lock_{lock_id}")},
                manufacturer="Sector Alarm",
                model="Lock",
                sw_version="master",
                via_device=(DOMAIN, f"sa_hub_{panel_id}"),
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"sa_panel_{panel_id}")},
                name=f"Sector Alarmpanel {panel_id}",
                manufacturer="Sector Alarm",
                model="Alarmpanel",
                sw_version="master",
                via_device=(DOMAIN, f"sa_hub_{panel_id}"),
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data[self._panel_id]

        if active := self.coordinator.data[self._panel_id].get(
            self.entity_description.key
        ):
            self._attr_is_on = active

        if self.entity_description.key == "closed":
            self._attr_is_on = data.get("Closed", True)
        elif self.entity_description.key == "low_battery":
            self._attr_is_on = data.get("LowBattery", False)
        elif self.entity_description.key == "online":
            self._attr_is_on = data.get("online")
        elif self.entity_description.key == "arm_ready":
            self._attr_is_on = data.get("arm_ready")

        if locks := self.coordinator.data[self._panel_id].get("lock"):
            for lock, lock_data in locks.items():
                if lock == self._lock_id:
                    self._attr_is_on = lock_data["autolock"]

        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return entity available."""
        return True
