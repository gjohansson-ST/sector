"""Typed definitions for Sector Alarm devices and their capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HouseCheckEndpoint = Literal[
    "doorsandwindows",
    "leakagedetectors",
    "smokedetectors",
]


@dataclass(frozen=True, kw_only=True)
class Device:
    serial: str
    label: str
    device_type: str
    low_battery: bool | None = None
    temperature: float | None = None
    humidity: float | None = None


@dataclass(frozen=True, kw_only=True)
class AlarmPanelDevice(Device):
    code_length: int = 6
    quick_arm_enabled: bool = True
    can_partial_arm: bool = True
    online: bool = True
    initial_alarm_status: int = 1


@dataclass(frozen=True, kw_only=True)
class LockDevice(Device):
    initial_status: Literal["lock", "unlock"] = "lock"


@dataclass(frozen=True, kw_only=True)
class SmartPlugDevice(Device):
    plug_id: str
    initial_status: Literal["On", "Off"] = "Off"


@dataclass(frozen=True, kw_only=True)
class HouseCheckDevice(Device):
    endpoint: HouseCheckEndpoint | None = None
    alarm: bool | None = None
    closed: bool | None = None
