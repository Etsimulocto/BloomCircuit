# BloomBoard Tester v2

Generic blank-board QA station for the common ESP32-S3 SuperMini profile.

Use it with nothing connected except USB for incoming inspection, then run it again after soldering to catch new faults.

## v2 panel

The app now presents the board as a pin panel with the common 37 exposed connections: 5V, GND, 3V3, TX, RX, and 32 exposed GPIOs.

The full sweep checks:

- ESP32-S3 startup / chip identity
- flash communication
- free heap sanity
- reset reason
- all exposed GPIOs with repeated internal pull-up / pull-down tests
- PASS / SUSPECT / FAIL status per GPIO
- JSON result logging

Click any GPIO for manual controls:

- TEST PIN
- READ
- PULL UP
- PULL DOWN
- ADC READ where supported
- TOUCH READ where supported
- DRIVE HIGH
- DRIVE LOW
- RELEASE / high impedance

## Drive safety

AUTO SWEEP does not deliberately drive GPIO outputs. Manual DRIVE HIGH / DRIVE LOW is locked until **BARE BOARD: nothing connected except USB** is checked.

DRIVE HIGH means ESP32 3.3 V logic. It never applies 5 V to a GPIO.

The firmware can command an output HIGH or LOW, but it cannot independently prove the voltage present at the physical pad. Actual pad-voltage verification is a future pogo-pin / external-measurement fixture job.

## Power panel

5V, 3V3 and GND are displayed separately. Exact rail voltage cannot be independently measured by the unmodified ESP32 itself, so the app includes manual meter fields for 5V and 3V3 plus a FLIR no-hotspot record.

## Install

```bash
cd ~/BloomCircuit/BloomBoardTester
./install.sh
```

## Run

```bash
cd ~/BloomCircuit/BloomBoardTester
./run.sh
```

`run.sh` launches `board_tester_v2.py`, which compiles and flashes `firmware_v2/firmware_v2.ino` when **FLASH + TEST ENTIRE BOARD** is pressed.

Results are saved under `results/`.

## Important limitation

Firmware-only diagnostics cannot prove every internal circuit or every possible solder bridge is healthy. FLIR, DMM/diode-mode comparison, and eventually the external pogo fixture remain independent test layers.
