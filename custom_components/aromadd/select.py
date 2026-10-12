"""Day selector for the schedule editor."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import AromaddScheduleEntity
from .schedule import DAY_GROUPS


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data[DOMAIN][entry.entry_id].schedule
    async_add_entities([AromaddDaySelect(entry, manager)])


class AromaddDaySelect(AromaddScheduleEntity, SelectEntity):
    """Which day (or group of days) the slot entities show and edit."""

    _attr_icon = "mdi:calendar-week"
    _attr_options = list(DAY_GROUPS)

    def __init__(self, entry, manager) -> None:
        super().__init__(entry, manager, "schedule_day", "Schedule day")

    @property
    def current_option(self) -> str:
        return self._manager.selected

    async def async_select_option(self, option: str) -> None:
        await self._manager.async_select(option)
