# HAPPY JARZ Controller

**Current platform release pair:** desktop app **v1.6.0** + firmware **v0.16.0**

This subsystem is the PC/Raspberry Pi field-service and control layer for the HAPPY JARZ powered stand. It sits above the known-good ESP32-S3 light/touch/OLED hardware layer and is designed so desktop-side changes do not casually rewrite the proven APA106 timing.

## Release/version discipline

Authoritative files:

```text
happyjarz-controller/VERSION          # desktop app version
happyjarz-controller/firmware/VERSION # firmware version
```

Current values:

```text
App      1.8.3
Firmware 0.12.0
```

Legacy filenames such as `happyjarz_controller_v0_3_3.py`, `happyjarz_integrated_v0_5.ino`, and `flash_happyjarz_v0_5.sh` are compatibility names only. The flasher reads `firmware/VERSION`, injects it into `HJ_FW_VERSION`, and verifies the final staged build before upload.

## Current proven behavior

- identify a Jar over USB serial and reconnect after unplug/replug
- independent Light 1 / Light 2 / Light 3 / Light 4 color control
- full **0-100% LED brightness range** in firmware
- on-device SOLID brightness tuning under `MENU -> LIGHTS`
- expanded sensory/holiday/color pattern library
- six capacitive-touch controls
- OLED HOME/menu/status pages
- standalone CLOCK date/time editor with no PC or Wi-Fi required while powered
- SETTINGS editors for ALARM and TIMER
- board-native HAPPY ARCADE with seven mini-games
- board-local **INFO / MANUAL** with 12 help pages
- Fuel Gauge / `GET POWER` telemetry
- 30-second screensaver timeout with SAYINGS / SPIRAL / TRIPPY / PARTICLES / BLOOM / BREATHE / GLITTER
- persistent custom marquee sayings
- transient desktop MENU/GAME input modes that fall back to local JAR control when the USB CDC session disappears

## Bench-proven hardware map

Controller: **ESP32-S3 SuperMini**

### APA106 lighting

- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- APA106 #2 DOUT -> APA106 #3 DIN
- APA106 #3 DOUT -> APA106 #4 DIN
- common GND with ESP32
- proven byte order: **RGB**
- ESP32 data is 3.3V logic

Bench baseline, October 2, 2026:

- the original two-lamp prototype operated through the full **0-100%** firmware range with lamp VCC at **3.3V**
- the same prototype also operated through the full **0-100%** range with lamp VCC at **5V**
- no blue-collapse / blue-shift was observed during this test
- **24% at 3.3V** was already visually plenty for normal jar use
- **5V at 100% is extremely bright** and is better treated as an intentional high-output / room-glow mode than a normal default

The old 50% firmware hard cap is therefore retired. The product can keep the full range available while using a much lower normal brightness setting.

Do not route 5V into an ESP32 GPIO. The successful 5V test applies to the APA106 lamp supply, not the ESP32 data pin.

Known-good RMT timing:

- 10 MHz clock
- bit 0 ~= 4 ticks high / 14 low
- bit 1 ~= 14 high / 4 low
- ~100 us reset/latch

### Capacitive touch

Physical map:

- GPIO4 = UP
- GPIO5 = DOWN
- GPIO9 = LEFT
- GPIO10 = RIGHT
- GPIO1 = A
- GPIO2 = B

Current HOME behavior:

- UP = next pattern
- DOWN = previous pattern
- LEFT = next Light 1 color
- RIGHT = next Light 2 color
- A = open OLED menu
- B = no HOME action

The proven touch layer uses direct `touchRead()`, roughly +20% thresholding, ~60 ms qualification, slow baseline drift and one action per touch/release cycle.

### OLED

Current 4-wire I2C OLED:

- VCC -> 3.3V
- GND -> GND
- SDA -> GPIO8
- SCL -> GPIO6
- address `0x3C`
- U8g2 renderer
- 128x64 layout

## MENU behavior

Main menu includes:

- CLOCK
- LIGHTS
- GAMES
- SETTINGS
- SYSTEM
- INFO

### CLOCK

CLOCK can be set entirely on the board:

- LEFT / RIGHT = choose MONTH / DAY / YEAR / HOUR / MINUTE
- UP / DOWN = change selected value
- A = save
- B = cancel/back

Without a battery-backed RTC, the ESP32 cannot account for elapsed time while fully powered off.

### LIGHTS / SOLID brightness

The current board-local brightness editor exposes the real 0-100% range:

- UP / DOWN = +/-5%
- LEFT / RIGHT = +/-1%
- A = save
- B = save/back

Bench preference for normal sensory use is approximately **24% at 3.3V**. Higher values remain available for brighter wall/ceiling illumination.

### SETTINGS

Current SETTINGS entries:

- ALARM
- TIMER

The earlier DISPLAY brightness editor was removed because it did not provide a useful product control for this OLED module/build.

### INFO / MANUAL

INFO is a 12-page built-in manual that works with no PC or Wi-Fi. It covers HOME controls, colors, brightness, clock/date, alarm/timer, arcade, screensavers, power/battery, USB/Wi-Fi behavior, and firmware/system information.

Controls:

- RIGHT / DOWN / A = next page
- LEFT / UP = previous page
- B = back to main menu

## Battery / power telemetry

Current prototype sensing path:

- GPIO3 ADC
- divider ratio `2.0`
- provisional `BATTERY_CAL_FACTOR = 1.370`
- battery percentage is voltage-estimated, not coulomb counted

Bench reference:

```text
V 4.16
BAT 98%
PWR BAT
```

`CHG ?` is intentional when USB is present because the charger IC charging/full signal is not wired to an ESP32 GPIO.

## Four-lamp lighting

Firmware v0.12.0 retains the four-lamp APA106 chain on the proven GPIO7/RMT transport and adds the host KEY/CAPS/OLED synchronization protocol used by app v1.5.0.

- all four lamps remain on the same daisy-chain data pin
- Light 1 through Light 4 have independent persistent SOLID colors
- USB protocol exposes `SET LED1 COLOR` through `SET LED4 COLOR`
- `GET STATUS` reports `led1` through `led4`
- two-color presets alternate across all four lamps
- RAINBOW uses four phase-separated colors
- RANDOM generates four independent colors
- TWINKLE / SPARKLE use each lamp's own selected base color
- COLOR_SWAP rotates all four selected colors

The desktop Pi/PC controller shows four independent light cards in a 2x2 layout.

## Pattern library

Current patterns:

`SOLID`, `FADE`, `PULSE`, `RAINBOW`, `RANDOM`, `HUE_FADE`, `DUAL_HUE`, `BREATH`, `DRIFT`, `AURORA`, `OCEAN`, `LAVENDER`, `SUNSET`, `CHRISTMAS`, `HALLOWEEN`, `VALENTINE`, `EASTER`, `FOURTH`, `THANKSGIVING`, `CANDY`, `GALAXY`, `FIRE`, `ICE`, `FOREST`, `NEON`, `TWINKLE`, `SPARKLE`, `COLOR_SWAP`, `COMET`, `FIREFLY`, `BUBBLEGUM`, `OFF`.

## OLED screensavers

Screensaver mode starts after **30 seconds of inactivity**.

Modes:

- SAYINGS
- SPIRAL
- TRIPPY
- PARTICLES

Controls:

- LEFT / RIGHT = previous / next saver
- B = exit
- SPIRAL/TRIPPY/PARTICLES: UP/DOWN = speed
- SPIRAL/TRIPPY/PARTICLES: A = reseed / new universe

Custom sayings provide 8 persistent slots up to 96 characters each with `BUILTIN`, `CUSTOM`, and `MIXED` source modes.

## Current Pi flash workflow

From the feature branch during current development:

```bash
cd ~/BloomCircuit
git pull
bash happyjarz-controller/tools/flash_happyjarz_v0_5.sh
```

The helper stages the compatibility base, applies the current patch chain, verifies the final sketch, compiles with Arduino CLI, uploads, and restarts the watcher.

Current Arduino CLI FQBN:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

## Logs

```text
~/.happyjarz/plug_watch.log
~/.happyjarz/plug_watch_manual_start.log
~/.happyjarz/controller_launch.log
~/.happyjarz/controller.log
```

## Protocol + firmware

See [`PROTOCOL.md`](PROTOCOL.md), [`APP_PROTOCOL_V0_3.md`](APP_PROTOCOL_V0_3.md), [`firmware/README.md`](firmware/README.md), and [`VERSIONING.md`](VERSIONING.md).

## Failure boundary

Preserve known-good layers. If local LED/touch/OLED behavior works but the desktop UI does not, debug watcher/controller/protocol deployment first. If local LEDs/touch/OLED fail, debug firmware/hardware before changing the desktop app.


### Integrated Mini mirror/controller

App v1.7.0 / firmware v0.17.2 are the current synchronized pair. The Mini was introduced in app v1.4.0 and expanded in v1.5.0 with semantic gamepad routing and the blue OLED mirror.

Current behavior:
- actual 128x64 U8g2 framebuffer mirror from the device
- one shared serial connection; no second OLED serial owner
- 12 visible app controls
- SIMPLE enables UP/DOWN/LEFT/RIGHT/A/B
- X/Y/L/R/START/SELECT remain visible but disabled until a FULL device advertises them
- app keys use the same firmware input path consumed by physical copper touch
- returned HJ|EVENT input messages pulse the matching Mini button
- OLED telemetry is change-driven, Base64 encoded and capped at 4 Hz

Do not reconstruct menus independently in the host app. The physical device framebuffer is authoritative.


### Gamepad routing

App v1.5.0 carries forward the proven BloomPetz Linux gamepad lessons without copying its early hard-coded-index behavior.

Routing order:
1. prefer semantic `/dev/input/event*`
2. fall back to semantic `/dev/input/js*`
3. never read both paths simultaneously for the same controller

Mapped logical controls:
- D-pad / hat / left stick -> UP DOWN LEFT RIGHT
- South -> A
- East -> B
- West -> X
- North -> Y
- TL -> L
- TR -> R
- START -> START
- SELECT -> SELECT

All gamepad events enter the same host `KEY ...` path used by clickable Mini controls. Device capability gating still applies, so SIMPLE ignores FULL-only actions until a FULL device advertises them.

The Mini OLED mirror uses blue pixels on black to match the physical blue OLED modules.


### Synchronization rule

The app must not treat a sent command as proof of physical state.

```text
host request
  -> ESP32 applies state
  -> ESP32 reports authoritative state
  -> host redraws from returned state
```

This rule applies to live lamp color, OLED content, input events and future FULL-device controls.

Do not open a second serial connection for the Mini, OLED mirror or gamepad layer. The controller's existing HAPPY JARZ serial link is the single owner.


### Four-lamp pattern engine

Firmware v0.13.0 removes the remaining two-lamp assumptions from the pattern service.

The earlier four-lamp staging patch upgraded only a subset of effects while many patterns still used a two-color helper that repeated outputs as 1/2/1/2. The v0.13.0 engine defines all four lamp outputs intentionally.

Notable behavior:
- RAINBOW uses four phase-separated hues
- DRIFT / AURORA / OCEAN / SUNSET / VALENTINE / FOREST / BUBBLEGUM use four independently phased related colors
- EASTER / FOURTH / THANKSGIVING / NEON rotate their palettes across all four lamps
- CANDY / FIRE / ICE / RANDOM generate four independent outputs
- GALAXY gives each lamp its own phase and sparkle cadence
- TWINKLE / SPARKLE preserve each lamp's own base color
- COLOR_SWAP rotates all four saved base colors
- COMET now physically travels across all four lamps with a fading tail
- FIREFLY treats each lamp independently
- HUE_FADE and LAVENDER remain intentionally uniform across all four bulbs
- DUAL_HUE / CHRISTMAS / HALLOWEEN intentionally alternate two colors across four bulbs

FADE, BREATH and PULSE operate on the full four-entry `ledColor[]` state.

The final staged verifier requires `HAPPYJARZ_FOUR_LAMP_PATTERN_ENGINE_V2` so an old pair-based service cannot be flashed accidentally.


### Stand-topology chase family

Firmware v0.15.0 adds patterns based on the real stand geometry:

```text
1 = top-left jar light
2 = top-right jar light
3 = left-side box accent
4 = right-side box accent
```

New patterns:
- CHASE_CW
- CHASE_CCW
- JAR_CHASE
- SIDE_CHASE
- SWEEP_LR
- SWEEP_TS
- DIAGONAL
- PING_PONG
- DUAL_CHASE
- OPP_CHASE
- JAR_PULSE
- SIDE_ACCENT

The clockwise physical path is `1 -> 2 -> 4 -> 3`.

These effects use the saved per-lamp base colors rather than hard-coding a single chase color, so user color choices continue to matter.


### Color-rolling chase update

Firmware v0.15.0 keeps the stand-topology chase motion but moves the chase color slowly through the hue wheel.

Affected patterns:
- CHASE_CW
- CHASE_CCW
- JAR_CHASE
- SIDE_CHASE
- SWEEP_LR
- SWEEP_TS
- DIAGONAL
- PING_PONG
- DUAL_CHASE
- OPP_CHASE
- JAR_PULSE
- SIDE_ACCENT

The spatial animation cadence remains fast enough to read as a chase, while hue advances much more slowly so it does not look like a rainbow strobe.

The chase family no longer depends on saved base colors being non-white.


### 100-pattern library

App v1.6.0 / firmware v0.16.0 expand the HAPPY JARZ sensory library to exactly 100 registered patterns.

The first 44 patterns remain the existing hand-built effects and topology-aware chase family. The additional 56 patterns use a compact descriptor-driven engine so flash growth stays modest compared with writing 56 separate large effect functions.

New descriptor families include:
- water / ice
- fire / warm
- forest / green
- dream / cosmic
- pink / fruit
- neon / arcade
- weather / sky

Renderer modes include:
- four-lamp palette flow
- phased brightness wave
- physical sweep with tail
- soft glow
- independent sparkle
- pair exchange
- diagonal alternation
- jar-to-side ripple

The app and firmware share the same 100 registered names. The final staged verifier requires `HAPPYJARZ_PATTERN_BANK_100`.

Exact compiled flash usage must be taken from `arduino-cli compile`; do not infer it from source length.


### Seven-mode OLED screensavers

App v1.7.0 / firmware v0.17.2 provide the current seven-mode OLED saver set:

- SAYINGS
- SPIRAL
- TRIPPY
- PARTICLES
- BLOOM
- BREATHE
- GLITTER

BLOOM renders an opening/closing lotus-like procedural flower.
BREATHE uses changing radius, geometry and dither density to create a fade/breath illusion on the monochrome OLED.
GLITTER runs a persistent falling field of mixed tiny shapes with independent speed, drift and occasional flash-stars.

LEFT/RIGHT cycles modes, B exits, UP/DOWN changes speed for procedural visual modes, and A reseeds/new-universe behavior.


#### Firmware 0.17.1 compile fix

The first seven-saver staging pass exposed two compile-only integration bugs:

1. `hjVisualSpeed` was declared after `hjPrintSaverStatus()` referenced it.
2. BLOOM used a six-argument `drawArc()` call, while installed U8g2 2.36.19 provides `drawArc(x, y, radius, start, end)`.

Firmware 0.17.1 fixes both in the staging patch. The saver behavior itself is otherwise unchanged from the 0.17.0 feature pass.


#### BLOOM petal styles

Firmware 0.17.3 simplifies BLOOM into a clean flower-only saver. It cycles through 4, 6, 8 and 10-petal outline styles with a small center and slow open/close motion. Background pollen, lower bowl/leaves and other decorative elements were removed.


#### App      1.8.3 screensaver OLED preview

The OLED + PROCEDURAL SCREENSAVERS panel now includes its own live 2x view of the actual 128x64 device framebuffer. It shares the same incoming `HJ|OLED|` stream as the Mini in LIGHTS + CONTROL; there is still one serial owner and one device framebuffer source of truth.

Changing saver mode, reseeding, or changing speed can now be watched directly on the screensaver page without switching tabs.


#### App      1.8.3 lamp-driven theme

The host UI can now derive its chrome directly from the four saved/base lamp colors:

- Light 1 BASE -> app background
- Light 2 BASE -> panel surfaces
- Light 3 BASE -> outlines/borders/accent
- Light 4 BASE -> primary text

Only BASE colors drive the theme. Animated `HJ|LED_FRAME|` output is explicitly ignored, so RAINBOW, CHASE and other live effects cannot flash or continuously recolor the desktop UI.

Secondary shades such as Panel2, muted text and hover states are derived from those four base colors. Literal LED swatches and the black/blue OLED mirror remain protected from theme recoloring.


#### App      1.8.3 pattern palette theming

The host theme now follows the selected light pattern rather than the saved BASE lamp colors.

When the pattern changes, the app samples a short burst of `HJ|LED_FRAME|` telemetry, ignores near-black transition frames, chooses the strongest/distinct pattern colors, builds background/panel/outline/text roles from that palette, then freezes the theme until the next pattern change.

This preserves a calm static UI while allowing OCEAN, EMBER, NEBULA, RAINBOW and other patterns to give the host app their own visual skin.


#### App      1.8.3 / Firmware 0.17.3 live LED palette capture

Firmware now exposes the actual four-lamp pattern output over the existing USB serial link:

```text
GET LED FRAME
STREAM LED ON
STREAM LED OFF
HJ|LED_FRAME|led1=r,g,b|led2=r,g,b|led3=r,g,b|led4=r,g,b|pattern=...|brightness=...
```

The stream is observed at the central `writeFrame()` hardware output path and rate-limited to 10 Hz. Raw pattern RGB is reported before global brightness scaling so the host theme preserves hue even at low lamp brightness.

App      1.8.3 enables the stream on connect. When a pattern changes, the app samples a short burst of live frames, derives a static host palette, then freezes that theme until the next pattern change.


#### App 1.8.3 board/gamepad theme sync

Pattern-theme capture now reacts to the authoritative `pattern=` field in live `HJ|LED_FRAME|` telemetry.

That means all three pattern-change paths now trigger the same frozen host theme:

- app pattern selector
- physical board touch controls
- USB/gamepad input routed into the board

The app updates its pattern selector from the device frame, arms a short palette capture, derives the new theme, then freezes it until the next pattern change.
