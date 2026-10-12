"""Work/pause duration entities for the schedule slots."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime

from .const import DOMAIN
from .entity import AromaddSlotEntity, AromaddTankEntity
from .tank import TANK_ML
from .schedule import SLOT_COUNT


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data[DOMAIN][entry.entry_id].schedule
    async_add_entities([AromaddLiquidNumber(entry, hass.data[DOMAIN][entry.entry_id].tank)])
    async_add_entities(
        AromaddSlotNumber(entry, manager, i, field, label, hi)
        for i in range(SLOT_COUNT)
        for field, label, hi in (("work", "run time", 3600), ("pause", "wait time", 7200))
    )


class AromaddSlotNumber(AromaddSlotEntity, NumberEntity):
    """Spray (work) or pause seconds. Longer spray / shorter pause = stronger scent."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, entry, manager, slot, field, label, maximum) -> None:
        super().__init__(entry, manager, slot, field, label)
        self._attr_native_min_value = 1 if field == "work" else 0
        self._attr_native_max_value = maximum

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._manager.update_slot(self._slot, **{self._field: int(value)})


class AromaddLiquidNumber(AromaddTankEntity, NumberEntity):
    """Estimated liquid left. Set it to what is in the tank now; it counts down."""

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = TANK_ML
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "mL"
    _attr_icon = "mdi:cup-water"

    def __init__(self, entry, tracker) -> None:
        super().__init__(entry, tracker, "liquid_remaining", "Liquid remaining")

    @property
    def native_value(self) -> float:
        return round(self._tracker.remaining_ml, 2)

    @property
    def extra_state_attributes(self) -> dict:
        t = self._tracker
        use = t.daily_use_ml
        return {
            "percent": round(t.remaining_ml / TANK_ML * 100, 1),
            "tank_capacity_ml": TANK_ML,
            "average_use_ml_per_day": round(use, 3) if use is not None else None,
        }

    async def async_set_native_value(self, value: float) -> None:
        await self._tracker.async_set_remaining(value)
