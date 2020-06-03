import logging
import asyncio
from datetime import timedelta
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

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

class SectorAlarmTemperatureSensor(Entity):
    """Representation of a Sector Alarm Temperature Sensor."""

    def __init__(self, hub, name):
        """Initialize the sensor."""
        self._hub = hub
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    async def async_update(self):
        """ Update temperature """
        state = self._hub.temp_state[self._name]
        self._state = state

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """ Return the state attributes. """
        state = self._hub.temp_state[self._name]
        return {"Temperature": state}
