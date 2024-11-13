"""Models for Sector."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SectorData:
    """Dataclass for all data."""

    alarm: PanelStatus
    devices: Devices
    locks: Locks


@dataclass
class Locks:
    """Dataclass Locks."""

    name: str
    serial_no: str
    lock_status: str  # Which are valid?
    low_battery: bool
    sound_level: int
    autolock: bool
    model: str = "Smart Lock"


@dataclass
class Devices:
    """Dataclass for devices."""

    name: str
    serial_no: str
    device_status: int | bool  # Needs to be checked
    model: str
    type: str
    low_battery: bool
    closed: bool  # Only valid doors/windows
    alarm: bool  # Only valid doors/windows+smoke detectors+leakage detectors likely


@dataclass
class PanelStatus:
    """Dataclass for Alarm Panel."""

    alarm_state: int
    is_online: bool
    ready_to_arm: bool
