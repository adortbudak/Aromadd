"""Start/end time entities for the schedule slots."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity

from .const import DOMAIN
from .entity import AromaddSlotEntity
from .schedule import SLOT_COUNT


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data[DOMAIN][entry.entry_id].schedule
    async_add_entities(
        AromaddSlotTime(entry, manager, i, field, label)
        for i in range(SLOT_COUNT)
        for field, label in (("start", "begin"), ("end", "end"))
    )


class AromaddSlotTime(AromaddSlotEntity, TimeEntity):
    _attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> time | None:
        v = self._value
        return time.fromisoformat(v) if v else None

    async def async_set_value(self, value: time) -> None:
        self._manager.update_slot(self._slot, **{self._field: value.strftime("%H:%M")})
