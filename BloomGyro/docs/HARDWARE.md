# BloomGyro Hardware / Bench Wiring

## Current target

- ESP32-S3 SuperMini
- MPU-6050 breakout
- SSD1306 128x64 OLED
- 4 x APA106-F8 diffused addressable RGB LEDs
- one capacitive touch wire/pad for ZERO

## I2C bus

Both devices share one bus:

~~~text
ESP32-S3 GPIO8 SDA ----+---- OLED SDA
                       |
                       +---- MPU-6050 SDA

ESP32-S3 GPIO6 SCL ----+---- OLED SCL
                       |
                       +---- MPU-6050 SCL
~~~

Expected addresses: OLED 0x3C, MPU-6050 0x68.

If AD0 on the MPU-6050 is pulled high, its address becomes 0x69; firmware v0.1 is configured for 0x68.

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

Positive Z sweeps clockwise. Negative Z sweeps counter-clockwise.

If the physical wiring order differs, change only the logical LED mapping rather than rewriting the sensor filter or RMT timing.

## ZERO touch

~~~text
copper / conductive touch surface
             |
             +---- GPIO1
~~~

No VCC or GND connection is needed for the capacitive pad itself.

The firmware calibrates untouched baseline at startup, uses about +20% threshold, requires about 60 ms valid touch, and slowly tracks environmental drift while untouched.

## First power-up checklist

1. Verify common ground.
2. Verify OLED at 0x3C.
3. Verify MPU-6050 at 0x68.
4. Keep the device stationary through gyro calibration.
5. Keep hands off the ZERO pad while its baseline is sampled.
6. Confirm all four LEDs go green at zero.
7. Rotate clockwise: red point should sweep LED0 -> LED1 -> LED2 -> LED3.
8. Rotate counter-clockwise: blue point should sweep LED0 -> LED3 -> LED2 -> LED1.
9. Touch ZERO and confirm X/Y/Z return near zero.
10. Let the unit sit still and record Z drift over several minutes.

## MPU-6050 limitation

The device has no magnetic reference. Z is not north/south heading and cannot self-correct absolute yaw drift. That limitation is expected behavior for this sensor.
