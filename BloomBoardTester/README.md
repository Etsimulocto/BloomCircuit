# BloomBoard Tester

Generic blank-board QA station for ESP32-S3 SuperMini boards.

Use on a board with nothing attached except USB. Intended for incoming inspection and again after soldering.

## What it tests

- chip identification / CPU startup
- flash communication
- heap sanity
- reset reason
- exposed GPIO pull-up / pull-down behavior
- repeated GPIO response to catch inconsistent/stuck pins
- touch-capable channel sampling
- manual FLIR thermal check record
- JSON result logging

## Important limitation

No firmware-only test can prove that every internal circuit and every possible short is healthy. A GPIO test can detect many stuck/bridged conditions, but an ohmmeter/diode-mode comparison and FLIR remain useful independent checks.

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

Plug in one naked ESP32-S3 SuperMini, choose `/dev/ttyACM*`, and press **TEST BOARD**.

Results are saved under `results/`.
