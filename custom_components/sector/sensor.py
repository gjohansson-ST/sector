import logging
import asyncio
from datetime import timedelta
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.const import DEVICE_CLASS_TEMPERATURE

import custom_components.sector as sector

DEPENDENCIES = ["sector"]
DOMAIN = "sector"
DEFAULT_NAME = "sector"

CONF_USERID = "userid"
CONF_PASSWORD = "password"
CONF_CODE_FORMAT = "code_format"
CONF_CODE = "code"
CONF_TEMP = "temp"
CONF_LOCK = "lock"

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):

    sector_hub = hass.data[sector.DOMAIN]

    thermometers = await sector_hub.get_thermometers()

    tempsensors = []
    for sensor in thermometers:
        name = await sector_hub.get_name(sensor, "temp")
        _LOGGER.debug("Sector: Fetched Label %s for serial %s", name, sensor)
        tempsensors.append(SectorAlarmTemperatureSensor(sector_hub, sensor, name))

    if tempsensors is not None and tempsensors != []:
            async_add_entities(tempsensors)
    else:
        return False

    return True

async def async_setup_entry(hass, entry, async_add_entities):

    sector_hub = hass.data[DOMAIN]

    thermometers = await sector_hub.get_thermometers()

    tempsensors = []
    for sensor in thermometers:
        name = await sector_hub.get_name(sensor, "temp")
        _LOGGER.debug("Sector: Fetched Label %s for serial %s", name, sensor)
        tempsensors.append(SectorAlarmTemperatureSensor(sector_hub, sensor, name))

    if tempsensors is not None and tempsensors != []:
            async_add_entities(tempsensors)
    else:
        return False

    return True

class SectorAlarmTemperatureDevice(Entity):

    @property
    def device_info(self):
        """Return device information about HACS."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Sector Alarm",
            "model": "Temperature",
            "sw_version": "master",
            "via_device": (DOMAIN, "sa_hub_"+str(self._hub.alarm_id)),
        }

class SectorAlarmTemperatureSensor(SectorAlarmTemperatureDevice):

    def __init__(self, hub, sensor, name):
        self._hub = hub
        self._serial = sensor
        self._name = name
        self._state = None
        self._uom = TEMP_CELSIUS
        self._deviceclass = DEVICE_CLASS_TEMPERATURE

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return (
            "sa_temp_"+str(self._serial)
        )

    @property
    def name(self):
        return "Sector "+str(self._name)+" "+str(self._serial)

    @property
    def unit_of_measurement(self):
        return self._uom

    async def async_update(self):
        update = await self._hub.async_update()
        state = self._hub.temp_state[self._serial]
        self._state = state
        return True

    @property
    def device_class(self):
        return self._deviceclass


    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        state = self._hub.temp_state[self._serial]
        return {
        "Temperature": state,
        "Serial No": self._serial,
        "Name": self._name
        }
