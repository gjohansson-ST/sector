"""Adds Temp sensors for Sector integration."""
import logging

from homeassistant.components.sensor import (
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):

    sector_hub = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    thermometers = await sector_hub.get_thermometers()

    tempsensors = []
    for sensor in thermometers:
        name = await sector_hub.get_name(sensor, "temp")
        _LOGGER.debug("Sector: Fetched Label %s for serial %s", name, sensor)
        description = SensorEntityDescription(
            key=sensor,
            name=name,
            unit_of_measurement=TEMP_CELSIUS,
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_TEMPERATURE,
        )
        tempsensors.append(
            SectorAlarmTemperatureSensor(sector_hub, coordinator, description)
        )

    if tempsensors:
        async_add_entities(tempsensors)
    else:
        _LOGGER.debug("No tempsensors to add")
        return False

    return True


class SectorAlarmTemperatureSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, hub, coordinator, description):
        self._hub = hub
        super().__init__(coordinator)
        self._serial = description.key
        self._attr_name = description.name
        self._attr_unique_id: str = "sa_temp_" + str(description.key)
        self.entity_description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self._attr_name,
            "manufacturer": "Sector Alarm",
            "model": "Temperature",
            "sw_version": "master",
            "via_device": (DOMAIN, "sa_hub_" + str(self._hub.alarm_id)),
        }

    @property
    def state(self):
        return self._hub.temp_state[self._serial]

    @property
    def extra_state_attributes(self):
        return {"Serial No": self._serial}
