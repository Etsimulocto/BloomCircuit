# BloomPetz Desktop / Raspberry Pi App

The Raspberry Pi companion is now partially working rather than purely planned.

## Current mini app

`bloompetz_mini.py` currently provides:

- automatic serial connection to the BloomPetz ESP32-S3
- four-line OLED screen mirroring
- keyboard arrow + A/B controls routed into the same firmware input path as the physical touch controls
- compact 192x114 desktop window
- pet-name header
- randomized readable app-only color themes
- left/right decorative falling-particle lanes matching the physical OLED side-art concept
- disconnect handling suitable for plug/unplug use

`bloompetz_plug_watch.py` and `install_bloompetz_autostart.sh` provide the Raspberry Pi auto-launch path.

Physical copper controls remain primary; the desktop app is a mirror/controller, not a replacement for device-local play.

## Current USB behavior

The firmware emits `BP|SCREEN|...` records whenever the four-line display changes. The mini app mirrors those records directly, so HOME sayings, status changes, menus, creator screens, STATS pages, minigame prompts, and marquee updates can all be reflected without maintaining a second copy of the game UI.

Keyboard input is sent back as logical UP / DOWN / LEFT / RIGHT / A / B events and handled by the same firmware `handleInput()` path used by the hardware controls.

## Planned expansion

The larger desktop layer can grow into:

- full 200-stat/history views and graphs
- archive of unlimited `.bloompet` files
- restore archived pets to one of three device slots
- automatic backup on USB connection
- pet library and metadata editing
- firmware/content installation
- diagnostics/service tools
- richer pet and screensaver management

Keep desktop backup/library behavior separate from ESP32 pet simulation logic. The ESP32 remains authoritative for the active pet state and core interaction loop.
