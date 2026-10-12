"""Switch platform for the Aromadd Diffuser (power + fan)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_platform
import voluptuous as vol
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aromadd_device import AromaddDevice
from .entity import AromaddSlotEntity
from .schedule import SLOT_COUNT
from .const import CONTROL_FAN, CONTROL_POWER, DOMAIN, MANUFACTURER, MODEL


@dataclass(frozen=True, kw_only=True)
class AromaddSwitchDescription(SwitchEntityDescription):
    """Describes an Aromadd switch."""

    control: str
    setter: Callable[[AromaddDevice, bool], Awaitable[None]]


SWITCHES: tuple[AromaddSwitchDescription, ...] = (
    AromaddSwitchDescription(
        key=CONTROL_POWER,
        translation_key=CONTROL_POWER,
        icon="mdi:air-purifier",
        control=CONTROL_POWER,
        setter=lambda device, on: device.async_set_power(on),
    ),
    AromaddSwitchDescription(
        key=CONTROL_FAN,
        translation_key=CONTROL_FAN,
        icon="mdi:fan",
        control=CONTROL_FAN,
        setter=lambda device, on: device.async_set_fan(on),
    ),
)


# Day bits for the schedule mask. 0x7F = every day. Monday = bit 0 is confirmed
# from a capture; Tue..Sun = bits 1..6 follows the same order (not yet verified).
DAY_BITS = {"mon": 1, "tue": 2, "wed": 4, "thu": 8, "fri": 16, "sat": 32, "sun": 64}

SLOT_SCHEMA = vol.Schema(
    {
        vol.Required("start"): cv.time,
        vol.Required("end"): cv.time,
        vol.Required("work"): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
        vol.Required("pause"): vol.All(vol.Coerce(int), vol.Range(min=0, max=7200)),
        vol.Optional("enabled", default=True): cv.boolean,
    }
)

SET_SCHEDULE_SCHEMA = {
    vol.Optional("days", default=list(DAY_BITS)): vol.All(
        cv.ensure_list, [vol.In(list(DAY_BITS))]
    ),
    vol.Required("slots"): vol.All(cv.ensure_list, [SLOT_SCHEMA], vol.Length(min=1, max=5)),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aromadd switches from a config entry."""
    device: AromaddDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AromaddSwitch(entry, device, description) for description in SWITCHES
    )
    async_add_entities(
        AromaddSlotEnabled(entry, device.schedule, i, "enabled", "active")
        for i in range(SLOT_COUNT)
    )
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_schedule", SET_SCHEDULE_SCHEMA, "async_service_set_schedule"
    )
    platform.async_register_entity_service(
        "read_schedule", None, "async_service_read_schedule",
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(
        "sync_clock", None, "async_service_sync_clock"
    )


class AromaddSwitch(SwitchEntity):
    """A switch backed by one Aromadd BLE control.

    Each command is confirmed by the device's state-report notification, so the
    reported state reflects what the diffuser acknowledged. Changes made with
    the physical button or the phone app while HA isn't connected are not pushed.
    """

    _attr_has_entity_name = True
    entity_description: AromaddSwitchDescription

    def __init__(
        self,
        entry: ConfigEntry,
        device: AromaddDevice,
        description: AromaddSwitchDescription,
    ) -> None:
        """Initialise the switch entity."""
        self._device = device
        self.entity_description = description
        address: str = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the last confirmed state for this control."""
        return self._device.state(self.entity_description.control)

    async def async_added_to_hass(self) -> None:
        """Register for state-change callbacks from the device."""
        self.async_on_remove(
            self._device.register_callback(self._handle_device_update)
        )

    @callback
    def _handle_device_update(self) -> None:
        """Update HA state when the device reports a change."""
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn this control on."""
        await self.entity_description.setter(self._device, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn this control off."""
        await self.entity_description.setter(self._device, False)
        self.async_write_ha_state()

    async def async_service_set_schedule(self, days, slots) -> None:
        """Write the on-board schedule for the chosen days."""
        mask = 0
        for day in days:
            mask |= DAY_BITS[day]
        parsed = [
            {
                "start_h": slot["start"].hour, "start_m": slot["start"].minute,
                "end_h": slot["end"].hour, "end_m": slot["end"].minute,
                "work": slot["work"], "pause": slot["pause"],
                "enabled": slot["enabled"],
            }
            for slot in slots
        ]
        try:
            await self._device.async_set_schedule(mask, parsed)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Could not set schedule: {err}") from err

    async def async_service_read_schedule(self) -> ServiceResponse:
        """Return the schedule stored on the diffuser (7 day blocks)."""
        try:
            days = await self._device.async_read_schedule()
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Could not read schedule: {err}") from err
        return {"day_blocks": days}

    async def async_service_sync_clock(self) -> None:
        """Set the diffuser clock to Home Assistant's time."""
        try:
            await self._device.async_sync_clock()
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Could not sync clock: {err}") from err


class AromaddSlotEnabled(AromaddSlotEntity, SwitchEntity):
    """Turn one schedule slot on or off."""

    _attr_icon = "mdi:calendar-check"

    @property
    def is_on(self) -> bool | None:
        return self._value

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._manager.update_slot(self._slot, enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._manager.update_slot(self._slot, enabled=False)
