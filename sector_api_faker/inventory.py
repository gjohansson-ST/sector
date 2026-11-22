"""The single source of truth for devices exposed by the Sector API faker."""

from __future__ import annotations

import os

from .models import (
    AlarmPanelDevice,
    Device,
    HouseCheckDevice,
    LockDevice,
    SmartPlugDevice,
)

ALARM_PANEL = AlarmPanelDevice(
    serial=os.environ.get("PANEL_ID", "1234"),
    label=os.environ.get("PANEL_NAME", "Faker Home"),
    device_type="Alarm panel",
)

LOCK_DEVICES = (
    LockDevice(
        serial="LOCK001",
        label="Front Door",
        device_type="Smart Lock",
        low_battery=False,
        initial_status="lock",
    ),
    LockDevice(
        serial="LOCK002",
        label="Garage Door",
        device_type="Smart Lock",
        low_battery=False,
        initial_status="lock",
    ),
)

SMART_PLUG_DEVICES = (
    SmartPlugDevice(
        serial="PLUG001",
        label="Living Room Plug",
        device_type="Smart Plug",
        plug_id="plug-001",
    ),
    SmartPlugDevice(
        serial="PLUG002",
        label="Bedroom Plug",
        device_type="Smart Plug",
        plug_id="plug-002",
    ),
)

HOUSECHECK_DEVICES = (
    HouseCheckDevice(
        serial="DOOR001",
        label="Front Door",
        device_type="Doors and Windows",
        endpoint="doorsandwindows",
        low_battery=False,
        alarm=False,
        closed=True,
    ),
    HouseCheckDevice(
        serial="DOOR002",
        label="Back Door",
        device_type="Doors and Windows",
        endpoint="doorsandwindows",
        low_battery=False,
        alarm=False,
        closed=False,
    ),
    HouseCheckDevice(
        serial="WINDOW001",
        label="Living Room Window",
        device_type="Doors and Windows",
        endpoint="doorsandwindows",
        low_battery=False,
        alarm=False,
        closed=True,
    ),
    HouseCheckDevice(
        serial="SMOKE001",
        label="Hallway Smoke Detector",
        device_type="Smoke Detector",
        endpoint="smokedetectors",
        low_battery=True,
        alarm=False,
        temperature=22.0,
        humidity=45.0,
    ),
    HouseCheckDevice(
        serial="LEAK001",
        label="Bathroom Leak Detector",
        device_type="Leakage Detectors",
        endpoint="leakagedetectors",
        low_battery=False,
        alarm=False,
    ),
    HouseCheckDevice(
        serial="CAMERA001",
        label="Living Room Camera",
        device_type="CameraPIR",
        low_battery=False,
        temperature=21.0,
        humidity=47.0,
    ),
    HouseCheckDevice(
        serial="KEYPAD001",
        label="Hallway Keypad",
        device_type="KeyPad",
        low_battery=False,
        temperature=20.0,
        humidity=42.0,
    ),
    HouseCheckDevice(
        serial="CLIMATE002",
        label="Bedroom",
        device_type="Temperatures",
        low_battery=False,
        temperature=19.0,
    ),
    HouseCheckDevice(
        serial="CLIMATE003",
        label="Kitchen",
        device_type="Temperatures",
        temperature=21.5,
        humidity=44.0,
    ),
)

DEVICES: tuple[Device, ...] = (
    ALARM_PANEL,
    *LOCK_DEVICES,
    *SMART_PLUG_DEVICES,
    *HOUSECHECK_DEVICES,
)

DEVICES_BY_SERIAL = {device.serial: device for device in DEVICES}
LOCKS_BY_SERIAL = {device.serial: device for device in LOCK_DEVICES}
PLUGS_BY_ID = {device.plug_id: device for device in SMART_PLUG_DEVICES}
