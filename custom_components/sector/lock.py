"""Adds Lock for Sector integration."""
from __future__ import annotations

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_CODE, CONF_CODE_FORMAT, DOMAIN
from .coordinator import SectorAlarmHub


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Lock platform."""

    sector_hub: SectorAlarmHub = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    code: str | None = entry.options.get(CONF_CODE)
    code_format: int | None = entry.options.get(CONF_CODE_FORMAT)

    lockdevices: list = []
    for panel, panel_data in sector_hub.data.items():
        for lock, lock_data in panel_data["lock"].items():
            name = lock_data["name"]
            autolock = lock_data["autolock"]
            serial = lock
            description = LockEntityDescription(
                key=lock, name=f"Sector {name} {serial}"
            )
            lockdevices.append(
                SectorAlarmLock(
                    sector_hub,
                    coordinator,
                    code,
                    code_format,
                    autolock,
                    description,
                    panel,
                )
            )

    if lockdevices:
        async_add_entities(lockdevices)


class SectorAlarmLock(CoordinatorEntity, LockEntity):
    """Sector lock."""

    def __init__(
        self,
        hub: SectorAlarmHub,
        coordinator: DataUpdateCoordinator,
        code: str | None,
        code_format: int | None,
        autolock: str,
        description: LockEntityDescription,
        panel_id: str,
    ) -> None:
        """Initialize lock."""
        self._hub = hub
        self._panel_id = panel_id
        super().__init__(coordinator)
        self._attr_name = description.name
        self._attr_unique_id = f"sa_lock_{description.key}"
        self._attr_code_format = f"^\\d{code_format}$" if code_format else None
        self._attr_is_locked = bool(
            self._hub.data[panel_id]["lock"][description.key]["status"] == "lock"
        )
        self._autolock = autolock
        self._code = code
        self.entity_description = description
        self._code_format = code_format

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"sa_lock_{self.entity_description.key}")},
            "name": self.entity_description.name,
            "manufacturer": "Sector Alarm",
            "model": "Lock",
            "sw_version": "master",
            "via_device": (DOMAIN, f"sa_hub_{self._panel_id}"),
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Additional states of lock."""
        return {
            "Autolock": self._autolock,
            "Serial No": self.entity_description.key,
        }

    async def async_unlock(self, **kwargs: str) -> None:
        """Unlock lock."""
        command = "unlock"
        code = kwargs.get(ATTR_CODE, self._code)
        if code:
            await self._hub.triggerlock(
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
            await self._hub.triggerlock(
                self.entity_description.key, code, command, self._panel_id
            )
            self._attr_is_locked = True
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_locked = bool(
            self._hub.data[self._panel_id]["lock"][self.entity_description.key][
                "status"
            ]
            == "lock"
        )
        self.async_write_ha_state()
