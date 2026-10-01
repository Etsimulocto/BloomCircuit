#!/usr/bin/env python3
"""HAPPY JARZ USB plug watcher.

Starts at user login, stays invisible, and launches the controller when a
HAPPY JARZ device identifies itself over USB serial.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import serial
from serial.tools import list_ports

BAUD = 115200
PROBE_TIMEOUT = 0.25
HANDSHAKE_SECONDS = 2.0
BOOT_SETTLE_SECONDS = 0.35
PORT_RELEASE_SECONDS = 0.60
SCAN_SECONDS = 1.0
RETRY_SECONDS = 2.0
HERE = Path(__file__).resolve().parent
CONTROLLER = HERE / "happyjarz_controller.py"
LOG_DIR = Path.home() / ".happyjarz"
LOG_FILE = LOG_DIR / "plug_watch.log"


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp}  {message}"
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except OSError:
        pass
    # Useful when launched manually; harmless when run from desktop autostart.
    print(line, flush=True)


def is_happy_jar(port_name: str) -> bool:
    """Ask a serial device to identify itself as a HAPPY JARZ controller."""
    try:
        with serial.Serial(port_name, BAUD, timeout=PROBE_TIMEOUT, write_timeout=0.5) as ser:
            time.sleep(BOOT_SETTLE_SECONDS)
            ser.reset_input_buffer()
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
                    log(f"Detected HAPPY JARZ on {port_name}: {line}")
                    return True
    except (serial.SerialException, OSError) as exc:
        log(f"Probe failed on {port_name}: {exc}")
        return False
    return False


def launch_controller() -> subprocess.Popen:
    python = sys.executable
    if sys.platform.startswith("win"):
        candidate = Path(python).with_name("pythonw.exe")
        if candidate.exists():
            python = str(candidate)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    err_path = LOG_DIR / "controller_launch.log"
    err_fp = err_path.open("a", encoding="utf-8")

    env = os.environ.copy()
    proc = subprocess.Popen(
        [python, str(CONTROLLER)],
        cwd=str(HERE),
        env=env,
        stdout=err_fp,
        stderr=err_fp,
        start_new_session=not sys.platform.startswith("win"),
    )
    log(f"Launched controller PID {proc.pid}; output -> {err_path}")
    return proc


def main() -> None:
    log("HAPPY JARZ plug watcher started")
    controller_proc: subprocess.Popen | None = None
    launched_ports: set[str] = set()
    retry_after: dict[str, float] = {}

    while True:
        current_ports = {p.device for p in list_ports.comports()}

        launched_ports.intersection_update(current_ports)
        retry_after = {p: t for p, t in retry_after.items() if p in current_ports}

        if controller_proc is not None and controller_proc.poll() is not None:
            log(f"Controller exited with code {controller_proc.returncode}")
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
                    # Give Linux/USB CDC a moment to release the serial handle.
                    time.sleep(PORT_RELEASE_SECONDS)
                    controller_proc = launch_controller()
                    break

                retry_after[port] = time.time() + RETRY_SECONDS

        time.sleep(SCAN_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Watcher stopped by user")
