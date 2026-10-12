"""Shared base for schedule entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL
from .schedule import ScheduleManager


def device_info(entry: ConfigEntry) -> dr.DeviceInfo:
    address: str = entry.data[CONF_ADDRESS]
    return dr.DeviceInfo(
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        identifiers={(DOMAIN, address)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=MODEL,
    )


class AromaddScheduleEntity(Entity):
    """Entity bound to the schedule manager; unavailable until it is loaded."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _always_available = False

    def __init__(
        self, entry: ConfigEntry, manager: ScheduleManager, key: str, name: str
    ) -> None:
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = device_info(entry)

    @property
    def available(self) -> bool:
        return self._always_available or self._manager.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._manager.register_callback(self.async_write_ha_state))


class AromaddSlotEntity(AromaddScheduleEntity):
    """Entity for one field of one schedule slot."""

    def __init__(self, entry, manager, slot: int, field: str, label: str) -> None:
        super().__init__(entry, manager, f"slot{slot + 1}_{field}", f"Schedule {slot + 1} {label}")
        self._slot = slot
        self._field = field
        # Schedules 3-5 are rarely needed; keep them out of the way until enabled.
        self._attr_entity_registry_enabled_default = slot < 2

    @property
    def _value(self):
        w = self._manager.working
        return w[self._slot][self._field] if w else None


class AromaddTankEntity(Entity):
    """Entity bound to the tank tracker (always available)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, tracker, key: str, name: str) -> None:
        self._tracker = tracker
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._tracker.register_callback(self.async_write_ha_state))
