#!/usr/bin/env python3
"""Pi desktop watcher: identify firmware, release USB, then open the app."""
import fcntl
import json
import subprocess
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports
from bloomface import instance_lock

HERE = Path(__file__).resolve().parent


def identify(port):
    # HELLO is read-only for BloomFace; never send measurement/output commands.
    try:
        with serial.Serial(port, 115200, timeout=0.15, write_timeout=0.2) as connection:
            deadline = time.monotonic() + 1.5
            connection.write(b"HELLO\n")
            while time.monotonic() < deadline:
                line = connection.readline(8192)
                try:
                    d = json.loads(line)
                    if isinstance(d, dict) and d.get("type") == "hello":
                        return d.get("device") == "BloomFace" and d.get("protocol") == 1
                except (ValueError, UnicodeError):
                    pass
    except (OSError, serial.SerialException):
        pass
    return False


def main():
    directory = Path.home() / ".cache" / "bloomface"
    directory.mkdir(parents=True, exist_ok=True)
    watcher_lock = open(directory / "watcher.lock", "a")
    try:
        fcntl.flock(watcher_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    attempts, opened = {}, set()
    while True:
        ports = {p.device: p for p in list_ports.comports() if p.vid == 0x303A}
        opened.intersection_update(ports)
        attempts = {p: n for p, n in attempts.items() if p in ports}
        for port in ports:
            if port in opened or attempts.get(port, 0) >= 8:
                continue
            # Do not open or probe a port while a BloomFace window is running.
            try:
                app_lock = instance_lock()
            except RuntimeError:
                break
            try:
                attempts[port] = attempts.get(port, 0) + 1
                matched = identify(port)
            finally:
                app_lock.close()
            if matched:
                subprocess.Popen([sys.executable, str(HERE / "bloomface.py"), "--port", port], cwd=HERE)
                opened.add(port)
                time.sleep(1)
                break
        time.sleep(2)


if __name__ == "__main__":
    main()
