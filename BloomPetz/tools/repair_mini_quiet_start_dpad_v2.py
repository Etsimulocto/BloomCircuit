#!/usr/bin/env python3
"""Robust Pi-only BloomPetz Mini repair for local rebuilt variants.

Repairs:
- quiet serial startup: remove startup HELLO and GET STATUS, keep GET SCREEN
- proven 8BitDo D-pad via /dev/input/js0: axis6/7, buttons0/1
- exactly one gamepad worker launch

Does not touch firmware.
"""
from pathlib import Path
import re
import sys

MARKER = "# BLOOMPETZ_QUIET_START_DPAD_V2"

GAMEPAD_METHOD = r'''    # BLOOMPETZ_QUIET_START_DPAD_V2
    def _gamepad_worker(self):
        """Read the proven 8BitDo D-pad directly from /dev/input/js0."""
        import struct as _struct
        JS_EVENT_BUTTON = 0x01
        JS_EVENT_AXIS = 0x02
        JS_EVENT_INIT = 0x80
        axis_state = {6: 0, 7: 0}
        announced = False

        while self.running:
            dev = "/dev/input/js0"
            if not os.path.exists(dev):
                if not announced:
                    print("[BloomPetz] waiting for /dev/input/js0", flush=True)
                    announced = True
                time.sleep(0.5)
                continue

            fd = None
            try:
                fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
                print("[BloomPetz] GAMEPAD LIVE: D-pad axis6/7, A/B button0/1", flush=True)
                announced = False
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

                    if etype == JS_EVENT_BUTTON and value == 1:
                        if number == 0:
                            print("[BloomPetz] pad -> A", flush=True)
                            self.send("KEY A")
                        elif number == 1:
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
                print("[BloomPetz] ERROR: no permission for /dev/input/js0", flush=True)
                time.sleep(1.0)
            except OSError as exc:
                print(f"[BloomPetz] gamepad read error: {exc}", flush=True)
                time.sleep(0.5)
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            time.sleep(0.25)

'''


def method_span(text: str, name: str):
    m = re.search(rf'(?m)^    def {re.escape(name)}\([^\n]*\):\n', text)
    if not m:
        return None
    n = re.search(r'(?m)^    (?:def |@staticmethod\s*$|@classmethod\s*$)', text[m.end():])
    end = m.end() + n.start() if n else len(text)
    return m.start(), end


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: repair_mini_quiet_start_dpad_v2.py <bloompetz_mini.py>")
    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"Mini not found: {p}")

    original = p.read_text()
    s = original

    # Quiet startup: operate only inside _serial_worker, independent of formatting.
    span = method_span(s, "_serial_worker")
    if not span:
        raise SystemExit("_serial_worker not found")
    a, b = span
    block = s[a:b]
    if 'self.send("GET SCREEN")' not in block:
        raise SystemExit("GET SCREEN not found inside _serial_worker")
    block = re.sub(r'(?m)^\s*self\.send\("HELLO"\)\s*\n', '', block)
    block = re.sub(r'(?m)^\s*self\.send\("GET STATUS"\)\s*\n', '', block)
    if MARKER not in block:
        block = block.replace('self.send("GET SCREEN")', f'{MARKER}\n                self.send("GET SCREEN")', 1)
    s = s[:a] + block + s[b:]

    # Remove any old _gamepad_worker implementation, then insert the proven one before serial worker.
    old_span = method_span(s, "_gamepad_worker")
    if old_span:
        a, b = old_span
        s = s[:a] + s[b:]

    serial_span = method_span(s, "_serial_worker")
    if not serial_span:
        raise SystemExit("_serial_worker disappeared during patch")
    s = s[:serial_span[0]] + GAMEPAD_METHOD + "\n" + s[serial_span[0]:]

    # Remove all old gamepad thread starts.
    s = re.sub(r'(?m)^\s*threading\.Thread\(target=self\._gamepad_worker[^\n]*\n', '', s)
    s = re.sub(r'(?m)^\s*threading\.Thread\(target=self\._event_gamepad_worker[^\n]*\n', '', s)

    # Add one worker immediately after the serial worker launch, tolerant of whitespace.
    pat = r'(?m)^(\s*threading\.Thread\(target=self\._serial_worker,\s*daemon=True\)\.start\(\)\s*)$'
    m = re.search(pat, s)
    if not m:
        raise SystemExit("serial worker thread launch not found")
    indent = re.match(r'\s*', m.group(1)).group(0)
    replacement = m.group(1) + "\n" + indent + "threading.Thread(target=self._gamepad_worker, daemon=True).start()  # BLOOMPETZ_QUIET_START_DPAD_V2"
    s = s[:m.start()] + replacement + s[m.end():]

    # Syntax-check before writing.
    try:
        compile(s, str(p), "exec")
    except SyntaxError as exc:
        raise SystemExit(f"patched Mini would be invalid Python: {exc}")

    backup = p.with_suffix(p.suffix + ".pre_quiet_start_dpad_v2")
    if not backup.exists():
        backup.write_text(original)
    p.write_text(s)

    print(f"Repaired Mini: {p}")
    print("quiet startup: GET SCREEN only")
    print("gamepad: /dev/input/js0 D-pad axis6/7, A/B button0/1")
    print("Python syntax check: PASS")
    print("Firmware untouched; no compile/flash required.")


if __name__ == "__main__":
    main()
