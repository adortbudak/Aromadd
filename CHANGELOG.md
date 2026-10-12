# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Liquid estimate**: the diffuser cannot report its level, so the integration integrates
  the spraying implied by the schedule (rated 0.001 mL per second, 500 mL tank) and keeps
  the total across restarts. New entities: `number` *Liquid remaining* (set it to what is in
  the tank now), `sensor` *Liquid level* (%) and *Estimated days left*, and `button`
  *Tank refilled*. Spraying done outside the schedule (manual power-on) is not counted.

### Changed
- Schedule entity names now sort in the order active, begin, end, run time, wait time.

## [0.4.0] - 2026-10-12

### Added
- **Schedule editor entities**, so no helpers, scripts or Apply button are needed:
  - `select` *Schedule day* (Monday..Sunday, Weekdays, Weekend, Every day)
  - per schedule (1-5): `time` start/end, `number` spray/pause seconds, `switch` enabled
    (schedules 3-5 are disabled by default in the entity registry)
  - `sensor` *Schedule summary* (plain-language, full week as an attribute) and
    *Schedule status* (idle/pending/saving/saved/error)
  - `button` *Reload schedule* and *Sync clock*
- Edits are **saved automatically** about 3 seconds after the last change; the write and a
  read-back of the whole week share one connection. The schedule is loaded at startup.
- Verified on hardware: Monday, Tuesday and Sunday day blocks.

## [0.3.0] - 2026-10-12

### Added
- On-board **schedule** support, decoded from app captures. New entity actions on the
  switches: `aromadd.set_schedule` (days + up to 5 slots of start, end, work seconds,
  pause seconds), `aromadd.read_schedule` (returns the 7 per-day blocks) and
  `aromadd.sync_clock` (sets the unit's clock from Home Assistant's time zone).
- Mist strength is the slot's work/pause seconds: this unit has no separate level.
- Commands retry once if the first connection attempt times out.

### Notes
- Frame format: `57 16 <day-mask> + 5 x 9-byte slots` (start h/m, end h/m, enabled,
  work s BE16, pause s BE16). Day mask bit 0 = Monday (confirmed); Tue..Sun are bits
  1..6 (Tuesday confirmed on a real unit; the rest follow the same order).
- Tested on a unit advertising as `Diffuser.A5.WIFI` (firmware `U5_A1...V1.0.20251127`).

### Planned
- LED light control (capture needed).

## [0.2.5] - 2026-06-20

### Fixed
- Avoid a ~30s delay (and HA service timeout) when sending a command: only the
  vendor `0xFFFx` characteristics are used now. Previously the code also tried to
  subscribe to the standard Service Changed characteristic (`0x2a05`), whose
  notify-subscribe blocked for 30s before failing. Confirmed: `fff2` is the write
  characteristic (handle 0x12) and `fff1` the notify characteristic (handle 0x17),
  matching the original packet capture.

## [0.2.4] - 2026-06-20

### Fixed
- **Switches did nothing on the real device.** Characteristic auto-detection
  classified the vendor `0xFFFx` control characteristics (FFF1..FFF4, expressed
  in the standard Bluetooth base form) as non-vendor, so commands were written to
  a generic GATT characteristic and ignored. Vendor detection now recognises the
  `0xFF00-0xFFFF` proprietary range, and the device layer subscribes to all
  candidate notify characteristics and tries each candidate write characteristic,
  keeping whichever returns a state report (and caching it for next time).

## [0.2.3] - 2026-06-17

### Added
- Local brand images in `custom_components/aromadd/brand/` (`icon.png`,
  `icon@2x.png`, `logo.png`, `logo@2x.png`) so the integration icon shows in the
  Home Assistant UI. This is the supported method for custom integrations as of
  HA 2026.3; the home-assistant/brands repo no longer accepts custom integrations.

## [0.2.2] - 2026-06-17

### Fixed
- **Control failure** (`BleakCharacteristicNotFoundError: Characteristic 18 was
  not found`). The integration wrote by raw GATT handle (`0x12`), but handle
  numbers differ between BLE stacks, so the handle from the phone capture did not
  resolve on the Home Assistant host. The write/notify characteristics are now
  discovered from the live GATT table at connect time (handle hint first, then a
  writable/notifiable + vendor-service fallback).
- Silenced a `SyntaxWarning` from the escape sequence in `const.py`'s docstring.

## [0.2.1] - 2026-06-17

### Fixed
- **Critical:** removed the invalid Bluetooth `local_name` matcher `"U5*"`. A
  wildcard in the first three characters is rejected by Home Assistant and caused
  the core `bluetooth` component to fail to set up, cascading to every
  Bluetooth-dependent integration (esphome, bluetooth_adapters, bermuda, bedjet,
  ibeacon, etc.). Remaining matchers (`"U5 Pro*"`, `"Aromadd*"`) are valid.

## [0.2.0] - 2026-06-16

### Added
- **Fan** switch (opcode 0x5703): ON payload `570310`, OFF payload `570300`,
  confirmed via state report `5303 xx`. Separate from the main Power switch.

### Changed
- Refactored the BLE device layer to handle multiple controls; the switch
  platform is now description-driven (Power + Fan).

## [0.1.0] - 2026-06-16

First public release. Bluetooth LE control of the Aromadd U5 Pro diffuser.

### Added
- `switch` entity for on/off control of the Aromadd U5 Pro.
- Device-confirmed state: each command is verified against the diffuser's own
  state-report notification (`53 08 01` / `53 08 00`) rather than assumed.
- Automatic Bluetooth discovery plus a manual device-picker config flow.
- Connect → write → confirm → disconnect handling so the official Aromadd app can
  still reconnect.
- Reverse-engineered BLE protocol from an HCI snoop log:
  frame `A5 AA AC | XOR(payload) | <payload> | C5 CC CA`; commands written to GATT
  handle `0x0012`, state reported via notifications on handle `0x0017`.
- HACS packaging: `hacs.json`, brand assets, and a `validate.yaml` workflow running
  the HACS Action and hassfest.

### Known limitations
- On/off only; mist level, LED, and timers are not yet implemented.
- Changes made with the physical button or phone app while Home Assistant is not
  connected are not pushed back to HA.

[Unreleased]: https://github.com/ajachierno/Aromadd/compare/v0.2.5...HEAD
[0.2.5]: https://github.com/ajachierno/Aromadd/releases/tag/v0.2.5
[0.2.4]: https://github.com/ajachierno/Aromadd/releases/tag/v0.2.4
[0.2.3]: https://github.com/ajachierno/Aromadd/releases/tag/v0.2.3
[0.2.2]: https://github.com/ajachierno/Aromadd/releases/tag/v0.2.2
[0.2.1]: https://github.com/ajachierno/Aromadd/releases/tag/v0.2.1
[0.2.0]: https://github.com/ajachierno/Aromadd/releases/tag/v0.2.0
[0.1.0]: https://github.com/ajachierno/Aromadd/releases/tag/v0.1.0
