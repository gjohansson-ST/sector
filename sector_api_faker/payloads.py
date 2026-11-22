"""Sector-shaped API response payloads derived from the device inventory."""

from __future__ import annotations

from typing import Any

from .climate import ClimateSensor, climate_value
from .inventory import (
    ALARM_PANEL,
    DEVICES,
    HOUSECHECK_DEVICES,
    LOCK_DEVICES,
    PLUGS_BY_ID,
)
from .models import HouseCheckDevice
from .state import FakerState


def panel_list() -> list[dict[str, str]]:
    return [
        {
            "PanelId": ALARM_PANEL.serial,
            "DisplayName": ALARM_PANEL.label,
        }
    ]


def panel_info(state: FakerState) -> dict[str, Any]:
    with state.lock:
        locks = [
            {
                "Label": device.label,
                "Serial": device.serial,
                "SerialNo": device.serial,
                "BatteryLow": device.low_battery,
                "Status": state.lock_states[device.serial],
            }
            for device in LOCK_DEVICES
        ]
        smartplugs = [
            {
                "Id": device.plug_id,
                "Label": device.label,
                "Serial": device.serial,
                "SerialNo": device.serial,
                "Status": state.plug_states[device.serial],
            }
            for device in PLUGS_BY_ID.values()
        ]
    return {
        "PanelId": ALARM_PANEL.serial,
        "Capabilities": ["UseLegacyHomeScreen"] if state.legacy_mode else [],
        "PanelCodeLength": ALARM_PANEL.code_length,
        "QuickArmEnabled": ALARM_PANEL.quick_arm_enabled,
        "CanPartialArm": ALARM_PANEL.can_partial_arm,
        "Locks": locks,
        "Temperatures": [],
        "Smartplugs": smartplugs,
    }


def panel_status(state: FakerState) -> dict[str, bool | int]:
    with state.lock:
        status = state.alarm_status
    return {"IsOnline": ALARM_PANEL.online, "Status": status}


def lock_status(state: FakerState) -> list[dict[str, Any]]:
    with state.lock:
        return [
            {
                "Label": device.label,
                "Serial": device.serial,
                "SerialNo": device.serial,
                "BatteryLow": device.low_battery,
                "Status": state.lock_states[device.serial],
            }
            for device in LOCK_DEVICES
        ]


def smart_plug_status(state: FakerState) -> list[dict[str, str]]:
    with state.lock:
        return [
            {
                "Id": device.plug_id,
                "Label": device.label,
                "Serial": device.serial,
                "SerialNo": device.serial,
                "Status": state.plug_states[device.serial],
            }
            for device in PLUGS_BY_ID.values()
        ]


def legacy_temperatures() -> list[dict[str, str]]:
    return [
        {
            "Label": device.label,
            "SerialNo": device.serial,
            "Serial": device.serial,
            "Temperature": str(climate_value(device, "temperature")),
        }
        for device in DEVICES
        if device.temperature is not None
        and device.device_type.upper() not in {"CAMERAPIR", "KEYPAD"}
    ]


def housecheck_devices(endpoint: str) -> dict[str, Any]:
    devices = [
        _housecheck_device(device)
        for device in HOUSECHECK_DEVICES
        if device.endpoint == endpoint
    ]
    return {"Floors": [{"Rooms": [{"Devices": devices}]}]}


def climate_components(sensor: ClimateSensor) -> dict[str, Any]:
    api_name = "Temperature" if sensor == "temperature" else "Humidity"
    components: list[dict[str, Any]] = []
    for device in DEVICES:
        if getattr(device, sensor) is None:
            continue
        component: dict[str, Any] = {
            "SerialNo": device.serial,
            "Label": device.label,
            "Name": f"{device.label} Sensor",
            "Type": device.device_type,
        }
        if device.low_battery is not None:
            component["LowBattery"] = device.low_battery
        component[api_name] = climate_value(device, sensor)
        components.append(component)
    return {"Sections": [{"Places": [{"Components": components}]}]}


def logs(state: FakerState, page_number: int, page_size: int) -> dict[str, Any]:
    start = (page_number - 1) * page_size
    with state.lock:
        records = state.logs[start : start + page_size]
    return {"Records": records}


def _housecheck_device(device: HouseCheckDevice) -> dict[str, Any]:
    result: dict[str, Any] = {
        "SerialString": device.serial,
        "Label": device.label,
        "Name": device.label,
        "Type": device.device_type,
    }
    for api_name, value in (
        ("LowBattery", device.low_battery),
        ("Alarm", device.alarm),
        ("Closed", device.closed),
    ):
        if value is not None:
            result[api_name] = value
    return result
