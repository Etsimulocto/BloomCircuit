# BloomGyro Hardware / Bench Wiring

## Current validated target

- ESP32-S3 SuperMini
- MPU-6500-class IMU breakout
- installed IMU `WHO_AM_I = 0x70`
- SSD1306 128x64 OLED
- 4 x APA106-F8 diffused addressable RGB LEDs
- one capacitive touch wire/pad for ZERO

## I2C bus

Both devices intentionally share one bus:

~~~text
ESP32-S3 GPIO8 SDA ----+---- OLED SDA
                       |
                       +---- IMU SDA

ESP32-S3 GPIO6 SCL ----+---- OLED SCL
                       |
                       +---- IMU SCL
~~~

Validated addresses:

~~~text
OLED  0x3C
IMU   0x68
~~~

The installed IMU responds with `WHO_AM_I=0x70`, identifying it as MPU-6500-class rather than a true MPU-6050.

Sharing SDA/SCL is normal I2C operation. The OLED and IMU coexist because they have different addresses.

## Validated bus timing

Current working configuration:

~~~text
I2C clock      400 kHz
OLED refresh   5 Hz
IMU target     ~200 Hz polling
gyro FS_SEL    0
gyro scale     131.0 LSB/(deg/s)
yaw ZCAL       1.0
~~~

A temporary 100 kHz diagnostic configuration made full-screen OLED traffic consume too much bus time and interfere with timely gyro sampling. Symptoms included slow yaw response and under-counted rotations.

Do not interpret that behavior as proof that the two I2C devices need separate pins.

## APA106 chain

~~~text
GPIO7
  |
  220R
  |
  v
LED0 DIN -> DOUT -> LED1 DIN -> DOUT -> LED2 DIN -> DOUT -> LED3 DIN
~~~

All four bulbs share power and ground. The project uses the existing custom APA106 RMT driver rather than generic NeoPixel timing.

## Physical light order

~~~text
            LED0
             ^
             |
     LED3 <--+--> LED1
             |
             v
            LED2
~~~

Positive Z sweeps clockwise in red.

Negative Z sweeps counter-clockwise in blue.

If the physical wiring order differs, change only the logical LED mapping rather than rewriting the sensor filter or RMT timing.

## ZERO touch

~~~text
copper / conductive touch surface
             |
             +---- GPIO1
~~~

No VCC or GND connection is needed for the capacitive pad itself.

The firmware calibrates the untouched baseline at startup and uses the touch input to redefine the current relative orientation as zero.

## Gyro / yaw behavior

The current firmware:

- measures startup gyro bias while the rig is stationary
- inverts native Z sign so clockwise is positive
- integrates Z unwrapped so 180/360-degree and multiple-turn tests remain measurable
- detects stillness from accelerometer magnitude plus gyro quietness
- slowly tracks Z zero-rate bias only while stationary
- clamps yaw rate to zero after confirmed stillness so a held angle does not continue creeping
- uses native gyro scale with `ZCAL=1.0`

The installed sensor has no magnetometer, so Z remains relative yaw rather than absolute compass heading.

## First power-up checklist

1. Verify common ground.
2. Verify OLED at `0x3C`.
3. Verify IMU at `0x68`.
4. Confirm serial reports `WHO_AM_I=0x70` on this installed board.
5. Keep the device stationary through startup gyro calibration.
6. Keep hands off the ZERO pad while its baseline is sampled.
7. Confirm serial config shows `gyro=0x00`, `fs_sel=0`, `scale=131.0`, and `i2c_khz=400`.
8. Confirm all four LEDs go green at zero.
9. Rotate clockwise: red point should sweep LED0 -> LED1 -> LED2 -> LED3.
10. Rotate counter-clockwise: blue point should sweep LED0 -> LED3 -> LED2 -> LED1.
11. Touch ZERO and confirm X/Y/Z return near zero.
12. Hold the rig still and confirm yaw no longer creeps continuously.
13. Run Simon calibration if angle accuracy needs to be checked.

## Bench result

The final bench test confirmed correct yaw behavior in all directions after restoring the bus to 400 kHz, slowing OLED refresh to 5 Hz, and returning Z to the native `1.0` scale.

The earlier "90 degrees reads about 70" behavior was traced to sampling/timing during the slower shared-bus diagnostic configuration, not to the OLED and IMU sharing SDA/SCL.


## Accelerometer / LED sensory-play notes

BloomMotionLights reuses this same IMU and four-LED hardware as a motion-reactive sensory test.

Useful IMU roles:

- X/Y gravity tilt for directional lighting
- acceleration magnitude for pickup/shake/impact
- gyro rates for twists, flicks, and motion energy
- no magnetometer required for these effects

The current four-light physical layout is sufficient for a yoke-style interaction:

~~~text
            TOP / LED0
                ^
                |
LEFT / LED3 <-- + --> RIGHT / LED1
                |
                v
           BOTTOM / LED2
~~~

Current preferred sensory behavior:

- all four idle in soft blue
- movement toward a direction crossfades that bulb toward warm gold
- diagonals blend adjacent bulbs
- full-scale response is around 45 degrees of tilt
- center dead zone is around 6%
- no white flash overlay in the main YOKE mode
- fast movement should remain colorful and directional rather than saturating to white

Bench testing showed that response tuning matters as much as sensor accuracy for sensory use. A too-wide tilt scale can feel unresponsive, while an overly sensitive motion/flash layer can wash out the directional effect.

See `firmware/BloomMotionLights/README.md` for the current motion-light behavior and tuning notes.
