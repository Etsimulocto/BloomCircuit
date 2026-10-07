# BloomGyro Firmware

## Current firmware

BloomGyro.ino — version 0.1.0 — bloomcore/v1.3

## External libraries

None beyond the ESP32 Arduino core.

Used core headers:

- Arduino.h
- Wire.h
- math.h
- esp32-hal-rmt.h

The SSD1306 text path and MPU-6050 register path are implemented locally so this first bench build does not depend on an additional Arduino library being installed.

## Board target

~~~text
esp32:esp32:esp32s3:CDCOnBoot=cdc
~~~

## Compile

From the repository root:

~~~bash
arduino-cli compile \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc \
  BloomGyro/firmware/BloomGyro
~~~

Do not upload a stale binary after a failed compile.

## Upload

~~~bash
PORT=$(ls /dev/ttyACM* 2>/dev/null | head -n1)

arduino-cli upload \
  -p "$PORT" \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,UploadSpeed=115200 \
  BloomGyro/firmware/BloomGyro
~~~

## Firmware layers

~~~text
I2C / MPU raw sample
        |
        v
gyro bias + complementary orientation
        |
        +------------------+
        |                  |
        v                  v
OLED X/Y/Z          relative Z ring mapping
                           |
                           v
                  proven APA106 RMT driver

GPIO1 capacitive touch
        |
        v
ZERO reference capture
~~~

## Diagnostic order

1. confirm boot identity;
2. confirm oled=1, mpu=1, led=1;
3. inspect physical wiring/I2C addresses;
4. inspect BG|ANGLES;
5. test ZERO;
6. inspect LED spatial mapping;
7. only then adjust filtering.

Do not change multiple layers at once.
