"""Adds Temp sensors for Sector integration."""
import logging
import asyncio
from datetime import timedelta
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    UpdateFailed,
)
from homeassistant.const import DEVICE_CLASS_TEMPERATURE
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """ No setup from yaml """
    return True


async def async_setup_entry(hass, entry, async_add_entities):

    sector_hub = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    thermometers = await sector_hub.get_thermometers()

    tempsensors = []
    for sensor in thermometers:
        name = await sector_hub.get_name(sensor, "temp")
        _LOGGER.debug("Sector: Fetched Label %s for serial %s", name, sensor)
        tempsensors.append(
            SectorAlarmTemperatureSensor(sector_hub, coordinator, sensor, name)
        )

    if tempsensors is not None and tempsensors != []:
        async_add_entities(tempsensors)
    else:
        return False

    return True


class SectorAlarmTemperatureDevice(Entity):
    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Sector Alarm",
            "model": "Temperature",
            "sw_version": "master",
            "via_device": (DOMAIN, "sa_hub_" + str(self._hub.alarm_id)),
        }


class SectorAlarmTemperatureSensor(CoordinatorEntity, SectorAlarmTemperatureDevice):
    def __init__(self, hub, coordinator, sensor, name):
        self._hub = hub
        super().__init__(coordinator)
        self._serial = sensor
        self._name = name
        self._state = None
        self._uom = TEMP_CELSIUS
        self._deviceclass = DEVICE_CLASS_TEMPERATURE

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return "sa_temp_" + str(self._serial)

    @property
    def name(self):
        return "Sector " + str(self._name) + " " + str(self._serial)

    @property
    def available(self):
        return True

    @property
    def unit_of_measurement(self):
        return self._uom

    @property
    def device_class(self):
        return self._deviceclass

    @property
    def state(self):
        try:
            self._state = self._hub.temp_state[self._serial]
        except:
            return None
        return self._state

    @property
    def device_state_attributes(self):
        try:
            state = self._hub.temp_state[self._serial]
        except:
            state = None
        return {"Temperature": state, "Serial No": self._serial, "Name": self._name}
