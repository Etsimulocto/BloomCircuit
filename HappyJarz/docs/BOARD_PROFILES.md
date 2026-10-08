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

FULL may add actions such as X/Y, shoulder buttons, START, SELECT, MENU or HOME, but names and mappings remain provisional until the real board is tested.

Host keyboards, gamepads and physical touch pads should all map into the same logical action layer.
