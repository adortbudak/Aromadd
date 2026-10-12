# Aromadd Diffuser — Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/ajachierno/Aromadd/actions/workflows/validate.yaml/badge.svg)](https://github.com/ajachierno/Aromadd/actions/workflows/validate.yaml)

A custom [Home Assistant](https://www.home-assistant.io/) integration to control an
**Aromadd U5 Pro** essential-oil diffuser over **Bluetooth Low Energy (BLE)**.

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ajachierno&repository=Aromadd&category=integration)

It exposes the diffuser's **power** and **fan** as `switch` entities.

> [!NOTE]
> The BLE protocol was reverse-engineered from a real U5 Pro HCI snoop log, so
> **on/off works out of the box** — no extra configuration needed. Each command is
> confirmed by the device's own state-report notification rather than just assumed.
> See [`CAPTURE_GUIDE.md`](CAPTURE_GUIDE.md) if you want to capture additional
> commands (mist level, LED, timers) the same way.

## Features

- Confirmed control of the Aromadd U5 Pro over BLE:
  - **Power** switch (main on/off)
  - **Fan** switch (on/off)
- Automatic Bluetooth discovery (the device shows up in *Settings → Devices & Services*)
- Connects, sends the command, reads back the device's state report, then disconnects
  so the Aromadd phone app can still reconnect

## How it works (protocol)

Commands are framed as:

```
A5 AA AC | XOR(payload) | <payload> | C5 CC CA
```

- Written to the GATT characteristic at value handle `0x0012`
- The device reports state via notifications on value handle `0x0017`

| Control     | Action | Payload     | Full frame             | State report |
|-------------|--------|-------------|------------------------|--------------|
| Power       | ON     | `57 08 01`  | `a5aaac5e570801c5ccca` | `53 08 01`   |
| Power       | OFF    | `57 08 00`  | `a5aaac5f570800c5ccca` | `53 08 00`   |
| Fan         | ON     | `57 03 10`  | `a5aaac44570310c5ccca` | `53 03 10`   |
| Fan         | OFF    | `57 03 00`  | `a5aaac54570300c5ccca` | `53 03 00`   |

The diffuser echoes a state report (`53 …`) for each command, which the integration
uses to confirm the real state rather than assuming it.

## Schedules and clock

The diffuser has an on-board schedule (5 slots per day). Mist strength is set by each
slot's **work** and **pause** seconds. Actions (target one of the diffuser's switches):

```yaml
action: aromadd.set_schedule
target:
  entity_id: switch.my_diffuser_power
data:
  days: [mon, tue, wed, thu, fri]
  slots:
    - start: "08:00:00"
      end: "22:00:00"
      work: 10
      pause: 120
```

- `aromadd.read_schedule` returns the stored schedule as a response (7 day blocks, Mon..Sun).
- `aromadd.sync_clock` sets the diffuser's clock to Home Assistant's time.
- `set_schedule` replaces the whole day: slots you don't pass are disabled.
- Close the Aromadd phone app first; the diffuser accepts one connection at a time.

## Requirements

- Home Assistant **2024.8.0** or newer
- A Bluetooth adapter recognised by Home Assistant (built-in, USB dongle, or an
  [ESPHome Bluetooth Proxy](https://esphome.io/projects/?type=bluetooth) in range of
  the diffuser)
- The diffuser powered on and **not currently connected in the Aromadd phone app**
  (it allows only one BLE connection at a time)

## Installation

### Option A — HACS (recommended)

1. In HACS, open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/ajachierno/Aromadd` as an **Integration**.
3. Search for **Aromadd Diffuser** in HACS and install it.
4. Restart Home Assistant.

### Option B — Manual

1. Copy the `custom_components/aromadd` folder into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. The diffuser is usually **auto-discovered** — look for an "Aromadd Diffuser"
   discovery card in **Settings → Devices & Services** and click **Configure**.
2. If it isn't discovered automatically, click **+ Add Integration**, search for
   **Aromadd Diffuser**, and pick your device from the list of nearby Bluetooth
   devices (close the Aromadd phone app first so the device is connectable).

That's it — a switch entity appears that turns your diffuser on and off.

## Project layout

```
custom_components/aromadd/
├── __init__.py          # setup / teardown, keeps the BLE device fresh
├── aromadd_device.py    # BLE connect → write → confirm → disconnect logic
├── config_flow.py       # discovery + manual device picker
├── const.py             # domain + the decoded BLE protocol constants
├── manifest.json        # integration metadata + Bluetooth matchers
├── switch.py            # the on/off switch entity
├── strings.json
└── translations/en.json
```

## Limitations & notes

- **Power + fan on/off** for now. Mist/fan-speed levels and the LED use the same
  framing and can be added once their payloads are captured (see `CAPTURE_GUIDE.md`).
- **Scheduling:** rather than programming the diffuser's on-board timer, schedule the
  `switch` entities with Home Assistant automations — it's more flexible and is the
  standard Home Assistant approach. (The device's own schedule frame, opcode
  `0x5716`, is understood but not yet exposed; see `CAPTURE_GUIDE.md`.)
- State is confirmed at the moment a command is sent. Changes made with the physical
  button or the phone app while HA isn't connected are not pushed back to HA.
- BLE range applies. Use a Bluetooth proxy if the diffuser is far from your HA host.
- Handles (`0x0012` / `0x0017`) are taken from the U5 Pro. If a future firmware moves
  them, update `WRITE_HANDLE` / `NOTIFY_HANDLE` in `const.py`.

## Disclaimer

Unofficial community integration, not affiliated with or endorsed by Aromadd.
Use at your own risk. Licensed under the MIT License.


## Buy me a coffee

Did you find this helpful? Consider supporting additional development:

<a href="https://www.buymeacoffee.com/ajachiernoo" target="_blank">
  <img src="https://raw.githubusercontent.com/ajachierno/Aromadd/main/brand/bmc_button.png" alt="Buy me a coffee" height="50">
</a>

<br><br>

<a href="https://www.buymeacoffee.com/ajachiernoo" target="_blank">
  <img src="https://raw.githubusercontent.com/ajachierno/Aromadd/main/brand/buymeacoffee_qr.png" alt="Buy me a coffee QR code" width="200">
</a>
