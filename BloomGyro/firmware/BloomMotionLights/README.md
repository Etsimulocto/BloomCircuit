# BloomMotionLights

Standalone motion-reactive lighting playground for the current BloomGyro bench rig.

This sketch is deliberately separate from the production HAPPY JARZ firmware. It exists to prototype what an IMU inside a future stand could do with the four existing APA106 lights.

## Hardware

Same wiring as BloomGyro:

- ESP32-S3 SuperMini
- MPU-6500-class IMU at 0x68 (current unit reports WHO_AM_I 0x70)
- SSD1306 OLED at 0x3C
- SDA GPIO8
- SCL GPIO6
- four APA106-F8 LEDs on GPIO7 through 220 ohm
- capacitive mode touch on GPIO1
- shared I2C bus at 400 kHz
- OLED/status refresh kept slow so IMU sampling stays responsive

## Motion modes

Touch GPIO1 to cycle three modes.

### 0 — Fluid Tilt

The four lights behave like a pool of colored light.

- tilt biases brightness toward that physical side
- Z rotation rolls the hue field
- motion adds energy/brightness
- a shake overlays a brief warm flash

### 1 — Comet

Tilt moves a bright colored head around the four-light ring with a soft tail.

### 2 — Aurora

All four bulbs breathe independently. Tilt changes phase; motion and rotation stir the palette faster.

## Why this does not need a magnetometer

These effects use gravity tilt, angular velocity, acceleration magnitude, and motion energy. They do not require absolute compass heading, so Z drift is not a problem.

## Compile

From the repository root:

```bash
arduino-cli compile \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc \
  BloomGyro/firmware/BloomMotionLights
```

## Upload

```bash
PORT=$(ls /dev/ttyACM* 2>/dev/null | head -n1)

arduino-cli upload \
  -p "$PORT" \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,UploadSpeed=115200 \
  BloomGyro/firmware/BloomMotionLights
```

Serial runs at 115200 and emits `BML|` diagnostics.

## Design note for future stand integration

The useful sensor signals are:

- gravity-derived X/Y tilt
- gyro X/Y/Z rates
- acceleration magnitude / impact
- combined motion energy

Those can drive light effects without using yaw as a precise orientation instrument.
