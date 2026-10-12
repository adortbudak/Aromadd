"""In-memory model of the diffuser's on-board schedule with debounced saving.

The diffuser stores 5 slots for each weekday. This manager keeps a copy of the
whole week, exposes one *working* set of 5 slots for the currently selected day
(or group of days), and writes the working set back to the device a few seconds
after the last edit so the entities behave like ordinary settings.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .aromadd_device import AromaddDevice

_LOGGER = logging.getLogger(__name__)

SLOT_COUNT = 5
SAVE_DELAY = 3.0  # seconds after the last edit before writing to the device

# Select option -> day mask. Monday = bit 0 is confirmed on hardware (as is
# Tuesday = bit 1); Wednesday..Sunday follow the same order.
DAY_GROUPS: dict[str, int] = {
    "Monday": 1,
    "Tuesday": 2,
    "Wednesday": 4,
    "Thursday": 8,
    "Friday": 16,
    "Saturday": 32,
    "Sunday": 64,
    "Weekdays (Mon-Fri)": 0x1F,
    "Weekend (Sat-Sun)": 0x60,
    "Every day": 0x7F,
}

# Intensity presets: (run seconds, wait seconds) applied to the active schedules.
# Mist strength is the run/wait ratio, so these are roughly 0.7%, 1.4% and 5.3%.
PRESETS: dict[str, tuple[int, int]] = {
    "Light": (5, 720),
    "Normal": (5, 360),
    "Strong": (10, 180),
}

STATUS_IDLE = "idle"
STATUS_LOADING = "loading"
STATUS_PENDING = "pending"
STATUS_SAVING = "saving"
STATUS_SAVED = "saved"
STATUS_ERROR = "error"


def _slot_bytes(slot: dict[str, Any]) -> dict[str, Any]:
    """Convert a stored slot ("HH:MM" strings) to the device writer's format."""
    return {
        "start_h": int(slot["start"][:2]), "start_m": int(slot["start"][3:5]),
        "end_h": int(slot["end"][:2]), "end_m": int(slot["end"][3:5]),
        "work": slot["work"], "pause": slot["pause"], "enabled": slot["enabled"],
    }


def describe_slots(slots: list[dict[str, Any]]) -> str:
    """Human-readable summary of the enabled slots."""
    parts = [
        f"{s['start']}-{s['end']} ({s['work']}s on / {s['pause']}s off)"
        for s in slots if s["enabled"]
    ]
    return ", ".join(parts) if parts else "No active slots"


class ScheduleManager:
    """Holds the schedule cache and the editable working copy."""

    def __init__(self, hass: HomeAssistant, device: AromaddDevice) -> None:
        self.hass = hass
        self._device = device
        self.week: list[list[dict[str, Any]]] | None = None
        self.working: list[dict[str, Any]] = []
        self.selected = "Monday"
        self.status = STATUS_IDLE
        self.error: str | None = None
        self._dirty = False
        self._unsub_timer: Callable[[], None] | None = None
        self._save_lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []

    # -- listeners -----------------------------------------------------------
    def register_callback(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb) if cb in self._listeners else None

    @callback
    def _changed(self) -> None:
        for cb in list(self._listeners):
            cb()

    # -- state ---------------------------------------------------------------
    @property
    def available(self) -> bool:
        return self.week is not None

    @property
    def mask(self) -> int:
        return DAY_GROUPS[self.selected]

    @property
    def _days(self) -> list[int]:
        return [d for d in range(7) if self.mask & (1 << d)]

    @property
    def days_differ(self) -> bool:
        """True if the selected days don't all hold the same slots right now."""
        if self.week is None:
            return False
        first = self.week[self._days[0]]
        return any(self.week[d] != first for d in self._days[1:])

    def _load_working(self) -> None:
        assert self.week is not None
        self.working = [dict(s) for s in self.week[self._days[0]]]

    def _cancel_timer(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    # -- actions -------------------------------------------------------------
    async def async_refresh(self) -> None:
        """Read the schedule from the device, discarding unsaved edits."""
        self._cancel_timer()
        self._dirty = False
        self.status, self.error = STATUS_LOADING, None
        self._changed()
        try:
            week = await self._device.async_read_schedule()
            if len(week) < 7:
                raise RuntimeError(f"device returned {len(week)} day blocks, expected 7")
            self.week = week
            self._load_working()
            self.status = STATUS_IDLE
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("schedule refresh failed: %s", err)
            self.status, self.error = STATUS_ERROR, str(err)
        self._changed()

    async def async_select(self, option: str) -> None:
        """Switch the day (group) being edited, saving pending edits first."""
        await self.async_save()
        self.selected = option
        if self.week is not None:
            self._load_working()
        self._changed()

    @callback
    def update_slot(self, index: int, **changes: Any) -> None:
        """Edit a slot in the working copy and schedule a save."""
        if self.week is None:
            return
        self.working[index].update(changes)
        self._dirty = True
        self.status, self.error = STATUS_PENDING, None
        self._cancel_timer()
        self._unsub_timer = async_call_later(self.hass, SAVE_DELAY, self._timer_fired)
        self._changed()

    @property
    def preset(self) -> str | None:
        """Preset matching every active schedule of the selected day, else None."""
        active = [s for s in self.working if s["enabled"]]
        if not active:
            return None
        for name, (work, pause) in PRESETS.items():
            if all(s["work"] == work and s["pause"] == pause for s in active):
                return name
        return None

    @callback
    def apply_preset(self, name: str) -> None:
        """Set run/wait seconds of the active schedules to a preset."""
        if self.week is None:
            return
        work, pause = PRESETS[name]
        for slot in self.working:
            if slot["enabled"]:
                slot["work"], slot["pause"] = work, pause
        self.update_slot(0)  # marks dirty, schedules the save, notifies listeners

    @callback
    def _timer_fired(self, _now: Any) -> None:
        self._unsub_timer = None
        self.hass.async_create_task(self.async_save())

    async def async_save(self) -> None:
        """Write the working copy to every selected day and read the week back."""
        self._cancel_timer()
        async with self._save_lock:
            if not self._dirty or self.week is None:
                return
            mask = self.mask
            slots = [dict(s) for s in self.working]
            self._dirty = False
            self.status, self.error = STATUS_SAVING, None
            self._changed()
            try:
                week = await self._device.async_write_schedule_and_read(
                    mask, [_slot_bytes(s) for s in slots]
                )
                if len(week) >= 7:
                    self.week = week
                if not self._dirty:
                    self._load_working()
                self.status = STATUS_SAVED if not self._dirty else STATUS_PENDING
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("schedule save failed: %s", err)
                self._dirty = True
                self.status, self.error = STATUS_ERROR, str(err)
            self._changed()

    async def async_sync_clock(self) -> None:
        await self._device.async_sync_clock()

    async def async_shutdown(self) -> None:
        """Flush pending edits (best effort) when the entry unloads."""
        try:
            await asyncio.wait_for(self.async_save(), timeout=30)
        except Exception:  # noqa: BLE001
            pass
        self._cancel_timer()
