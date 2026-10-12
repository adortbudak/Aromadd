"""Estimate how much scent liquid is left from the on-board schedule.

The manufacturer rates the unit at 0.001 mL per second of spraying and the
tank at 500 mL. The device cannot report its level, so this integrates the
spraying implied by the schedule (work / (work + pause) inside each enabled
window) minute by minute, and persists the running total.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .schedule import ScheduleManager

_LOGGER = logging.getLogger(__name__)

ML_PER_SECOND = 0.001
TANK_ML = 500.0
TICK = timedelta(minutes=1)
MAX_CATCH_UP = timedelta(days=7)


def _slot_fraction(slot: dict[str, Any]) -> float:
    cycle = slot["work"] + slot["pause"]
    return slot["work"] / cycle if cycle else 0.0


def _minutes(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:5])


def _window_minutes(slot: dict[str, Any]) -> int:
    start, end = _minutes(slot["start"]), _minutes(slot["end"])
    return end - start if end >= start else 1440 - start + end


def _in_window(slot: dict[str, Any], minute: int) -> bool:
    start, end = _minutes(slot["start"]), _minutes(slot["end"])
    if start == end:
        return False
    return start <= minute < end if start < end else (minute >= start or minute < end)


class TankTracker:
    """Running estimate of the liquid left in the tank."""

    def __init__(self, hass: HomeAssistant, entry_id: str, manager: ScheduleManager) -> None:
        self.hass = hass
        self._manager = manager
        self._store: Store = Store(hass, 1, f"aromadd_tank_{entry_id}")
        self.remaining_ml: float = TANK_ML
        self.last_tick: datetime = dt_util.utcnow()
        self._listeners: list[Callable[[], None]] = []

    def register_callback(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb) if cb in self._listeners else None

    @callback
    def _changed(self) -> None:
        for cb in list(self._listeners):
            cb()

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data:
            self.remaining_ml = float(data["remaining_ml"])
            self.last_tick = dt_util.parse_datetime(data["last_tick"]) or self.last_tick

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"remaining_ml": self.remaining_ml, "last_tick": self.last_tick.isoformat()}
        )

    @callback
    def async_start(self) -> Callable[[], None]:
        return async_track_time_interval(self.hass, self._async_tick, TICK)

    async def _async_tick(self, _now: Any = None) -> None:
        """Account for the spraying since the last tick (catches up after downtime)."""
        week = self._manager.week
        if week is None:
            return  # schedule unknown; keep last_tick so the time is counted later
        now = dt_util.utcnow()
        t = max(self.last_tick, now - MAX_CATCH_UP)
        used = 0.0
        while t < now:
            step = min(timedelta(minutes=1), now - t)
            mid = dt_util.as_local(t + step / 2)
            minute = mid.hour * 60 + mid.minute
            for slot in week[mid.weekday()]:
                if slot["enabled"] and _in_window(slot, minute):
                    used += step.total_seconds() * _slot_fraction(slot) * ML_PER_SECOND
            t += step
        self.last_tick = now
        self.remaining_ml = max(0.0, self.remaining_ml - used)
        await self._async_save()
        self._changed()

    async def async_set_remaining(self, ml: float) -> None:
        self.remaining_ml = max(0.0, min(TANK_ML, ml))
        self.last_tick = dt_util.utcnow()
        await self._async_save()
        self._changed()

    @property
    def daily_use_ml(self) -> float | None:
        """Average consumption per day over the week, from the current schedule."""
        week = self._manager.week
        if week is None:
            return None
        total = sum(
            _window_minutes(s) * 60 * _slot_fraction(s) * ML_PER_SECOND
            for day in week for s in day if s["enabled"]
        )
        return total / 7

    @property
    def days_left(self) -> float | None:
        use = self.daily_use_ml
        return round(self.remaining_ml / use, 1) if use else None

