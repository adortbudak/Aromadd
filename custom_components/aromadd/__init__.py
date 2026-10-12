"""The Aromadd Diffuser integration."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .aromadd_device import AromaddDevice
from .const import DOMAIN
from .schedule import ScheduleManager
from .tank import TankTracker

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aromadd Diffuser from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )
    if ble_device is None:
        raise ConfigEntryNotReady(
            f"Could not find Aromadd device with address {address}. "
            "Make sure it is powered on and in range of a Bluetooth adapter."
        )

    device = AromaddDevice(ble_device)
    device.schedule = ScheduleManager(hass, device)
    device.tank = TankTracker(hass, entry.entry_id, device.schedule)
    await device.tank.async_load()
    entry.async_on_unload(device.tank.async_start())
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device

    @callback
    def _async_update_ble_device(
        service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Keep the cached BLEDevice fresh as HA rediscovers it."""
        device.set_ble_device(service_info.device)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble_device,
            BluetoothCallbackMatcher({"address": address.upper()}),
            BluetoothScanningMode.ACTIVE,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Load the on-board schedule without delaying setup; the entities stay
    # unavailable until it arrives (press "Reload schedule" if the phone app
    # was holding the connection).
    entry.async_create_background_task(
        hass, device.schedule.async_refresh(), "aromadd initial schedule load"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.data[DOMAIN][entry.entry_id].schedule.async_shutdown()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        device: AromaddDevice = hass.data[DOMAIN].pop(entry.entry_id)
        await device.async_disconnect()
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok
