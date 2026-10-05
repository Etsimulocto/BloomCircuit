# BloomPetz Firmware

ESP32-S3 runtime lives here.

## Current build

`bloompetz_v0_1.ino` is the first functional vertical slice.

Implemented now:

- proven Happy Jarz six-touch GPIO map
- proven GPIO7 APA106 custom RMT layer
- three persistent pet slots
- 200 developmental float stats per pet
- fixed four-line / 16-character UI contract
- eight daily actions
- randomized three-direction D-pad Simon sequence
- response-speed growth from 0.0001 to 0.0050
- 25 weighted/random developmental rolls per first daily action completion
- once-per-day reward flag per action
- 12.5 food/energy cost per rewarded action
- full 100 -> 0 eight-action daily energy cycle
- feed-at-empty behavior
- three treats per calendar day
- midnight daily flag/treat reset without resetting the stomach
- Preferences blob persistence with checksum
- USB serial screen mirror and service commands
- touch and LED diagnostics

## OLED boundary

The repository still does not contain the known-good physical OLED driver. Do not invent or replace it while debugging BloomPetz.

`physicalOledRender()` is intentionally the single integration boundary. The rest of the firmware already renders the exact four display lines through `BP|SCREEN` USB records, so the desktop app can mirror and test the UI before the physical OLED layer is imported.

## Build target

ESP32-S3 SuperMini using the Arduino ESP32 core.

Use USB CDC on boot, matching the known-good Happy Jarz setup.

Typical FQBN:

```bash
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

Serial protocol: `115200 baud`.

## Important v0.1 commands

```text
HELLO
GET STATUS
GET SLOTS
GET STATS
GET SCREEN
SAVE
FEED
TREAT
SET SLOT 1
SET DATE 2026-10-04
CREATE 1|Lophire|Cat|[=^.^=] zZz
ACTION PLAY
DIAG TOUCH
DIAG LED
RECAL TOUCH
```

The desktop app automatically supplies `SET DATE` when it connects until a final device RTC/NTP architecture is selected.

## Data relationship

The 200 stats are stored compactly as indexes `0..199` on the ESP32.

`../data/stats/stat_manifest.json` defines the stable category/index map, while each category JSON contains its 10 alphabetized human-readable names.

`../data/actions/action_weights.json` mirrors the compiled v0.1 action/category weighting map for tuning.

Once public `.bloompet` saves exist, do not reorder the manifest. Future structural changes require save migration/versioning.

## Diagnostics

Follow `../docs/V0_1_TEST_PLAN.md` before changing higher layers.

BloomCore rule: if `DIAG LED` passes, do not rewrite the proven APA106 driver to fix pet/UI behavior. If `DIAG TOUCH` passes, do not change capacitive sensing while fixing action/menu logic.

## Planned split

As v0.1 proves itself on hardware, the integrated prototype can be separated into:

- `display.*`
- `touch.*`
- `pet_engine.*`
- `lighting.*`
- `save_system.*`
- `usb_protocol.*`
- `diagnostics.*`

Do not split merely for appearance before the first vertical slice is proven. Preserve known-good states before refactoring.
