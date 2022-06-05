"""Adds Lock for Sector integration."""
from __future__ import annotations

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE, STATE_LOCKED
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
    code: str = entry.data[CONF_CODE]
    code_format: int = entry.data[CONF_CODE_FORMAT]

    locks = await sector_hub.get_locks()
    if not locks:
        return
    lockdevices: list = []
    for lock in locks:
        name = await sector_hub.get_name(lock, "lock")
        autolock = await sector_hub.get_autolock(lock)
        description = LockEntityDescription(key=lock, name=f"Sector {name} {lock}")
        lockdevices.append(
            SectorAlarmLock(
                sector_hub,
                coordinator,
                code,
                code_format,
                lock,
                autolock,
                description,
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
        code: str,
        code_format: int,
        serial: str,
        autolock: str,
        description: LockEntityDescription,
    ) -> None:
        """Initialize lock."""
        self._hub = hub
        super().__init__(coordinator)
        self._attr_name = description.name
        self._attr_unique_id: str = "sa_lock_" + str(description.key)
        self._attr_code_format: str = f"^\\d{code_format}$"
        self._attr_is_locked = bool(
            self._hub.lock_state[description.key] == STATE_LOCKED
        )
        self._autolock = autolock
        self._code = code
        self.entity_description = description
        self._code_format = code_format

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._attr_name,
            "manufacturer": "Sector Alarm",
            "model": "Lock",
            "sw_version": "master",
            "via_device": (DOMAIN, "sa_hub_" + str(self._hub.alarm_id)),
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Additional states of lock."""
        return {
            "Autolock": self._autolock,
            "Serial No": self.entity_description.key,
        }

    async def async_unlock(self, **kwargs) -> None:
        """Unlock lock."""
        command = "unlock"
        code = kwargs.get(ATTR_CODE, self._code)
        if code:
            await self._hub.triggerlock(self.entity_description.key, code, command)
            self._attr_is_locked = False
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided")

    async def async_lock(self, **kwargs) -> None:
        """Lock lock."""
        command = "lock"
        code = kwargs.get(ATTR_CODE, self._code)
        if code:
            await self._hub.triggerlock(self.entity_description.key, code, command)
            self._attr_is_locked = True
            self.async_write_ha_state()
            return
        raise HomeAssistantError("No code provided")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_locked = bool(
            self._hub.lock_state[self.entity_description.key] == "lock"
        )
        self.async_write_ha_state()
