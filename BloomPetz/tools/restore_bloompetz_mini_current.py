#!/usr/bin/env python3
"""Restore the current BloomPetz Mini generation safely.

Starts from the authoritative V3 rebuild, then preserves the two proven fixes:
- Happy Jarz simple serial open (no manual DTR/RTS toggling; prevents second boot)
- raw 8BitDo /dev/input/js0 D-pad+A/B input

V3 already provides:
- 21-column mirror support
- DND-aware layout with side art hidden in DND
- clickable six-button controls
- host time sync on connect and every 60 seconds
"""
from pathlib import Path
import py_compile
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REBUILD = ROOT / "BloomPetz/tools/rebuild_bloompetz_mini_v3.py"
APP = ROOT / "BloomPetz/desktop/bloompetz_mini.py"


def main():
    if not REBUILD.exists():
        raise SystemExit(f"missing V3 rebuild tool: {REBUILD}")

    backup = APP.with_suffix(".py.before_current_restore")
    if APP.exists() and not backup.exists():
        backup.write_text(APP.read_text())

    subprocess.run([sys.executable, str(REBUILD)], check=True)
    s = APP.read_text()

    old_open = '''    def _open_port(self,port):\n        s=serial.Serial(); s.port=port; s.baudrate=BAUD; s.timeout=.25; s.write_timeout=.25\n        s.dtr=False; s.rts=False; s.open(); s.dtr=False; s.rts=False; return s\n'''
    new_open = '''    def _open_port(self,port):\n        # Proven Happy Jarz pattern: do not manually toggle DTR/RTS.\n        return serial.Serial(port, BAUD, timeout=.25, write_timeout=.25)\n'''
    if old_open not in s:
        raise SystemExit("V3 _open_port anchor not found")
    s = s.replace(old_open, new_open, 1)

    # Start the proven raw 8BitDo reader beside the serial worker.
    serial_launch = '        threading.Thread(target=self._serial_worker, daemon=True).start()\n'
    gamepad_launch = '        threading.Thread(target=self._gamepad_worker, daemon=True).start()\n'
    if serial_launch not in s:
        raise SystemExit("V3 serial thread launch anchor not found")
    s = s.replace(serial_launch, serial_launch + gamepad_launch, 1)

    anchor = '    def _open_port(self,port):\n'
    if anchor not in s:
        raise SystemExit("patched _open_port anchor missing")

    gamepad = r'''    def _gamepad_worker(self):
        """Read physical 8BitDo D-pad axis6/7 and A/B button0/1."""
        import struct as _struct
        JS_EVENT_BUTTON = 0x01
        JS_EVENT_AXIS = 0x02
        JS_EVENT_INIT = 0x80
        axis_state = {6: 0, 7: 0}

        while self.running:
            dev = "/dev/input/js0"
            if not os.path.exists(dev):
                time.sleep(0.5)
                continue

            fd = None
            try:
                fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
                print("[BloomPetz] GAMEPAD LIVE: D-pad axis6/7, A/B button0/1", flush=True)
                axis_state = {6: 0, 7: 0}

                while self.running and os.path.exists(dev):
                    try:
                        packet = os.read(fd, 8)
                    except BlockingIOError:
                        time.sleep(0.005)
                        continue
                    except OSError:
                        break

                    if len(packet) != 8:
                        continue

                    _ms, value, etype, number = _struct.unpack("IhBB", packet)
                    etype &= ~JS_EVENT_INIT

                    if etype == JS_EVENT_BUTTON:
                        if value == 1 and number == 0:
                            print("[BloomPetz] pad -> A", flush=True)
                            self.send("KEY A")
                        elif value == 1 and number == 1:
                            print("[BloomPetz] pad -> B", flush=True)
                            self.send("KEY B")
                        continue

                    if etype != JS_EVENT_AXIS or number not in (6, 7):
                        continue

                    pos = -1 if value < -16000 else (1 if value > 16000 else 0)
                    old = axis_state[number]
                    axis_state[number] = pos
                    if pos == 0 or pos == old:
                        continue

                    if number == 6:
                        key = "LEFT" if pos < 0 else "RIGHT"
                    else:
                        key = "UP" if pos < 0 else "DOWN"

                    print(f"[BloomPetz] pad -> {key}", flush=True)
                    self.send(f"KEY {key}")

            except PermissionError:
                print("[BloomPetz] no permission for /dev/input/js0", flush=True)
                time.sleep(1.0)
            except OSError as exc:
                print(f"[BloomPetz] gamepad error: {exc}", flush=True)
                time.sleep(0.5)
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            time.sleep(0.25)

'''
    s = s.replace(anchor, gamepad + anchor, 1)
    APP.write_text(s)
    py_compile.compile(str(APP), doraise=True)

    print(f"RESTORED CURRENT MINI: {APP}")
    print("  V3 21-column/DND-aware layout")
    print("  DND hides side art")
    print("  host time sync restored")
    print("  Happy Jarz no-reset serial open")
    print("  8BitDo D-pad axis6/7 + A/B button0/1")
    print("  Python syntax check: PASS")
    print("Firmware untouched; no compile/flash required.")


if __name__ == "__main__":
    main()
