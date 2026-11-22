"""Stable randomized readings for climate-capable devices."""

from __future__ import annotations

import random
import time
from typing import Literal

from .models import Device

ClimateSensor = Literal["temperature", "humidity"]


def climate_value(
    device: Device, sensor: ClimateSensor, now: float | None = None
) -> float:
    baseline = getattr(device, sensor)
    if baseline is None:
        raise ValueError(f"{device.serial} does not have a {sensor} sensor")

    bucket = int((time.time() if now is None else now) // 1800)
    variation = 0.8 if sensor == "temperature" else 4.0
    noise = random.Random(f"{device.serial}:{sensor}:{bucket}").uniform(
        -variation, variation
    )
    return round(baseline + noise, 1)
