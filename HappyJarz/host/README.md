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
