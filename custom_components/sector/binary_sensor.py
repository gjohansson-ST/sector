"""Binary Sensor platform for Sector integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
    """Set up Sensibo binary sensor platform."""

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
    """Representation of a Sensibo Motion Binary Sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        panel_id: str,
        lock_id: str | None,
        autolock: bool | None,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initiate Sensibo Motion Binary Sensor."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        self._lock_id = lock_id
        self.entity_description = description
        self._attr_unique_id: str = "sa_bs_" + str(description.key)
        self._attr_is_on = autolock

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if active := self.coordinator.data[self._panel_id].get(
            self.entity_description.key
        ):
            self._attr_is_on = active
        if locks := self.coordinator.data[self._panel_id].get("lock"):
            for lock, lock_data in locks.items():
                if lock == self._lock_id:
                    self._attr_is_on = lock_data["autolock"]

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity available."""
        return True
