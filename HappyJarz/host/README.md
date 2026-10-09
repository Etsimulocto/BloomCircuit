# HAPPY JARZ Host Layer

This will contain shared Pi/PC host behavior.

Planned responsibilities:
- USB device detection
- identity/capability parsing
- release-manifest lookup
- safe update selection
- firmware update orchestration
- Mini app
- logical gamepad/keyboard/input routing
- host screensaver integration
- future Windows support

Pi support should be stabilized first. Windows support can be added after SIMPLE and FULL device profiles are established so the project does not fragment into many temporary builds.


## Architecture contracts

See:
- `../docs/HOST_APP.md`
- `../docs/SYNCHRONICITY.md`

The central design goal is hardware / USB / host-app synchronicity. Host UI state follows authoritative device state rather than simply caching commands it sent.

## Current synchronized release

Host app: **1.8.4**

Firmware: **0.17.13**

The host continues to treat device state as authoritative. Current firmware also reports accessory pause/resume and battery-warning events. One-hour sleep remains device-local so the Jar can keep time and service its alarm without a host connection.

## Gamepad/menu parity

Firmware `0.17.13` finalizes the logical input contract. Host Mini clicks and semantic Linux gamepad events still enter as `KEY UP/DOWN/LEFT/RIGHT/A/B`, but those events are now merged before every normal OLED menu/game router.

CLOCK, SETTINGS, INFO, LIGHTS, GAMES/ARCADE, MAIN MENU and HOME therefore receive the same logical controls as the physical copper touch inputs. Physical touch remains separately identifiable only for the one-hour sleep wake check.
