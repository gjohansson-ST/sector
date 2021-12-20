"""Adds Temp sensors for Sector integration."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .__init__ import SectorAlarmHub
from .const import CONF_TEMP, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Sensor platform."""

    sector_hub: SectorAlarmHub = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    if not entry.data[CONF_TEMP]:
        return

    thermometers = await sector_hub.get_thermometers()
    tempsensors = []
    for sensor in thermometers:
        name = await sector_hub.get_name(sensor, "temp")
        description = SensorEntityDescription(
            key=sensor,
            name=name,
            native_unit_of_measurement=TEMP_CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.TEMPERATURE,
        )
        tempsensors.append(
            SectorAlarmTemperatureSensor(sector_hub, coordinator, description)
        )

    if tempsensors:
        async_add_entities(tempsensors)


class SectorAlarmTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Sector Temp sensor."""

    def __init__(
        self,
        hub: SectorAlarmHub,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Temp sensor."""
        self._hub = hub
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id: str = "sa_temp_" + str(description.key)
        self._attr_native_value = self._hub.temp_state[description.key]

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
    def extra_state_attributes(self) -> dict:
        """Extra states for sensor."""
        return {"Serial No": self.entity_description.key}

    def update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._hub.temp_state[self.entity_description.key]
