#!/usr/bin/env python3
import os
import subprocess
import time

PORT = '/dev/ttyACM0'
APP = os.path.expanduser('~/BloomCircuit/happyjarz-controller/tools/happyjarz_meter.py')


def main():
    present = os.path.exists(PORT)
    armed = not present
    proc = None

    while True:
        now_present = os.path.exists(PORT)

        # Rearm only after an actual unplug. This prevents reopening the app
        # if the user manually closes it while the controller remains plugged in.
        if not now_present:
            armed = True
            if proc is not None and proc.poll() is not None:
                proc = None

        if now_present and armed:
            armed = False
            if proc is None or proc.poll() is not None:
                try:
                    proc = subprocess.Popen(['python3', APP])
                except Exception:
                    proc = None

        present = now_present
        time.sleep(0.5)


if __name__ == '__main__':
    main()
