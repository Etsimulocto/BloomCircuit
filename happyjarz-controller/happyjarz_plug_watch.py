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
HANDSHAKE_SECONDS = 2.0
BOOT_SETTLE_SECONDS = 0.35
SCAN_SECONDS = 1.0
RETRY_SECONDS = 2.0
HERE = Path(__file__).resolve().parent
CONTROLLER = HERE / "happyjarz_controller.py"


def is_happy_jar(port_name: str) -> bool:
    """Ask a serial device to identify itself as a HAPPY JARZ controller.

    Opening the ESP32-S3 CDC port may reset the board. The integrated firmware
    also performs touch calibration and OLED startup work before serial identity
    is available, so allow enough time for a complete boot before giving up.
    """
    try:
        with serial.Serial(port_name, BAUD, timeout=PROBE_TIMEOUT, write_timeout=0.5) as ser:
            time.sleep(BOOT_SETTLE_SECONDS)
            ser.reset_input_buffer()

            # Send HELLO more than once during the handshake window. If the first
            # one lands while the ESP32 is still booting, a later one will stick.
            deadline = time.time() + HANDSHAKE_SECONDS
            next_hello = 0.0
            while time.time() < deadline:
                now = time.time()
                if now >= next_hello:
                    ser.write(b"HELLO\n")
                    ser.flush()
                    next_hello = now + 0.40

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
    launched_ports: set[str] = set()
    retry_after: dict[str, float] = {}

    while True:
        current_ports = {p.device for p in list_ports.comports()}

        # Forget devices after unplug so reinserting the same port can launch again.
        launched_ports.intersection_update(current_ports)
        retry_after = {p: t for p, t in retry_after.items() if p in current_ports}

        if controller_proc is not None and controller_proc.poll() is not None:
            controller_proc = None

        if controller_proc is None:
            now = time.time()
            for port in sorted(current_ports):
                if port in launched_ports:
                    continue
                if now < retry_after.get(port, 0.0):
                    continue

                if is_happy_jar(port):
                    launched_ports.add(port)
                    retry_after.pop(port, None)
                    controller_proc = launch_controller()
                    break

                # A failed first probe is not permanent; the ESP32 may simply
                # still be completing its boot/calibration sequence.
                retry_after[port] = time.time() + RETRY_SECONDS

        time.sleep(SCAN_SECONDS)


if __name__ == "__main__":
    main()
