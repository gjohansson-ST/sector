"""Adds Temp sensors for Sector integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TEMP, DOMAIN
from .coordinator import SectorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform for Sector integration."""

    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not entry.data[CONF_TEMP]:
        return

    sensor_list = []
    for panel, panel_data in coordinator.data.items():
        if "temp" in panel_data:
            for sensor, sensor_data in panel_data["temp"].items():
                name = sensor_data["name"]
                serial = sensor_data["serial"]
                description = SensorEntityDescription(
                    key=sensor,
                    name=name,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    state_class=SensorStateClass.MEASUREMENT,
                    device_class=SensorDeviceClass.TEMPERATURE,
                )
                sensor_list.append(
                    SectorAlarmTemperatureSensor(coordinator, description, panel, serial)
                )

    if sensor_list:
        async_add_entities(sensor_list)


class SectorAlarmTemperatureSensor(
    CoordinatorEntity[SectorDataUpdateCoordinator], SensorEntity
):
    """Representation of a Sector temperature sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        description: SensorEntityDescription,
        panel_id: str,
        serial: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        self._serial = serial
        self.entity_description = description
        self._attr_unique_id: str = f"sa_temp_{serial}"
        self._attr_native_value = self.coordinator.data[panel_id]["temp"][
            description.key
        ].get("temperature")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"sa_temp_{serial}")},
            name=description.name,
            manufacturer="Sector Alarm",
            model="Contact and Shock Detector",
            sw_version="master",
            via_device=(DOMAIN, f"sa_hub_{panel_id}"),
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Extra states for sensor."""
        return {"Serial No": self._serial}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            temp := self.coordinator.data[self._panel_id]["temp"]
            .get(self.entity_description.key, {})
            .get("temperature")
        ):
            self._attr_native_value = temp
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True
