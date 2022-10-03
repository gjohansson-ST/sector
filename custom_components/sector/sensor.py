"""Adds Temp sensors for Sector integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TEMP, DOMAIN
from .coordinator import SectorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Sensor platform."""

    coordinator: SectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not entry.data[CONF_TEMP]:
        return

    sensor_list = []
    for panel, panel_data in coordinator.data.items():
        if "temp" in panel_data:
            for sensor, sensor_data in panel_data["temp"].items():
                name = sensor_data["name"]
                description = SensorEntityDescription(
                    key=sensor,
                    name=name,
                    native_unit_of_measurement=TEMP_CELSIUS,
                    state_class=SensorStateClass.MEASUREMENT,
                    device_class=SensorDeviceClass.TEMPERATURE,
                )
                sensor_list.append(
                    SectorAlarmTemperatureSensor(coordinator, description, panel)
                )

    if sensor_list:
        async_add_entities(sensor_list)


class SectorAlarmTemperatureSensor(
    CoordinatorEntity[SectorDataUpdateCoordinator], SensorEntity
):
    """Sector Temp sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SectorDataUpdateCoordinator,
        description: SensorEntityDescription,
        panel_id: str,
    ) -> None:
        """Initialize Temp sensor."""
        super().__init__(coordinator)
        self._panel_id = panel_id
        self.entity_description = description
        self._attr_unique_id: str = "sa_temp_" + str(description.key)
        self._attr_native_value = self.coordinator.data[panel_id]["temp"][
            description.key
        ].get("temperature")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"sa_temp_{description.key}")},
            name=description.name,
            manufacturer="Sector Alarm",
            model="Temperature",
            sw_version="master",
            via_device=(DOMAIN, f"sa_hub_{panel_id}"),
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Extra states for sensor."""
        return {"Serial No": self.entity_description.key}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            temp := self.coordinator.data[self._panel_id]["temp"]
            .get(self.entity_description.key, {})
            .get("temperature")
        ):
            self._attr_native_value = temp

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity available."""
        return True
