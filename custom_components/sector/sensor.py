import logging
import asyncio
from datetime import timedelta
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.const import DEVICE_CLASS_TEMPERATURE

import custom_components.sector as sector

DEPENDENCIES = ["sector"]

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):

    sector_hub = hass.data[sector.DATA_SA]

    thermometers = await sector_hub.get_thermometers()

    if thermometers is not None:
        async_add_entities(
            SectorAlarmTemperatureSensor(sector_hub, thermometer)
            for thermometer in thermometers
        )
    else:
        return False

    return True

class SectorAlarmTemperatureSensor(Entity):

    def __init__(self, hub, serial):
        self._hub = hub
        self._serial = serial
        self._state = None
        self._uom = TEMP_CELSIUS
        self._deviceclass = DEVICE_CLASS_TEMPERATURE

    @property
    def name(self):
        return self._name

    @property
    def unit_of_measurement(self):
        return self._uom

    async def async_update(self):
        update = await self._hub.async_update()
        state = self._hub.temp_state[self._name]
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
        state = self._hub.temp_state[self._name]
        return {"Temperature": state}
