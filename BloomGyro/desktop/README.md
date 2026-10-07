# BloomGyro Mini

Small Raspberry Pi desktop monitor/controller for BloomGyro.

## What it does

- auto-connects to the ESP32-S3 over USB CDC
- uses the proven BloomPetz no-reset serial-open pattern (DTR/RTS forced low)
- shows live X, Y, Z angles
- shows Z angular rate and raw GPIO1 touch reading
- shows OLED / IMU / LED health
- provides a **ZERO / RESET** button that sends `ZERO` to firmware
- reconnects if Linux re-enumerates the same ESP32 as a different `/dev/ttyACM*`
- writes a CSV session log with angles, zero events, boot/calibration/error records, port events, touch values, and hardware status

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

## Logs

Default directory:

```text
~/.local/share/bloomgyro/logs/
```

Each launch creates a file like:

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

`ZERO` and `RESET` both redefine the current X/Y/Z orientation as zero. They do not reboot the ESP32.

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

- plugging in a controller running **BloomGyro** opens BloomGyro Mini automatically
- the watcher identifies the firmware by its `BG|IDENTITY|device=BloomGyro` response, so other Espressif boards are not intentionally claimed
- unplugging that BloomGyro closes the Mini automatically after a short disconnect grace
- brief ESP32-S3 USB re-enumeration is tolerated
- the watcher starts automatically at Raspberry Pi desktop login

Watcher log:

```text
~/.local/share/bloomgyro/plug_watch.log
```
