"""Adds Lock for Sector integration."""
import logging
import asyncio
from datetime import timedelta
from homeassistant.components.lock import LockEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    UpdateFailed,
)
from homeassistant.const import ATTR_CODE, STATE_LOCKED, STATE_UNKNOWN, STATE_UNLOCKED
from .const import (
    DOMAIN,
    CONF_CODE,
    CONF_CODE_FORMAT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """ No setup from yaml """
    return True


async def async_setup_entry(hass, entry, async_add_entities):

    sector_hub = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    code = entry.data[CONF_CODE]
    code_format = entry.data[CONF_CODE_FORMAT]

    locks = await sector_hub.get_locks()

    lockdevices = []
    for lock in locks:
        name = await sector_hub.get_name(lock, "lock")
        autolock = await sector_hub.get_autolock(lock)
        _LOGGER.debug("Sector: Fetched Label %s for serial %s", name, lock)
        _LOGGER.debug("Sector: Fetched Autolock %s for serial %s", autolock, lock)
        lockdevices.append(
            SectorAlarmLock(
                sector_hub, coordinator, code, code_format, lock, name, autolock
            )
        )

    if lockdevices is not None and lockdevices != []:
        async_add_entities(lockdevices)
    else:
        return False

    return True


class SectorAlarmLockDevice(LockEntity):
    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Sector Alarm",
            "model": "Lock",
            "sw_version": "master",
            "via_device": (DOMAIN, "sa_hub_" + str(self._hub.alarm_id)),
        }


class SectorAlarmLock(CoordinatorEntity, SectorAlarmLockDevice):
    def __init__(self, hub, coordinator, code, code_format, serial, name, autolock):
        self._hub = hub
        super().__init__(coordinator)
        self._serial = serial
        self._name = name
        self._autolock = autolock
        self._code = code
        self._code_format = code_format
        self._state = STATE_UNKNOWN

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return "sa_lock_" + str(self._serial)

    @property
    def name(self):
        return "Sector " + str(self._name) + " " + str(self._serial)

    @property
    def changed_by(self):
        return None

    @property
    def state(self):
        state = self._hub.lock_state[self._serial]
        if state == "lock":
            return STATE_LOCKED
        elif state == "unlock":
            return STATE_UNLOCKED
        else:
            return STATE_UNKNOWN

    @property
    def available(self):
        return True

    @property
    def code_format(self):
        """Return one or more digits/characters"""
        return "^\\d{%s}$" % self._code_format
        # return self._code_format

    @property
    def device_state_attributes(self):
        return {
            "Name": self._name,
            "Autolock": self._autolock,
            "Serial No": self._serial,
        }

    @property
    def is_locked(self):
        return self._state == STATE_LOCKED

    async def async_unlock(self, **kwargs):
        command = "unlock"
        _LOGGER.debug("Lock: command is %s", command)
        _LOGGER.debug("Lock: self._code is %s", self._code)
        code = kwargs.get(ATTR_CODE, self._code)
        _LOGGER.debug("Lock: code is %s", code)
        if code is None:
            _LOGGER.debug("Lock: No code supplied")
            return

        result = await self._hub.triggerlock(self._serial, code, command)
        if result:
            _LOGGER.debug("Lock: Sent command to trigger lock")
            self._state = STATE_LOCKED
            await self.coordinator.async_refresh()

    async def async_lock(self, **kwargs):
        command = "lock"
        _LOGGER.debug("Lock: command is %s", command)
        _LOGGER.debug("Lock: self._code is %s", self._code)
        code = kwargs.get(ATTR_CODE, self._code)
        _LOGGER.debug("Lock: code is %s", code)
        if code is None:
            _LOGGER.debug("Lock: No code supplied")
            return

        result = await self._hub.triggerlock(self._serial, code, command)
        if result:
            _LOGGER.debug("Lock: Sent command to trigger lock")
            self._state = STATE_UNLOCKED
            await self.coordinator.async_refresh()
