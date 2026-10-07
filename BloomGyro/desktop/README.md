# BloomGyro Mini

Small Raspberry Pi desktop monitor/controller for BloomGyro.

## What it does

- auto-connects to the ESP32-S3 over USB CDC
- uses the proven no-reset serial-open pattern with DTR/RTS forced low
- shows live X, Y, Z angles
- shows Z angular rate and raw GPIO1 touch reading
- shows stationary-state and Z-bias diagnostics
- shows OLED / IMU / LED health
- provides a **ZERO / RESET** button that sends `ZERO`
- reconnects if Linux re-enumerates the same ESP32 as a different `/dev/ttyACM*`
- writes a CSV session log with angles, zero events, boot/calibration/error records, port events, touch values, hardware status, still-state, and Z-bias data

## Run

From the repository:

```bash
cd ~/BloomCircuit/BloomGyro
python3 desktop/bloomgyro_mini.py
```

Dependency:

```bash
sudo apt install -y python3-serial python3-tk
```

If the plug watcher is installed, plugging in BloomGyro may open the Mini automatically; do not launch a second copy unnecessarily.

## Logs

Default directory:

```text
~/.local/share/bloomgyro/logs/
```

Each launch creates a session CSV such as:

```text
bloomgyro_20261007_143100.csv
```

Override the directory with:

```bash
BLOOMGYRO_LOG_DIR=~/BloomGyroLogs python3 desktop/bloomgyro_mini.py
```

## Serial commands

The firmware accepts:

```text
HELLO
GET STATUS
STATUS
ZERO
RESET
ZERO RESET
```

`ZERO` and `RESET` both redefine the current X/Y/Z orientation as zero. They do **not** reboot the ESP32.

To force one port:

```bash
BLOOMGYRO_PORT=/dev/ttyACM0 python3 desktop/bloomgyro_mini.py
```

Normally this is unnecessary; the app prefers an Espressif `/dev/serial/by-id/` path when available.

## Automatic plug / unplug behavior

Install the desktop watcher once:

```bash
cd ~/BloomCircuit/BloomGyro/desktop
bash install_bloomgyro_autostart.sh
```

After installation:

- plugging in firmware that identifies as **BloomGyro** opens BloomGyro Mini automatically
- other Espressif boards are not intentionally claimed
- unplugging BloomGyro closes the Mini after a short disconnect grace
- brief ESP32-S3 USB re-enumeration is tolerated
- the watcher starts automatically at Raspberry Pi desktop login

Watcher log:

```text
~/.local/share/bloomgyro/plug_watch.log
```

## Simon calibration logger

BloomGyro Mini includes a **SIMON CAL** button for guided hardware calibration.

The current sequence is intentionally physical and simple: every yaw motion is another 45-degree turn from the last position.

Clockwise sweep:

```text
ZERO
+45
+45
+45
+45
+45
+45
+45
+45  -> one full turn
```

Then return to the physical start mark, set a fresh zero, and repeat the same eight 45-degree steps counterclockwise.

The final section repeats the tilt checks:

- front edge up about 45°
- back edge up about 45°
- right edge up about 45°
- left edge up about 45°

Each capture averages the most recent live samples rather than using one instantaneous reading.

The calibration session produces:

```text
~/.local/share/bloomgyro/logs/bloomgyro_cal_YYYYMMDD_HHMMSS.csv
~/.local/share/bloomgyro/logs/bloomgyro_cal_YYYYMMDD_HHMMSS.txt
```

The CSV records target angle, averaged X/Y/Z, Z rate, touch value, sample count, min/max values, yaw error, and measured/target ratio.

The TXT is a compact human-readable report.

Print the newest report in the terminal with:

```bash
cat "$(ls -t ~/.local/share/bloomgyro/logs/bloomgyro_cal_*.txt | head -n1)"
```

## Current validated result

The final bench run established that yaw behaves correctly in both directions after:

- returning shared I2C to 400 kHz
- reducing OLED refresh to 5 Hz
- keeping fast IMU sampling
- using native yaw scale `ZCAL=1.0`
- retaining stationary bias / hold-lock behavior

Earlier 100 kHz testing caused OLED traffic to starve IMU sampling, which made 90-degree turns read low and made response feel slow. That was a timing problem, not an I2C-address conflict.

If calibration suddenly regresses, verify the running firmware build and serial `BG|IMUCFG|` line before changing scale constants.
