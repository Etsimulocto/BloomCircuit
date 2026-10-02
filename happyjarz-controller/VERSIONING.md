# HAPPY JARZ Versioning Rules

These rules are mandatory for HAPPY JARZ releases and behavior-changing builds.

## Current versions

- Desktop app: `happyjarz-controller/VERSION`
- Firmware: `happyjarz-controller/firmware/VERSION`

The current release pair is:

- App `1.1.0`
- Firmware `0.6.0`

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
