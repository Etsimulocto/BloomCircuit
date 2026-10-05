#!/usr/bin/env python3
"""Launch BloomPetz Mini when the ESP32-S3 appears; re-arm on real unplug."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from serial.tools import list_ports

SCAN_SECONDS = 0.20
STABLE_SECONDS = 2.0
HERE = Path(__file__).resolve().parent
APP = HERE / "bloompetz_mini.py"


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


def port_generation(name: str):
    try:
        st = os.stat(name)
        return (name, st.st_dev, st.st_ino)
    except OSError:
        return None


def likely_bloompetz_ports() -> list[str]:
    ports = []
    for p in list_ports.comports():
        if not p.device.startswith("/dev/ttyACM"):
            continue
        desc = f"{p.description or ''} {p.manufacturer or ''}".lower()
        if "esp32" in desc or "espressif" in desc or "usb jtag" in desc:
            ports.append(p.device)
    if ports:
        return sorted(ports)
    return sorted(p.device for p in list_ports.comports() if p.device.startswith("/dev/ttyACM"))


def launch(port: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["BLOOMPETZ_PORT"] = port
    return subprocess.Popen(
        [sys.executable, str(APP)],
        cwd=str(HERE),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    proc: subprocess.Popen | None = None
    launched_generation = None
    first_seen: dict[str, float] = {}

    while True:
        now = time.monotonic()
        ports = set(likely_bloompetz_ports())
        generations = {p: port_generation(p) for p in ports}

        for p in list(first_seen):
            if p not in ports:
                first_seen.pop(p, None)
        for p in ports:
            first_seen.setdefault(p, now)

        if launched_generation is not None and launched_generation not in generations.values():
            launched_generation = None

        if proc is not None and proc.poll() is not None:
            proc = None

        if proc is None and launched_generation is None and not programmer_running():
            for port in sorted(ports):
                gen = generations.get(port)
                if gen is None:
                    continue
                if now - first_seen.get(port, now) < STABLE_SECONDS:
                    continue
                proc = launch(port)
                launched_generation = gen
                break

        time.sleep(SCAN_SECONDS)


if __name__ == "__main__":
    main()
