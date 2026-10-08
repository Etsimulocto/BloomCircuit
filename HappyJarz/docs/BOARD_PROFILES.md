# HAPPY JARZ Board Profiles

## Rule

Applications and games should target **logical actions and capabilities**, not raw GPIO numbers.

Raw GPIO belongs in a board profile.

## SIMPLE profile

Status: current/proven integrated hardware family.

Controller:
- ESP32-S3 Mini class
- 4 MB flash target

Current proven inputs:
- UP
- DOWN
- LEFT
- RIGHT
- A
- B

Current proven integrated pin map:
- GPIO4 = UP
- GPIO5 = DOWN
- GPIO9 = LEFT
- GPIO10 = RIGHT
- GPIO1 = A
- GPIO2 = B
- GPIO7 = APA106 data
- GPIO8 = OLED SDA
- GPIO6 = OLED SCL
- GPIO3 = battery/supply ADC path

Lighting:
- four APA106 lamps
- one daisy-chain
- GPIO7 -> 220 ohm -> DIN1 -> DIN2 -> DIN3 -> DIN4
- proven RGB byte order
- proven custom ESP32 HAL RMT transport

Do not casually replace the proven low-level APA106 transport.

## FULL profile

Status: planned, hardware not yet bench-verified.

Expected controller class:
- full-size ESP32-S3
- approximately 16 MB flash
- approximately 8 MB PSRAM

Expected differences:
- more physical touch/button inputs
- larger native content budget
- additional board-local games/screensavers/features

Do not freeze the FULL GPIO map until the actual board is in hand.

## Logical input layer

Current common actions:

```text
ACTION_UP
ACTION_DOWN
ACTION_LEFT
ACTION_RIGHT
ACTION_A
ACTION_B
```

FULL target logical controls:

```text
UP
DOWN
LEFT
RIGHT
A
B
X
Y
L
R
START
SELECT
```

That is 12 gamepad-style actions total.

The FULL board should not be forced to reuse the SIMPLE raw GPIO map. Because the full-size ESP32-S3 exposes many more GPIOs, peripheral functions such as OLED I2C, APA106 data and battery ADC can be moved away from touch-capable pins as needed so the board can reserve enough native touch channels for the full gamepad layout.

Exact FULL GPIO assignments remain provisional until the actual production board is received and bench-tested.

Keep spare touch capacity where practical for future controls or touch-shield/noise handling.

Host keyboards, gamepads, physical touch pads and on-screen app controls should all map into the same logical action layer.


## Lamp physical topology

Current four-lamp stand geometry:

```text
      TOP / JARS

   [1]       [2]
 top-left   top-right

   [3]       [4]
 side-left  side-right
```

Functional groups:
- Jar pair: 1 + 2
- Side accent pair: 3 + 4
- Left column: 1 + 3
- Right column: 2 + 4

Canonical clockwise path:

```text
1 -> 2 -> 4 -> 3 -> 1
```

Pattern code should use physical topology names rather than assuming APA106 DIN order alone.
