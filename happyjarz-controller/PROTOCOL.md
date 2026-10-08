# HAPPY JARZ USB Serial Protocol v0.1

Transport: USB CDC serial, 115200 baud, UTF-8, one command per line.

The host must identify a Jar before treating a serial port as a HAPPY JARZ device.

## Handshake

Host:

```text
HELLO
```

Jar:

```text
HJ|IDENTITY|serial=HJ-001|hw=V1|fw=0.1
```

Any port that does not answer with `HJ|IDENTITY|` is ignored.

## Commands

```text
GET STATUS
GET TOUCH
STREAM TOUCH ON
STREAM TOUCH OFF
SET LED1 COLOR <R> <G> <B>
SET LED2 COLOR <R> <G> <B>
SET LED3 COLOR <R> <G> <B>
SET LED4 COLOR <R> <G> <B>
SET BRIGHTNESS <0-100>
SET PATTERN <registered pattern name>
TEST RGB
TEST TOUCH
SAVE
PING
```

RGB values are integers 0-255.

## Responses

Acknowledgement:

```text
HJ|ACK|command=<name>
```

Error:

```text
HJ|ERR|message=<plain text>
```

Touch sample:

```text
HJ|TOUCH|c1=4821|c2=4766|up=4902|down=4810
```

Status:

```text
HJ|STATUS|brightness=75|pattern=FADE|led1=255,0,128|led2=0,64,255|led3=128,0,255|led4=0,255,180
```

Diagnostic:

```text
HJ|TEST|rgb=PASS
HJ|TEST|touch=PASS
```

Heartbeat:

```text
HJ|PONG
```

## Rules

1. Protocol parsing belongs above the proven APA106 timing driver.
2. Malformed commands must return `HJ|ERR|...`; they must not reset or reconfigure the low-level driver.
3. `SAVE` means persist the current user configuration in ESP32 nonvolatile storage.
4. Touch streaming is diagnostic telemetry only; local touch control must continue to work without a PC attached.
5. The Jar remains a standalone product. USB control is a service/configuration path, not a runtime dependency.


## Host Mini synchronization

Introduced with app 1.4.0 / firmware 0.12.0; current host app is 1.5.0.

### Capabilities

```text
GET CAPS
```

SIMPLE currently replies:

```text
HJ|CAPS|profile=SIMPLE|controls=up,down,left,right,a,b|oled=128x64|oled_mirror=1|leds=4
```

The host app uses this capability list to keep FULL-only controls visible but disabled.

### Host logical input

```text
KEY UP
KEY DOWN
KEY LEFT
KEY RIGHT
KEY A
KEY B
```

On SIMPLE these commands enter the same logical input queue consumed by the physical copper-touch path. Unsupported FULL controls return an error rather than being guessed.

Typical host-origin event:

```text
HJ|EVENT|input=up|source=host
HJ|ACK|command=KEY
```

Future FULL firmware may advertise and accept:

```text
X Y L R START SELECT
```

only after the real FULL GPIO/profile is bench-verified.

### OLED mirror

```text
GET OLED
STREAM OLED ON
STREAM OLED OFF
```

Frame:

```text
HJ|OLED|seq=<n>|codec=b64v1|bytes=1024|data=<base64>
```

The payload is the actual 1024-byte U8g2 128x64 full framebuffer used for the physical SSD1306 display. The staged firmware wraps the existing `sendBuffer()` presentation path so menus, games, screensavers and other renderers mirror the pixels actually presented to the OLED.

Streaming is change-driven and rate-limited to at most four frames per second. This is an initial conservative USB budget and should be tuned only after hardware latency testing.

The host must use the existing serial connection. Do not open a second serial session for the OLED mirror.


### Gamepad host mapping

Gamepad support is host-side and requires no additional firmware command beyond `KEY <ACTION>`.

Current app v1.5.0 host mapping:

```text
D-pad / hat / left stick -> KEY UP/DOWN/LEFT/RIGHT
South                    -> KEY A
East                     -> KEY B
West                     -> KEY X
North                    -> KEY Y
TL                       -> KEY L
TR                       -> KEY R
START                    -> KEY START
SELECT                   -> KEY SELECT
```

The host prefers semantic `/dev/input/event*` and falls back to semantic `/dev/input/js*`. It must not consume both simultaneously for the same physical controller.

SIMPLE firmware currently accepts only the controls returned by `GET CAPS`. FULL-only actions remain a forward-compatible host surface until FULL hardware is verified.


### Topology chase patterns

Firmware v0.14.0 registers:

```text
CHASE_CW
CHASE_CCW
JAR_CHASE
SIDE_CHASE
SWEEP_LR
SWEEP_TS
DIAGONAL
PING_PONG
DUAL_CHASE
OPP_CHASE
JAR_PULSE
SIDE_ACCENT
```

These names are accepted through the existing `SET PATTERN <name>` command and are included in the local pattern cycle.


### Screensaver control

Current app 1.7.0 / firmware 0.17.1 support seven board-local saver modes:

```text
SET SAVER MODE SAYINGS
SET SAVER MODE SPIRAL
SET SAVER MODE TRIPPY
SET SAVER MODE PARTICLES
SET SAVER MODE BLOOM
SET SAVER MODE BREATHE
SET SAVER MODE GLITTER
```

Other saver commands:

```text
GET SAVER STATUS
SAVER ENTER
SAVER EXIT
SAVER NEXT
SAVER PREV
SAVER RESEED
SAVER SPEED UP
SAVER SPEED DOWN
```

For BLOOM, BREATHE and GLITTER, status includes `visual_speed=<1..8>`. The graphics remain device-rendered and are mirrored to the host through the normal `HJ|OLED|` framebuffer stream.
