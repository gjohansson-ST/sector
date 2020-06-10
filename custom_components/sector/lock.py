import logging
import asyncio
from datetime import timedelta
from homeassistant.components.lock import LockEntity
from homeassistant.const import (ATTR_CODE, STATE_LOCKED, STATE_UNKNOWN,
                                 STATE_UNLOCKED)

import custom_components.sector as sector

DEPENDENCIES = ['sector']
DOMAIN = "sector"

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):

    sector_hub = hass.data[sector.DATA_SA]
    code = discovery_info[sector.CONF_CODE]
    code_format = discovery_info[sector.CONF_CODE_FORMAT]

    locks = await sector_hub.get_locks()

    lockdevices = []
    for lock in locks:
        name = await sector_hub.get_name(lock, "lock")
        autolock = await sector_hub.get_autolock(lock)
        _LOGGER.debug("Sector: Fetched Label %s for serial %s", name, lock)
        _LOGGER.debug("Sector: Fetched Autlock %s for serial %s", autolock, lock)
        lockdevices.append(SectorAlarmLock(sector_hub, code, code_format, lock, name, autolock))

    if lockdevices is not None and lockdevices != []:
        async_add_entities(lockdevices)
    else:
        return False

    return True

class SectorAlarmLockDevice(LockEntity):

    @property
    def device_info(self):
        """Return device information about HACS."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Sector Alarm",
            "model": "Lock",
            "sw_version": "master",
            "via_device_id": (DOMAIN, "sa_panel_"+str(self._hub.alarm_id)),
        }

class SectorAlarmLock(SectorAlarmLockDevice):

    def __init__(self, hub, code, code_format, serial, name, autolock):
        self._hub = hub
        self._serial = serial
        self._name = name
        self._autolock = autolock
        self._code = code
        self._code_format = code_format
        self._state = STATE_UNKNOWN

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return (
            "sa_lock_"+str(self._serial)
        )

    @property
    def name(self):
        return "Sector "+str(self._name)+" "+str(self._serial)

    @property
    def changed_by(self):
        return None

    @property
    def state(self):
        return self._state

    @property
    def available(self):
        return True

    @property
    def code_format(self):
        return self._code_format

    @property
    def device_state_attributes(self):
        return {
            "Name": self._name,
            "Autolock": self._autolock,
            "Serial No": self._serial
        }

    async def async_update(self):
        update = await self._hub.async_update()
        state = self._hub.lock_state[self._serial]
        if state == 'lock':
            self._state = STATE_LOCKED
        elif state == 'unlock':
            self._state = STATE_UNLOCKED
        else:
            self._state = STATE_UNKNOWN
        return True

    @property
    def is_locked(self):
        return self._state == STATE_LOCKED

    async def unlock(self, **kwargs):
        command = "unlock"
        _LOGGER.debug("Sector: command is %s", command)
        _LOGGER.debug("Sector: self._code is %s", self._code)
        code = kwargs.get(ATTR_CODE, self._code)
        _LOGGER.debug("Sector: code is %s", code)
        if code is None:
            _LOGGER.debug("Sector: No code supplied")
            return False

        state = await self._hub.triggerlock(self._serial, code, command)
        _LOGGER.debug("Sector: state is %s", state)
        if state:
            self._state = STATE_UNLOCKED
            _LOGGER.debug("Sector: self._state is %s", self._state)
            return True

        return False

    async def lock(self, **kwargs):
        command = "lock"
        _LOGGER.debug("Sector: command is %s", command)
        _LOGGER.debug("Sector: self._code is %s", self._code)
        code = kwargs.get(ATTR_CODE, self._code)
        _LOGGER.debug("Sector: code is %s", code)
        if code is None:
            _LOGGER.debug("Sector: No code supplied")
            return False

        state = await self._hub.triggerlock(self._serial, code, command)
        _LOGGER.debug("Sector: state is %s", state)
        if state:
            self._state = STATE_LOCKED
            _LOGGER.debug("Sector: self._state is %s", self._state)
            return True

        return False
