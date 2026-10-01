#!/usr/bin/env python3
"""HAPPY JARZ USB plug watcher.

Starts at user login, stays mostly invisible, and launches the controller when a
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
BOOT_SETTLE_SECONDS = 0.20
SCAN_SECONDS = 0.20
RETRY_SECONDS = 1.0
PORT_RELEASE_SECONDS = 0.30

HERE = Path(__file__).resolve().parent
CONTROLLER = HERE / "happyjarz_controller.py"
LOG_DIR = Path.home() / ".happyjarz"
WATCH_LOG = LOG_DIR / "plug_watch.log"
LAUNCH_LOG = LOG_DIR / "controller_launch.log"


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {message}"
    print(line, flush=True)
    try:
        with WATCH_LOG.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except OSError:
        pass


def port_generation(port_name: str):
    """Return a lightweight instance token for a serial device.

    On Linux, /dev/ttyACM0 can disappear and be recreated with the same name.
    The inode changes when that happens, which lets us detect a fast replug even
    when polling never catches a long 'port missing' interval. On other systems,
    fall back to the device name.
    """
    if os.name == "posix":
        try:
            st = os.stat(port_name)
            return (port_name, st.st_dev, st.st_ino)
        except OSError:
            return None
    return (port_name,)


def identify_happy_jar(port_name: str) -> str | None:
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
                    next_hello = now + 0.25

                line = ser.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("HJ|IDENTITY|"):
                    return line
    except (serial.SerialException, OSError):
        return None
    return None


def launch_controller() -> subprocess.Popen:
    python = sys.executable
    if sys.platform.startswith("win"):
        candidate = Path(python).with_name("pythonw.exe")
        if candidate.exists():
            python = str(candidate)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    launch_fp = LAUNCH_LOG.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        [python, str(CONTROLLER)],
        cwd=str(HERE),
        stdout=launch_fp,
        stderr=subprocess.STDOUT,
    )
    return proc


def main() -> None:
    controller_proc: subprocess.Popen | None = None
    launched_generation = None
    retry_after: dict[str, float] = {}

    log("HAPPY JARZ plug watcher started")

    while True:
        ports = {p.device: p for p in list_ports.comports()}
        current_ports = set(ports)

        # If the controller window was closed, allow the currently attached Jar
        # to launch it again on a later plug/replug event.
        if controller_proc is not None and controller_proc.poll() is not None:
            log(f"Controller PID {controller_proc.pid} exited")
            controller_proc = None

        # Track the actual device instance, not just '/dev/ttyACM0'. A fast
        # unplug/replug can reuse that pathname but creates a new device node.
        attached_generations = {
            name: port_generation(name)
            for name in current_ports
        }

        if launched_generation is not None:
            still_present = launched_generation in attached_generations.values()
            if not still_present:
                log("HAPPY JARZ unplug detected; replug is armed")
                launched_generation = None
                retry_after.clear()

        # Do not open the serial port while our controller already owns it.
        # The controller itself auto-reconnects after an unplug/replug.
        if controller_proc is None:
            now = time.time()
            for port in sorted(current_ports):
                generation = attached_generations.get(port)
                if generation is None:
                    continue
                if generation == launched_generation:
                    continue
                if now < retry_after.get(port, 0.0):
                    continue

                identity = identify_happy_jar(port)
                if identity:
                    log(f"Detected HAPPY JARZ on {port}: {identity}")
                    launched_generation = generation
                    retry_after.pop(port, None)
                    time.sleep(PORT_RELEASE_SECONDS)
                    controller_proc = launch_controller()
                    log(f"Launched controller PID {controller_proc.pid}; output -> {LAUNCH_LOG}")
                    break

                retry_after[port] = time.time() + RETRY_SECONDS

        time.sleep(SCAN_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("HAPPY JARZ plug watcher stopped")
