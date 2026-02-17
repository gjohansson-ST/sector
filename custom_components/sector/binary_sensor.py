"""Binary sensor platform for Sector Alarm integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from custom_components.sector.const import RUNTIME_DATA

from .coordinator import (
    DeviceRegistry,
    SectorAlarmConfigEntry,
    SectorDeviceDataUpdateCoordinator,
)
from .entity import SectorAlarmBaseEntity

_LOGGER = logging.getLogger(__name__)


BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="low_battery",
        name="Battery",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    BinarySensorEntityDescription(
        key="closed",
        name="Door/Window",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    BinarySensorEntityDescription(
        key="leak_detected",
        name="Leak detected",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    BinarySensorEntityDescription(
        key="alarm",
        name="Alarm",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    BinarySensorEntityDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SectorAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sector Alarm binary sensors."""
    coordinators: list[SectorDeviceDataUpdateCoordinator] = entry.runtime_data[
        RUNTIME_DATA.DEVICE_COORDINATORS
    ]
    entities: list[
        SectorAlarmBinarySensor
        | SectorAlarmPanelOnlineBinarySensor
        | SectorAlarmClosedSensor
    ] = []

    for coordinator in coordinators:
        _proccess_coordinator(coordinator, entities)

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug(
            f"No binary sensor entities to add for '{coordinator.__class__.__name__}'"
        )


def _proccess_coordinator(
    coordinator: DataUpdateCoordinator,
    entities: list[
        SectorAlarmBinarySensor
        | SectorAlarmPanelOnlineBinarySensor
        | SectorAlarmClosedSensor
    ],
):
    device_registry: DeviceRegistry = coordinator.data.get(
        "device_registry", DeviceRegistry()
    )
    devices: dict[str, Any] = device_registry.fetch_devices_by_coordinator(
        coordinator.name
    )
    for serial_no, device in devices.items():
        device_name: str = device["name"]
        device_model = device["model"]
        for entity_model, entity in device.get("entities", {}).items():
            sensors = entity.get("sensors", {})

            for description in BINARY_SENSOR_TYPES:
                if description.key not in sensors:
                    continue

                if description.key == "online":
                    _add_if_unique(
                        SectorAlarmPanelOnlineBinarySensor(
                            coordinator,
                            serial_no,
                            description,
                            device_name,
                            device_model,
                            entity_model,
                        ),
                        entities,
                    )
                    _LOGGER.debug(
                        "Added %s sensor for device %s", description.name, serial_no
                    )
                elif description.key == "closed":
                    _add_if_unique(
                        SectorAlarmClosedSensor(
                            coordinator,
                            serial_no,
                            description,
                            device_name,
                            device_model,
                            entity_model,
                        ),
                        entities,
                    )
                    _LOGGER.debug(
                        "Added %s sensor for device %s", description.name, serial_no
                    )
                else:
                    _add_if_unique(
                        SectorAlarmBinarySensor(
                            coordinator,
                            serial_no,
                            description,
                            device_name,
                            device_model,
                            entity_model,
                        ),
                        entities,
                    )
                    _LOGGER.debug(
                        "Added %s sensor for device %s", description.name, serial_no
                    )


def _add_if_unique(entity, entities):
    for i, existing in enumerate(entities):
        if (
            existing._serial_no == entity._serial_no
            and existing._attr_unique_id == entity._attr_unique_id
        ):
            # Always keep real device value
            if existing._device_model == existing._entity_model:
                return

            if entity._device_model == entity._entity_model:
                entities[i] = entity
            return

    # No duplicate found
    entities.append(entity)


class SectorAlarmBinarySensor(SectorAlarmBaseEntity, BinarySensorEntity):
    """Base class for a Sector Alarm binary sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        serial_no: str,
        entity_description: BinarySensorEntityDescription,
        device_name: str,
        device_model: str,
        entity_model: str,
    ) -> None:
        """Initialize the sensor with device info."""
        super().__init__(
            coordinator, serial_no, device_name, device_model, entity_model
        )
        self.entity_description = entity_description
        self._sensor_type = entity_description.key
        self._attr_unique_id = f"{serial_no}_{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return True if the sensor is on."""
        entity: dict[str, Any] = self.entity_data or {}
        sensors = entity.get("sensors", {})
        return sensors.get(self._sensor_type, None)


class SectorAlarmClosedSensor(SectorAlarmBinarySensor):
    """Binary sensor for detecting closed status of doors/windows."""

    @property
    def is_on(self) -> bool:
        """Return True if the door/window is open (closed: False)."""
        entity: dict[str, Any] = self.entity_data or {}
        sensors = entity.get("sensors", {})
        is_closed: bool = sensors.get("closed", None)

        if is_closed is None:
            return None  # type: ignore
        else:
            return not is_closed  # negated because we display Open status


class SectorAlarmPanelOnlineBinarySensor(SectorAlarmBinarySensor, BinarySensorEntity):
    """Binary sensor for the Sector Alarm panel online status."""

    @property
    def is_on(self):
        """Return True if the panel is online."""
        entity: dict[str, Any] = self.entity_data or {}
        sensors = entity.get("sensors", {})
        return sensors.get("online", None)
