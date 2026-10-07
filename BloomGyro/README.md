# BloomGyro

BloomGyro is a standalone ESP32-S3 motion visualizer built from the proven BloomCircuit hardware/code layers.

It is **not a HAPPY JARZ application**. It reuses the known-good BloomCircuit techniques for the ESP32-S3, SSD1306 OLED, capacitive touch, and APA106 timing.

## What it does

- Reads an **MPU-6050** accelerometer + gyroscope.
- Shows live relative orientation on the OLED: X, Y, and Z in degrees.
- Uses **four APA106-F8 RGB LEDs** as a spatial rotation indicator.
- Uses the color language **GREEN = zero**, **RED = positive**, **BLUE = negative**.
- A capacitive touch wire on GPIO1 sets the current physical orientation as the new zero.

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

As Z rotates positive, a red point moves clockwise around the four LEDs. As Z rotates negative, a blue point moves counter-clockwise. Brightness is interpolated between adjacent LEDs so the point sweeps instead of jumping.

## Hardware map

| Function | Connection |
|---|---|
| ESP32-S3 | SuperMini |
| OLED | SSD1306 128x64, I2C 0x3C |
| MPU-6050 | I2C 0x68 |
| SDA | GPIO8 |
| SCL | GPIO6 |
| APA106 data | GPIO7 through 220 ohm resistor |
| ZERO capacitive touch | GPIO1 |
| APA106 count | 4 |

The OLED and MPU-6050 share the same I2C bus because they have different addresses.

## Orientation behavior

X and Y use a complementary filter: gyro motion is blended with the gravity vector from the accelerometer.

Z/yaw is integrated from the gyro.

**Important:** the MPU-6050 has no magnetometer, so Z is a relative rotation measurement and will slowly drift. The ZERO touch control is deliberately part of the design so the operator can instantly establish a fresh reference.

## Build

Firmware:

~~~text
BloomGyro/firmware/BloomGyro/BloomGyro.ino
~~~

Compile with the same ESP32-S3 board target used elsewhere in BloomCircuit:

~~~bash
arduino-cli compile \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc \
  BloomGyro/firmware/BloomGyro
~~~

Upload:

~~~bash
PORT=$(ls /dev/ttyACM* 2>/dev/null | head -n1)

arduino-cli upload \
  -p "$PORT" \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,UploadSpeed=115200 \
  BloomGyro/firmware/BloomGyro
~~~

No MPU-6050 or OLED Arduino library is required. The firmware talks directly to both devices over Wire. The APA106 layer retains the custom ESP32-S3 RMT timing already proven in BloomCircuit.

## Startup

1. Power the board while it is sitting still.
2. BloomGyro verifies the I2C devices.
3. The gyro bias is sampled while the board remains still.
4. Capacitive ZERO is calibrated hands-off.
5. The current orientation is automatically set to zero.
6. The OLED begins showing X/Y/Z and the four-light ring becomes active.

## ZERO control

Touch the GPIO1 copper/touch wire.

The current orientation becomes approximately X=0, Y=0, Z=0. All four LEDs flash green to confirm the new reference.

## Serial diagnostics

USB CDC serial runs at 115200 baud.

Useful records include:

~~~text
BG|IDENTITY|...
BG|BOOT|oled=1|mpu=1|led=1
BG|CAL|...
BG|ZERO|...
BG|ANGLES|x=...|y=...|z=...|gz_dps=...
BG|ERROR|...
~~~

## BloomCore maintenance rule

Preserve known-good lower layers. In particular, do not replace the APA106 RMT timing while diagnosing MPU filtering, OLED layout, or touch behavior. Diagnose one layer at a time.
