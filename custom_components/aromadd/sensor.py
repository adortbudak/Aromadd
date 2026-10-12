"""Sensors describing the schedule being edited and the save status."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .entity import AromaddScheduleEntity, AromaddTankEntity
from .schedule import DAY_GROUPS, describe_slots
from .tank import TANK_ML


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data[DOMAIN][entry.entry_id].schedule
    tracker = hass.data[DOMAIN][entry.entry_id].tank
    async_add_entities([
        AromaddScheduleSummary(entry, manager),
        AromaddScheduleStatus(entry, manager),
        AromaddDaysLeft(entry, tracker),
        AromaddLiquidPercent(entry, tracker),
    ])


class AromaddScheduleSummary(AromaddScheduleEntity, SensorEntity):
    """Plain-language summary of the selected day; the full week is an attribute."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, entry, manager) -> None:
        super().__init__(entry, manager, "schedule_summary", "Schedule summary")

    @property
    def native_value(self) -> str:
        return describe_slots(self._manager.working)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        m = self._manager
        names = list(DAY_GROUPS)[:7]
        attrs: dict[str, Any] = {
            "day": m.selected,
            "days_differ": m.days_differ,
            "week": {n: describe_slots(m.week[i]) for i, n in enumerate(names)} if m.week else {},
        }
        return attrs


class AromaddScheduleStatus(AromaddScheduleEntity, SensorEntity):
    """idle / loading / pending / saving / saved / error."""

    _always_available = True
    _attr_icon = "mdi:cloud-sync-outline"

    def __init__(self, entry, manager) -> None:
        super().__init__(entry, manager, "schedule_status", "Schedule status")

    @property
    def native_value(self) -> str:
        return self._manager.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"error": self._manager.error}


class AromaddDaysLeft(AromaddTankEntity, SensorEntity):
    """Days until the tank runs out at the current schedule's average use."""

    _attr_icon = "mdi:calendar-end"
    _attr_native_unit_of_measurement = "d"

    def __init__(self, entry, tracker) -> None:
        super().__init__(entry, tracker, "days_left", "Estimated days left")

    @property
    def native_value(self):
        return self._tracker.days_left


class AromaddLiquidPercent(AromaddTankEntity, SensorEntity):
    _attr_icon = "mdi:percent"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, entry, tracker) -> None:
        super().__init__(entry, tracker, "liquid_percent", "Liquid level")

    @property
    def native_value(self) -> float:
        return round(self._tracker.remaining_ml / TANK_ML * 100, 1)
