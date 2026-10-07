# BloomMotionLights

Standalone motion-reactive lighting playground for the current BloomGyro bench rig.

This sketch is deliberately separate from the production HAPPY JARZ firmware. It exists to prototype what an accelerometer/gyro inside a future stand can do with the four existing APA106 lights.

## Hardware

Same bench wiring as BloomGyro:

- ESP32-S3 SuperMini
- MPU-6500-class IMU at 0x68 (current unit reports WHO_AM_I 0x70)
- SSD1306 OLED at 0x3C
- SDA GPIO8
- SCL GPIO6
- four APA106-F8 LEDs on GPIO7 through 220 ohm
- capacitive mode touch on GPIO1
- shared I2C bus at 400 kHz
- OLED/status refresh kept slow so IMU sampling stays responsive

## What the IMU is useful for

For sensory-light effects, the most useful signals are:

- gravity-derived X/Y tilt
- gyro X/Y/Z angular rate
- acceleration magnitude / impacts
- overall motion energy

These effects do **not** require absolute compass heading. The gyro's Z drift is therefore not a blocker.

For absolute yaw that returns to the same world heading after arbitrary spins, a magnetometer would be required. That is a separate use case from motion-reactive lighting.

## Current motion modes

Touch GPIO1 to cycle four modes.

### 0 — YOKE_RESPONSIVE

This is the currently preferred sensory mode.

The four bulbs behave like a simple X/Y joystick or yoke:

- idle: all four bulbs are soft blue
- move/tilt toward one side: that physical bulb crossfades toward warm gold
- diagonal movement: the two neighboring bulbs blend together
- stronger tilt: stronger color change and brightness
- no white shake flash in YOKE mode
- rough handling should still preserve direction/color instead of washing all four bulbs out

Current response tuning:

~~~text
full-scale tilt   about 45 degrees
dead zone         about 6%
tilt smoothing    fast enough to follow hand motion
response curve    ease-out for early visible feedback
~~~

The installed board axis mapping is corrected in firmware so the physical lights follow the stand's movement rather than the raw sensor-axis labels.

### 1 — Fluid Tilt

The four lights behave like a pool of colored light.

- tilt biases brightness toward that physical side
- Z rotation rolls the hue field
- motion adds energy/brightness
- motion pulse is intentionally restrained

### 2 — Comet

Tilt moves a bright colored head around the four-light ring with a soft tail.

### 3 — Aurora

All four bulbs breathe independently. Tilt changes phase; motion and rotation stir the palette faster.

## Sensory-design lessons from bench testing

The first YOKE experiments were too aggressive: small/fast movement could saturate the LEDs and make the output look white or directionless.

The useful pattern for a sensory toy is:

1. preserve a calm idle color
2. use a real center dead zone so tiny jitter does not constantly fire
3. use a broad enough detection range that normal shaking/handling does not immediately hit maximum
4. make the response visible early with a soft curve rather than a hard threshold
5. avoid white overlays that erase direction information
6. let direction be shown primarily by **which bulb changes**, not by assigning every direction a permanently different color

The current YOKE mode uses soft blue idle and a shared blue-to-gold transition for all directions.

## Accelerometer vs gyro responsibilities

Use the accelerometer for:

- steady tilt
- X/Y directional intent
- gravity-relative orientation
- impact / pickup / shake magnitude

Use the gyro for:

- rotation speed
- flicks / twists
- stirring color/effect motion
- short-term dynamic movement

Do not use integrated gyro Z as an absolute compass heading without a magnetometer.

## LED lessons

The current four APA106-F8 bulbs are enough for useful directional feedback when they are treated as four physical directions:

~~~text
            LED0
             ^
             |
     LED3 <--+--> LED1
             |
             v
            LED2
~~~

Four bulbs work well for:

- top/right/bottom/left directional feedback
- diagonal blends
- moving gradients
- fluid fields
- comet/trail effects
- motion-energy brightness

For sensory use, smooth crossfades are more readable than trying to make each bulb represent an exact angle.

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

Current identity:

~~~text
BML|IDENTITY|device=BloomMotionLights|fw=0.2.5|mode0=YOKE_RESPONSIVE
~~~

Serial runs at 115200 and emits `BML|` diagnostics.

## Design note for future stand integration

A future stand can get a lot of sensory behavior from a basic 6-axis IMU without needing a compass.

The useful design pattern is:

~~~text
accelerometer -> tilt / direction / impact
gyro          -> motion speed / twists / flicks
motion model  -> smooth response range
APA106 ring   -> directional color + brightness feedback
~~~

The bench result shows that four addressable bulbs are enough for convincing X/Y directional feedback when the response curve, dead zone, and color behavior are tuned for human handling rather than instrument-style precision.
