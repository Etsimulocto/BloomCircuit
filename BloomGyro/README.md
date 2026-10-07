# BloomGyro

BloomGyro is a standalone ESP32-S3 motion visualizer built from proven BloomCircuit hardware/code layers.

It is **not a HAPPY JARZ application**. It reuses the known-good BloomCircuit techniques for the ESP32-S3, SSD1306 OLED, capacitive touch, and APA106 timing.

## Current validated hardware

- ESP32-S3 SuperMini
- SSD1306 128x64 OLED at I2C `0x3C`
- MPU-6500-class accelerometer/gyro at I2C `0x68`
- installed IMU `WHO_AM_I = 0x70`
- 4 x APA106-F8 addressable RGB LEDs
- capacitive ZERO input on GPIO1

The breakout was initially treated as MPU-6050-compatible because the basic accel/gyro register map is compatible, but the live device identifies as `0x70`, so BloomGyro documentation now treats it as an MPU-6500-class device.

## What it does

- shows live relative X, Y, and Z orientation in degrees
- uses four APA106-F8 RGB LEDs as a spatial rotation indicator
- uses **GREEN = zero**, **RED = positive**, **BLUE = negative**
- sets the current orientation as zero from the GPIO1 capacitive touch input or desktop Mini app
- streams structured `BG|` serial diagnostics at 115200 baud
- supports guided Simon calibration and CSV/TXT logging from the Raspberry Pi Mini app

## Four-light layout

~~~text
            LED0
             ^
             |
     LED3 <--+--> LED1
             |
             v
            LED2
~~~

At zero, all four lights are green.

Positive Z moves a red point clockwise around the ring. Negative Z moves a blue point counter-clockwise. Adjacent LEDs are brightness-interpolated so the point sweeps instead of jumping.

## Hardware map

| Function | Connection |
|---|---|
| ESP32-S3 | SuperMini |
| OLED | SSD1306 128x64, I2C 0x3C |
| IMU | MPU-6500-class, I2C 0x68, WHO_AM_I 0x70 |
| SDA | GPIO8 |
| SCL | GPIO6 |
| APA106 data | GPIO7 through 220 ohm resistor |
| ZERO capacitive touch | GPIO1 |
| APA106 count | 4 |

The OLED and IMU intentionally share SDA/SCL. This is normal I2C operation because each device has a different address.

## Validated bus / timing configuration

The working bench configuration is:

~~~text
I2C bus       400 kHz
IMU sampling  target 200 Hz
OLED refresh  5 Hz
Z scale       native MPU scale, ZCAL = 1.0
~~~

A diagnostic experiment at 100 kHz made OLED traffic consume enough bus time to interfere with timely IMU sampling. That caused yaw to respond slowly and under-count rotation. Restoring the bus to 400 kHz and reducing OLED refresh to 5 Hz fixed the sampling problem.

Do not reduce the shared bus to 100 kHz without also reconsidering OLED traffic and IMU timing.

## Orientation behavior

X and Y use a complementary filter: gyro motion is blended with the gravity vector from the accelerometer.

Z/yaw is integrated from the gyro. The installed IMU's native Z sign is inverted in firmware so the BloomGyro convention remains:

~~~text
clockwise        positive / red
counterclockwise negative / blue
~~~

The final validated yaw scale uses the sensor's native scale (`ZCAL=1.0`). Earlier empirical multipliers such as `1.24` and `1.285714` were removed after the real timing problem was found.

## Stationary bias handling

Startup performs a gyro bias calibration while the rig is still.

During operation BloomGyro also detects confirmed stillness. While stationary it can slowly track Z zero-rate bias; once stillness is confirmed, residual yaw rate is clamped to zero so a held angle does not continue creeping indefinitely.

Bias learning freezes immediately when motion is detected.

## Important yaw limitation

This IMU has no magnetometer. Z is therefore **relative yaw**, not compass heading. It cannot know north or restore an absolute world heading on its own.

ZERO is deliberately part of the design.

## Build / flash

Firmware:

~~~text
BloomGyro/firmware/BloomGyro/BloomGyro.ino
~~~

Recommended helper:

~~~bash
cd ~/BloomCircuit/BloomGyro
bash flash.sh --compile-only
ls /dev/ttyACM*
bash flash.sh /dev/ttyACM0
~~~

Use the actual ACM port shown on the Pi.

Direct Arduino CLI compile:

~~~bash
arduino-cli compile   --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc   BloomGyro/firmware/BloomGyro
~~~

The ESP32-S3 can re-enumerate between `/dev/ttyACM0` and `/dev/ttyACM1`; that does not mean there are two boards.

## Startup

1. Keep the rig still at power-up.
2. BloomGyro probes OLED and IMU.
3. IMU identity/configuration is reported over serial.
4. Startup gyro bias is measured.
5. capacitive touch baseline is measured hands-off.
6. current orientation is set as zero.
7. live display, serial telemetry, and light ring begin.

## ZERO control

Touch the GPIO1 conductive pad/wire or press **ZERO / RESET** in BloomGyro Mini.

That redefines the current orientation as approximately X=0, Y=0, Z=0. It does **not** reboot the ESP32.

## Serial diagnostics

USB CDC serial runs at 115200 baud.

Useful records include:

~~~text
BG|IDENTITY|device=BloomGyro|fw=...|build=...|z_cal=...
BG|BOOT|oled=1|mpu=1|led=1
BG|IMU|whoami=0x70
BG|IMUCFG|...|gyro=0x00|fs_sel=0|scale=131.0|i2c_khz=400|z_cal=1.000000
BG|CAL|...
BG|ZERO|...
BG|ANGLES|x=...|y=...|z=...|gz_dps=...|still=...|bz=...
BG|STATUS|...
BG|ERROR|...
~~~

For the validated configuration, `gyro=0x00`, `fs_sel=0`, and `scale=131.0` indicate the ±250 dps gyro range.

## Bench validation result

The final bench check confirmed that clockwise/counterclockwise rotations and the main tested angles track correctly in all directions after the 400 kHz / 5 Hz timing fix and return to native Z scale.

If yaw accuracy regresses, verify firmware build identity, IMU config readback, bus speed, OLED refresh rate, and actual ACM port before changing scale constants.

## BloomCore maintenance rule

Preserve known-good lower layers. In particular:

- do not replace the APA106 RMT timing while debugging orientation
- do not alter yaw scale before checking sample timing
- do not assume a 0x70 device is an MPU-6050
- change one diagnostic layer at a time


## Accelerometer-driven sensory lighting

The same validated IMU stack now powers `BloomMotionLights`, a separate motion-reactive LED test.

The important takeaway is that a basic accelerometer/gyro is already enough for strong sensory interaction:

- tilt can select a physical direction
- motion speed can drive brightness/energy
- shake and impacts can trigger effects
- diagonal movement can blend neighboring bulbs
- four APA106 lights are enough for a useful top/right/bottom/left field

The current preferred YOKE behavior uses all four bulbs as a directional field: idle is soft blue, and movement toward a side crossfades that side toward warm gold. The response starts early, reaches full strength around 45 degrees, and avoids white saturation during rough handling.

Absolute yaw is not needed for this use; a magnetometer is only necessary if the product must recover a true world-relative heading after arbitrary spins.

See `firmware/BloomMotionLights/README.md` for the sensory-light tuning notes.
