# HAPPY JARZ Versioning Rules

These rules are mandatory for HAPPY JARZ releases and behavior-changing builds.

## Current versions

- Desktop app: `happyjarz-controller/VERSION`
- Firmware: `happyjarz-controller/firmware/VERSION`

The current release pair is:

- App `1.6.0`
- Firmware `0.16.0`

## Mandatory bump rule

Any change that alters user-visible behavior, device behavior, protocol behavior, hardware handling, deployment behavior, or diagnostics MUST bump the relevant version before merge.

Examples that require a firmware bump:

- touch behavior
- OLED/menu behavior
- battery/power reporting
- LED patterns or brightness rules
- screensavers
- serial protocol commands or fields
- startup/shutdown behavior
- hardware pin or calibration changes

Examples that require an app bump:

- controller UI behavior
- launcher/autostart behavior
- controller-side protocol handling
- new tabs, controls, telemetry, diagnostics, or settings
- updater/deployment behavior

If one change affects both sides, bump both.

Documentation-only edits that do not alter runtime behavior do not require a version bump.

## Semantic versioning

Use `MAJOR.MINOR.PATCH`.

- PATCH: bug fix with no intentional feature expansion
- MINOR: new feature, new supported behavior, or meaningful capability change
- MAJOR: incompatible protocol/product architecture change

Do not keep rebuilding under the same version number.

## Source of truth

Never hard-code a new release number in only one UI string.

- The desktop controller reads its version from `happyjarz-controller/VERSION`.
- The firmware flash pipeline injects the value from `happyjarz-controller/firmware/VERSION` into `HJ_FW_VERSION` before verification/compile/upload.
- The staged firmware verifier must reject a firmware image whose embedded version does not match the firmware version file.

Legacy filenames such as `happyjarz_controller_v0_3_3.py`, `happyjarz_integrated_v0_5.ino`, and `flash_happyjarz_v0_5.sh` may remain as implementation filenames until a deliberate cleanup. They are NOT release-version sources.

## Release checklist

Before merging a runtime change:

1. Decide whether app, firmware, or both changed.
2. Bump the required VERSION file(s).
3. Update release/status docs if behavior changed.
4. Stage firmware through the standard flasher.
5. Confirm staged verification PASS includes the expected firmware version.
6. Confirm the desktop title/log reports the expected app version.
7. Confirm `HJ|IDENTITY` reports the expected firmware version.

If those versions do not agree, stop. Do not flash or publish the build.


### Host Mini synchronization

App 1.4.0 / firmware 0.12.0 are paired because the integrated Mini depends on new firmware protocol:
- GET CAPS
- KEY <logical action>
- GET OLED
- STREAM OLED ON/OFF
- HJ|OLED framebuffer frames

Older firmware may still run the host application, but the synchronized Mini controls/mirror are not considered supported without firmware 0.12.0 or later.


### App 1.5.0

Host-only update. Firmware remains 0.12.0.

Adds semantic Linux gamepad support with event* preferred and js* fallback, full 12-action mapping for future FULL hardware, and blue OLED mirror pixels matching the physical display.


### Firmware 0.13.0

Four-lamp pattern cleanup.

Replaces the remaining two-lamp pattern assumptions with an explicit four-output engine. App protocol remains compatible with host app 1.5.0; this is a firmware behavior update rather than a host protocol break.


### Firmware 0.14.0

Adds stand-topology chase effects based on the physical four-lamp geometry:
1 top-left, 2 top-right, 3 side-left, 4 side-right.

Host app remains 1.5.0 and exposes the new pattern names through its existing pattern dropdown.


### Firmware 0.15.0

Color-rolling chase update.

All topology chase patterns now generate their own slowly rotating hue while preserving their existing physical motion paths.


### App 1.6.0 / Firmware 0.16.0

100-pattern release.

Adds a 56-entry descriptor-driven pattern bank on top of the existing 44 effects, for exactly 100 registered patterns total. The host dropdown and firmware registry are updated together.
