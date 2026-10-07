# BloomGyro Firmware

## Current firmware

`BloomGyro.ino` — current bench line 0.1.1 — `bloomcore/v1.3`

Current validated yaw configuration:

~~~text
IMU WHO_AM_I  0x70
I2C           400 kHz
OLED refresh  5 Hz
gyro FS_SEL   0
gyro scale    131.0 LSB/(deg/s)
ZCAL          1.0
~~~

## External libraries

None beyond the ESP32 Arduino core.

Used core headers:

- `Arduino.h`
- `Wire.h`
- `math.h`
- `esp32-hal-rmt.h`

The SSD1306 text path and MPU-compatible register path are implemented locally so the bench build does not depend on an additional Arduino sensor/display library.

## IMU identity

The installed device reports:

~~~text
WHO_AM_I = 0x70
~~~

That is treated as an MPU-6500-class IMU. The firmware also accepts the compatible `0x68` / `0x69` identities used by MPU-6050-class parts.

The basic accel/gyro register path is shared across these compatible devices, but documentation should not call the installed `0x70` unit a true MPU-6050.

## Board target

~~~text
esp32:esp32:esp32s3:CDCOnBoot=cdc
~~~

## Compile / flash

From the repository root:

~~~bash
cd ~/BloomCircuit/BloomGyro
bash flash.sh --compile-only
ls /dev/ttyACM*
bash flash.sh /dev/ttyACM0
~~~

Use the port that actually exists after compile / bootloader re-enumeration.

Direct compile:

~~~bash
arduino-cli compile   --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc   BloomGyro/firmware/BloomGyro
~~~

Do not upload a stale binary after a failed compile.

## Firmware layers

~~~text
shared 400 kHz I2C
        |
        +--> MPU raw sample (~200 Hz target)
        |       |
        |       v
        |   startup bias + stationary bias tracker
        |       |
        |       +--> X/Y complementary filter
        |       |
        |       +--> unwrapped relative Z integration
        |
        +--> SSD1306 OLED (5 Hz refresh)

relative Z
   |
   v
four-LED spatial ring
   |
   v
proven APA106 RMT driver

GPIO1 capacitive touch
   |
   v
ZERO reference capture
~~~

## Why OLED refresh is 5 Hz

OLED and IMU intentionally share SDA/SCL.

A 100 kHz diagnostic run made full OLED redraw traffic slow enough to interfere with timely IMU sampling. The symptom was slow yaw response and severe under-counting during turns.

The validated fix is:

- restore I2C to 400 kHz
- refresh OLED at 5 Hz
- keep IMU polling much faster
- preserve elapsed-time integration across occasional longer loop intervals

This is a timing issue, not an address conflict.

## Yaw scale history

Temporary empirical Z multipliers were tested while yaw appeared to under-count rotation.

Those multipliers were removed after the bus/display timing issue was isolated. With correct sampling, the sensor's native scale is the validated setting:

~~~text
GYRO_Z_CAL = 1.000000
~~~

Do not reintroduce `1.24` or `1.285714` merely because a single hand-turned calibration point looks low. First verify sampling timing and firmware identity.

## Stationary hold / drift control

BloomGyro measures startup gyro bias while still.

During normal operation it detects stillness using acceleration magnitude plus gyro quietness. After confirmed stillness:

- Z bias is adjusted slowly
- yaw rate is clamped to zero
- a held heading stops creeping
- bias learning freezes as soon as motion resumes

This reduces zero-rate drift without pretending the gyro has an absolute heading reference.

## Diagnostic records

The firmware emits structured records including:

~~~text
BG|IDENTITY|device=BloomGyro|fw=...|build=...|z_cal=...
BG|IMU|whoami=0x70
BG|IMUCFG|pwr1=...|smpl=...|cfg=...|gyro=...|accel=...|fs_sel=...|scale=...|i2c_khz=400|z_cal=...
BG|STATUS|...|still=...|bz=...
BG|ANGLES|...|still=...|bz=...
~~~

Expected gyro configuration for the validated bench setup:

~~~text
gyro=0x00
fs_sel=0
scale=131.0
~~~

## Diagnostic order

1. confirm the visible / serial firmware build identity
2. confirm `oled=1`, `mpu=1`, `led=1`
3. confirm `WHO_AM_I=0x70` on this installed board
4. confirm `gyro=0x00`, `fs_sel=0`, `scale=131.0`
5. confirm `i2c_khz=400`
6. inspect `BG|ANGLES`
7. test ZERO
8. check that a held angle stops creeping
9. run Simon calibration
10. only then consider filter/scale changes

Do not change multiple layers at once.


## Motion-light reuse

The validated IMU layer is also reused by `BloomMotionLights`, a standalone sensory-light playground.

Key lesson: accelerometer/gyro data is often more useful as an **interaction signal** than as an instrument reading.

For motion-reactive LEDs:

- X/Y tilt comes from gravity-relative accelerometer data
- gyro rates provide motion speed and twists
- acceleration magnitude provides shake/impact energy
- absolute Z heading is unnecessary

The current YOKE sensory mode maps X/Y motion onto the four physical APA106 bulbs with:

- soft blue idle
- blue-to-gold directional crossfade
- about 45-degree full-scale tilt
- about 6% center dead zone
- early-response easing
- no white flash overlay in YOKE mode

This keeps the output useful during energetic handling instead of saturating all four LEDs.
