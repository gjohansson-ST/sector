"""Adds Lock for Sector integration."""
from __future__ import annotations

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SectorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the lock platform."""

    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    lock_entities: list[SectorAlarmLock] = []
    for panel_id, panel_data in coordinator.data.items():
        if "lock" in panel_data:
            for lock_serial, lock_data in panel_data["lock"].items():
                description = LockEntityDescription(
                    key=lock_serial,
                    name=f"Sector {lock_data['name']} {lock_serial}",
                )
                lock_entities.append(
                    SectorAlarmLock(
                        coordinator=coordinator,
                        description=description,
                        panel_id=panel_id,
                        lock_serial=lock_serial,
                    )
                )

    if lock_entities:
        async_add_entities(lock_entities)


class SectorAlarmLock(CoordinatorEntity[SectorDataUpdateCoordinator], LockEntity):
    """Sector lock entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        description: LockEntityDescription,
        panel_id: str,
        lock_serial: str,
    ) -> None:
        """Initialize the lock."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        self._lock_serial = lock_serial
        self.entity_description = description
        self._attr_unique_id = f"sa_lock_{lock_serial}"
        self._attr_is_locked = (
            self.coordinator.data[panel_id]["lock"][lock_serial].get("status") == "lock"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, lock_serial)},
            name=description.name,
            manufacturer="Sector Alarm",
            model="Lock",
            sw_version="master",
            via_device=(DOMAIN, f"sa_hub_{panel_id}"),
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Additional states of lock."""
        return {
            "Serial No": self._lock_serial,
        }

    async def async_unlock(self, **kwargs: str) -> None:
        """Unlock the lock."""
        command = "unlock"
        if code := kwargs.get(ATTR_CODE):
            await self.coordinator.triggerlock(
                lock=self._lock_serial, code=code, command=command, panel_id=self._panel_id
            )
            self._attr_is_locked = False
            self.async_write_ha_state()

    async def async_lock(self, **kwargs: str) -> None:
        """Lock the lock."""
        command = "lock"
        if code := kwargs.get(ATTR_CODE):
            await self.coordinator.triggerlock(
                lock=self._lock_serial, code=code, command=command, panel_id=self._panel_id
            )
            self._attr_is_locked = True
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if lock := self.coordinator.data[self._panel_id]["lock"].get(self._lock_serial):
            self._attr_is_locked = bool(lock.get("status") == "lock")
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return entity available."""
        return True
