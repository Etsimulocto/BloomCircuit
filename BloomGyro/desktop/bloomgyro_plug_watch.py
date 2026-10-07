#!/usr/bin/env python3
"""Auto-launch BloomGyro Mini when BloomGyro hardware is plugged in."""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports

BAUD = 115200
SCAN_SECONDS = 0.25
STABLE_SECONDS = 1.2
IDENTIFY_TIMEOUT = 1.5

HERE = Path(__file__).resolve().parent
APP = HERE / "bloomgyro_mini.py"


def programmer_running() -> bool:
    try:
        p = subprocess.run(
            ["pgrep", "-f", "arduino-cli|esptool"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return p.returncode == 0
    except Exception:
        return False


def esp_ports() -> list[str]:
    found = []
    for p in list_ports.comports():
        if not p.device.startswith("/dev/ttyACM"):
            continue
        desc = f"{p.description or ''} {p.manufacturer or ''}".lower()
        if p.vid == 0x303A or "espressif" in desc or "usb jtag" in desc or "esp32" in desc:
            found.append(p.device)
    return sorted(found)


def stable_path_for(port: str) -> str:
    real = os.path.realpath(port)
    for link in sorted(glob.glob("/dev/serial/by-id/*")):
        try:
            if os.path.realpath(link) == real:
                return link
        except OSError:
            pass
    return port


def open_no_reset(port: str) -> serial.Serial:
    s = serial.Serial()
    s.port = port
    s.baudrate = BAUD
    s.timeout = 0.20
    s.write_timeout = 0.20
    s.dtr = False
    s.rts = False
    s.open()
    s.dtr = False
    s.rts = False
    return s


def identify_bloomgyro(port: str) -> bool:
    """Ask the firmware who it is without deliberately toggling DTR/RTS."""
    try:
        s = open_no_reset(port)
    except Exception:
        return False

    try:
        try:
            s.reset_input_buffer()
        except Exception:
            pass
        s.write(b"HELLO\n")
        s.flush()

        deadline = time.monotonic() + IDENTIFY_TIMEOUT
        while time.monotonic() < deadline:
            raw = s.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("BG|IDENTITY|") and "device=BloomGyro" in line:
                return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass
    return False


def launch(port: str) -> subprocess.Popen:
    assigned = stable_path_for(port)
    env = os.environ.copy()
    env["BLOOMGYRO_PORT"] = assigned
    return subprocess.Popen(
        [sys.executable, str(APP)],
        cwd=str(HERE),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    proc: subprocess.Popen | None = None
    first_seen: dict[str, float] = {}
    launched_realpath: str | None = None

    while True:
        now = time.monotonic()
        ports = esp_ports()
        current_realpaths = {os.path.realpath(p) for p in ports}

        for p in list(first_seen):
            if p not in ports:
                first_seen.pop(p, None)
        for p in ports:
            first_seen.setdefault(p, now)

        if proc is not None and proc.poll() is not None:
            proc = None
            launched_realpath = None

        # Do not probe while flashing/programming.
        if proc is None and not programmer_running():
            for port in ports:
                if now - first_seen.get(port, now) < STABLE_SECONDS:
                    continue
                real = os.path.realpath(port)
                if launched_realpath == real:
                    continue
                if identify_bloomgyro(port):
                    proc = launch(port)
                    launched_realpath = real
                    break

        # Re-arm after a genuine disconnect.
        if launched_realpath is not None and launched_realpath not in current_realpaths:
            if proc is None or proc.poll() is not None:
                launched_realpath = None

        time.sleep(SCAN_SECONDS)


if __name__ == "__main__":
    main()
