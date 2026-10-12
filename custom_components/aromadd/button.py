"""Buttons: refresh the schedule from the device, sync the clock."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import AromaddScheduleEntity, AromaddTankEntity
from .tank import TANK_ML


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data[DOMAIN][entry.entry_id].schedule
    async_add_entities([
        AromaddRefreshButton(entry, manager),
        AromaddClockButton(entry, manager),
        AromaddRefillButton(entry, hass.data[DOMAIN][entry.entry_id].tank),
    ])


class AromaddRefreshButton(AromaddScheduleEntity, ButtonEntity):
    _always_available = True
    _attr_icon = "mdi:refresh"

    def __init__(self, entry, manager) -> None:
        super().__init__(entry, manager, "refresh_schedule", "Reload schedule")

    async def async_press(self) -> None:
        await self._manager.async_refresh()
        if self._manager.error:
            raise HomeAssistantError(
                f"Could not read the schedule: {self._manager.error}. "
                "Close the Aromadd phone app and try again."
            )


class AromaddClockButton(AromaddScheduleEntity, ButtonEntity):
    _always_available = True
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, entry, manager) -> None:
        super().__init__(entry, manager, "sync_clock", "Sync clock")

    async def async_press(self) -> None:
        try:
            await self._manager.async_sync_clock()
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Could not sync clock: {err}") from err


class AromaddRefillButton(AromaddTankEntity, ButtonEntity):
    """Press after refilling the tank to reset the estimate to full."""

    _attr_icon = "mdi:water-plus"

    def __init__(self, entry, tracker) -> None:
        super().__init__(entry, tracker, "refill_tank", "Tank refilled")

    async def async_press(self) -> None:
        await self._tracker.async_set_remaining(TANK_ML)
