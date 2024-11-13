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
    lock_status: str
    low_battery: str  # Needs to be checked
    model: str = "Smart Lock"


@dataclass
class Devices:
    """Dataclass for devices."""

    name: str
    serial_no: str
    device_status: str  # Needs to be checked
    model: str
    type: str


@dataclass
class PanelStatus:
    """Dataclass for Alarm Panel."""

    alarm_state: int
    is_online: bool
