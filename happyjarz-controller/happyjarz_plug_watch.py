#!/usr/bin/env python3
"""HAPPY JARZ USB plug watcher.

Starts at user login, stays invisible, and launches the controller when a
HAPPY JARZ device identifies itself over USB serial.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports

BAUD = 115200
PROBE_TIMEOUT = 0.25
SCAN_SECONDS = 1.0
HERE = Path(__file__).resolve().parent
CONTROLLER = HERE / "happyjarz_controller.py"


def is_happy_jar(port_name: str) -> bool:
    try:
        with serial.Serial(port_name, BAUD, timeout=PROBE_TIMEOUT, write_timeout=0.5) as ser:
            time.sleep(0.08)
            ser.reset_input_buffer()
            ser.write(b"HELLO\n")
            ser.flush()
            deadline = time.time() + 0.45
            while time.time() < deadline:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("HJ|IDENTITY|"):
                    return True
    except (serial.SerialException, OSError):
        return False
    return False


def launch_controller() -> subprocess.Popen:
    python = sys.executable
    # On Windows, prefer pythonw so no console window appears.
    if sys.platform.startswith("win"):
        candidate = Path(python).with_name("pythonw.exe")
        if candidate.exists():
            python = str(candidate)
    return subprocess.Popen([python, str(CONTROLLER)], cwd=str(HERE))


def main() -> None:
    controller_proc: subprocess.Popen | None = None
    seen_ports: set[str] = set()

    while True:
        current_ports = {p.device for p in list_ports.comports()}

        # Allow a removed/reinserted Jar to trigger again later.
        seen_ports.intersection_update(current_ports)

        if controller_proc is not None and controller_proc.poll() is not None:
            controller_proc = None

        if controller_proc is None:
            for port in sorted(current_ports - seen_ports):
                seen_ports.add(port)
                if is_happy_jar(port):
                    controller_proc = launch_controller()
                    break

        time.sleep(SCAN_SECONDS)


if __name__ == "__main__":
    main()
