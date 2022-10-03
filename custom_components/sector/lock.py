"""Adds Lock for Sector integration."""
from __future__ import annotations

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CODE, CONF_CODE_FORMAT, DOMAIN
from .coordinator import SectorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Lock platform."""

    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    code: str | None = entry.options.get(CONF_CODE)
    code_format: int | None = entry.options.get(CONF_CODE_FORMAT)

    lock_list: list = []
    for panel, panel_data in coordinator.data.items():
        if "lock" in panel_data:
            for lock, lock_data in panel_data["lock"].items():
                name = lock_data["name"]
                serial = lock
                description = LockEntityDescription(
                    key=lock, name=f"Sector {name} {serial}"
                )
                lock_list.append(
                    SectorAlarmLock(
                        coordinator,
                        code,
                        code_format,
                        description,
                        panel,
                    )
                )

    if lock_list:
        async_add_entities(lock_list)


class SectorAlarmLock(CoordinatorEntity[SectorDataUpdateCoordinator], LockEntity):
    """Sector lock."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        code: str | None,
        code_format: int | None,
        description: LockEntityDescription,
        panel_id: str,
    ) -> None:
        """Initialize lock."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        self._attr_unique_id = f"sa_lock_{description.key}"
        self._attr_code_format = f"^\\d{code_format}$" if code_format else None
        self._attr_is_locked = bool(
            self.coordinator.data[panel_id]["lock"][description.key]["status"] == "lock"
        )
        self._code = code
        self.entity_description = description
        self._code_format = code_format
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"sa_lock_{description.key}")},
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
            "Serial No": self.entity_description.key,
        }

    async def async_unlock(self, **kwargs: str) -> None:
        """Unlock lock."""
        command = "unlock"
        code = kwargs.get(ATTR_CODE, self._code)
        if code:
            await self.coordinator.triggerlock(
                self.entity_description.key, code, command, self._panel_id
            )
            self._attr_is_locked = False
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided")

    async def async_lock(self, **kwargs: str) -> None:
        """Lock lock."""
        command = "lock"
        code = kwargs.get(ATTR_CODE, self._code)
        if code:
            await self.coordinator.triggerlock(
                self.entity_description.key, code, command, self._panel_id
            )
            self._attr_is_locked = True
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if lock := self.coordinator.data[self._panel_id]["lock"].get(
            self.entity_description.key
        ):
            self._attr_is_locked = bool(lock.get("status") == "lock")
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity available."""
        return True
