"""In-memory alarm, lock, plug, and audit-log state."""

from __future__ import annotations

import threading
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .inventory import ALARM_PANEL, LOCK_DEVICES, PLUGS_BY_ID

DEFAULT_TIME_ZONE = "Europe/Stockholm"


class FakerState:
    legacy_mode: bool

    def __init__(
        self, time_zone: str = DEFAULT_TIME_ZONE, legacy_mode: bool = False
    ) -> None:
        try:
            self.time_zone = ZoneInfo(time_zone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(
                f"Unknown or unavailable IANA time zone: {time_zone!r}"
            ) from error
        self.lock = threading.RLock()
        self.legacy_mode = legacy_mode
        self.alarm_status = ALARM_PANEL.initial_alarm_status
        self.lock_states = {
            device.serial: device.initial_status for device in LOCK_DEVICES
        }
        self.plug_states = {
            device.serial: device.initial_status
            for device in PLUGS_BY_ID.values()
        }
        self.logs: list[dict[str, str]] = []

    def update_alarm(self, status: int, event_type: str) -> None:
        with self.lock:
            self.alarm_status = status
            self._add_log(event_type, "")

    def update_lock(self, serial: str, status: str) -> bool:
        with self.lock:
            device = next(
                (device for device in LOCK_DEVICES if device.serial == serial),
                None,
            )
            if device is None:
                return False
            self.lock_states[serial] = status
            self._add_log(status, device.label)
            return True

    def update_plug(self, plug_id: str, status: str) -> bool:
        with self.lock:
            device = PLUGS_BY_ID.get(plug_id)
            if device is None:
                return False
            self.plug_states[device.serial] = status
            return True

    def _add_log(self, event_type: str, lock_name: str) -> None:
        self.logs.insert(
            0,
            {
                "User": "Faker User",
                "Channel": "Home Assistant",
                "Time": datetime.now(self.time_zone).isoformat(),
                "EventType": event_type,
                "LockName": lock_name,
            },
        )
        del self.logs[1000:]
