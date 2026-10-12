"""Synthetic fixtures only. Prices, battery size and weather are invented."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from math import sin, pi

from .model import Scenario, Site, Slot


def scenario(kind: str = "sunny") -> Scenario:
    if kind not in ("sunny", "cloudy", "away", "impossible", "stale"):
        raise ValueError("unknown demo scenario")
    start = datetime(2030, 1, 15, tzinfo=timezone(timedelta(hours=10)))
    slots = []
    for i in range(48):
        hour = i / 2
        sun = max(0, sin(pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 0
        pv = 17 * sun ** 1.6
        if kind == "cloudy":
            pv *= 0.23 if 9 <= hour <= 14 else 0.50
        home = 0.6 + (1.6 if 17 <= hour <= 21 else 0) + (0.5 if 6 <= hour <= 8 else 0)
        available = not (kind == "away" and 7 <= hour < 18)
        slots.append(Slot((start + timedelta(minutes=i * 30)).isoformat(), round(pv, 4), home,
                          0.08 if 9 <= hour < 16 else 0.35, 0, available))
    return Scenario(kind, (start - timedelta(hours=24 if kind == "stale" else 1)).isoformat(),
                    30, 180 if kind == "impossible" else 20,
                    (start + timedelta(hours=23)).isoformat(), Site(), tuple(slots))
