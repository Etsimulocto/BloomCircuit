#!/usr/bin/env python3
import os
import subprocess
import time

PORT = '/dev/ttyACM0'
APP = os.path.expanduser('~/BloomCircuit/happyjarz-controller/tools/happyjarz_meter.py')
STABLE_SECONDS = 2.0
POLL_SECONDS = 0.25


def programmer_running():
    """Do not grab the serial port while Arduino/esptool is compiling or flashing."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'arduino-cli|esptool'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def main():
    present = os.path.exists(PORT)
    armed = not present
    proc = None
    appeared_at = time.monotonic() if present else None

    while True:
        now_present = os.path.exists(PORT)

        # An actual unplug rearms auto-launch. It also clears the stability timer.
        if not now_present:
            armed = True
            appeared_at = None
            if proc is not None and proc.poll() is not None:
                proc = None
        else:
            if not present or appeared_at is None:
                appeared_at = time.monotonic()

            stable = (time.monotonic() - appeared_at) >= STABLE_SECONDS

            # Only launch after the USB serial device has stayed up long enough
            # to rule out reset/bootloader transitions, and never during a flash.
            if armed and stable and not programmer_running():
                armed = False
                if proc is None or proc.poll() is not None:
                    try:
                        proc = subprocess.Popen(['python3', APP])
                    except Exception:
                        proc = None

        present = now_present
        time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
