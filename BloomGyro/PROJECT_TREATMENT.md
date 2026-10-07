# BloomGyro — Project Treatment

## Purpose

BloomGyro is a small physical instrument that makes rotation visible in two ways at once:

1. exact X/Y/Z relative angles on a 128x64 OLED;
2. an immediate four-point color display that can be read without looking closely at numbers.

The instrument should feel physical and obvious rather than like a generic sensor demo.

## Interaction language

The color grammar is fixed:

- **green = zero**
- **red = positive**
- **blue = negative**

The four LEDs form a spatial ring around the device.

At the reference orientation all four LEDs are green.

When the device rotates around Z, the active point travels around the four lights. Positive motion occupies the red family; negative motion occupies the blue family. The renderer blends neighboring LEDs so the indication moves smoothly through intermediate angles.

## Display

~~~text
BLOOM GYRO

X +012.3 DEG
Y -004.7 DEG
Z +138.2 DEG
~~~

The readout is relative to the most recent ZERO operation.

## ZERO

GPIO1 is used as one capacitive touch surface.

A valid touch captures current X/Y/Z as the new reference, makes the displayed values approximately zero, flashes all four LEDs green, and logs the event over USB serial.

ZERO is a first-class feature, not a workaround. The MPU-6050 contains no magnetometer, so integrated Z/yaw is inherently relative and slowly drifts.

## Sensor model

MPU-6050 provides a 3-axis accelerometer and 3-axis gyroscope at I2C address 0x68 in the current wiring.

X and Y combine accelerometer gravity information with integrated gyro motion using a complementary filter. Z integrates gyro Z rate and is intentionally presented as relative rotation from ZERO rather than compass heading.

## Proven code reused

BloomGyro preserves the proven ESP32-S3 APA106 output layer:

- GPIO7
- 220 ohm series data resistor
- RMT clock 10 MHz
- bit 0: 4 ticks HIGH / 14 ticks LOW
- bit 1: 14 ticks HIGH / 4 ticks LOW
- 100 us latch

The old two-light count is expanded to **four LEDs** without changing the low-level timing.

## BloomCore boundaries

- If serial angles change but OLED does not: inspect OLED/I2C rendering.
- If angles are correct but lights are wrong: inspect the four-light mapping/render layer.
- If X/Y are unstable: inspect mounting, accel/gyro calibration and filtering.
- If Z slowly walks while stationary: re-zero and measure drift; do not mistake yaw drift for an LED-driver failure.
- If touch does not zero: inspect touch raw/baseline/threshold before changing orientation math.
- If LEDs fail entirely: run the known-good APA106 layer before touching sensor code.

The goal is an understandable, serviceable instrument whose lower layers remain independently testable.
