#!/usr/bin/env python3
"""Repair the live BloomPetz Mini after the Mini rebuild regressed two proven fixes.

Desktop-only repair:
- restore quiet serial startup: GET SCREEN only (no startup HELLO / GET STATUS burst)
- restore 8BitDo /dev/input/js0 D-pad+A/B input

Bench-proven 8BitDo mapping on this exact Pi/controller:
  axis 6 = D-pad LEFT/RIGHT
  axis 7 = D-pad UP/DOWN
  button 0 = A
  button 1 = B

Firmware is intentionally untouched.
"""
from pathlib import Path
import re
import sys

MARKER = "# BLOOMPETZ_QUIET_START_DPAD_REPAIR_V1"

METHOD = r'''    # BLOOMPETZ_QUIET_START_DPAD_REPAIR_V1
    def _gamepad_worker(self):
        """Read the proven 8BitDo D-pad directly from Linux /dev/input/js0."""
        import struct as _struct

        JS_EVENT_BUTTON = 0x01
        JS_EVENT_AXIS = 0x02
        JS_EVENT_INIT = 0x80
        axis_state = {6: 0, 7: 0}
        announced_missing = False

        while self.running:
            dev = "/dev/input/js0"
            if not os.path.exists(dev):
                if not announced_missing:
                    print("[BloomPetz] waiting for 8BitDo /dev/input/js0", flush=True)
                    announced_missing = True
                time.sleep(0.5)
                continue

            announced_missing = False
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
                        time.sleep(0.005)
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
                print("[BloomPetz] ERROR: no permission to read /dev/input/js0", flush=True)
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


def fail(msg):
    raise SystemExit(msg)


def main():
    if len(sys.argv) != 2:
        fail("usage: repair_mini_quiet_start_dpad.py <bloompetz_mini.py>")

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        fail(f"Mini not found: {p}")

    original = p.read_text()
    s = original

    # Restore the proven quiet startup. Accept either exact old block or already-partial state.
    old = '''                self.send("HELLO")\n                self.send("GET SCREEN")\n                self.send("GET STATUS")\n'''
    if old in s:
        s = s.replace(
            old,
            '''                # BLOOMPETZ_QUIET_START_DPAD_REPAIR_V1\n                # Proven quiet startup: do not exercise HELLO/STATUS immediately after USB open.\n                self.send("GET SCREEN")\n''',
            1,
        )
    else:
        # Remove only startup HELLO/GET STATUS lines if a previous patch already reshaped spacing.
        serial_pos = s.find("    def _serial_worker(self):")
        send_pos = s.find("    def send(self, command: str):", serial_pos)
        if serial_pos < 0 or send_pos < 0:
            fail("could not locate serial worker/send section")
        block = s[serial_pos:send_pos]
        if 'self.send("GET SCREEN")' not in block:
            fail("serial startup GET SCREEN anchor missing")
        block = re.sub(r'^\s*self\.send\("HELLO"\)\s*\n', '', block, flags=re.M)
        block = re.sub(r'^\s*self\.send\("GET STATUS"\)\s*\n', '', block, flags=re.M)
        s = s[:serial_pos] + block + s[send_pos:]

    # Replace or insert one gamepad worker.
    start = s.find("    def _gamepad_worker(self):\n")
    if start >= 0:
        candidates = []
        for token in (
            "    def send(self, command: str):\n",
            "    @staticmethod\n",
            "    def _event_gamepad_worker(self):\n",
        ):
            pos = s.find(token, start + 1)
            if pos >= 0:
                candidates.append(pos)
        if not candidates:
            fail("could not locate end of existing _gamepad_worker")
        s = s[:start] + METHOD + "\n" + s[min(candidates):]
    else:
        send_pos = s.find("    def send(self, command: str):\n")
        if send_pos < 0:
            fail("send() anchor missing")
        s = s[:send_pos] + METHOD + "\n" + s[send_pos:]

    # Ensure exactly one _gamepad_worker launch, immediately after serial worker launch.
    lines = [line for line in s.splitlines(True)
             if "threading.Thread(target=self._gamepad_worker" not in line]
    s = "".join(lines)
    serial_launch = "        threading.Thread(target=self._serial_worker, daemon=True).start()\n"
    if serial_launch not in s:
        fail("serial worker launch anchor missing")
    s = s.replace(
        serial_launch,
        serial_launch + "        threading.Thread(target=self._gamepad_worker, daemon=True).start()  # BLOOMPETZ_QUIET_START_DPAD_REPAIR_V1\n",
        1,
    )

    # Prevent an older event-gamepad worker from being launched simultaneously.
    s = re.sub(
        r'^\s*threading\.Thread\(target=self\._event_gamepad_worker[^\n]*\n',
        '', s, flags=re.M
    )

    if MARKER not in s:
        future = "from __future__ import annotations\n"
        if future in s:
            s = s.replace(future, future + "\n" + MARKER + "\n", 1)
        else:
            s = MARKER + "\n" + s

    backup = p.with_suffix(p.suffix + ".pre_quiet_start_dpad_repair")
    if not backup.exists():
        backup.write_text(original)
    p.write_text(s)

    print(f"Repaired Mini: {p}")
    print("  startup serial: GET SCREEN only")
    print("  8BitDo D-pad: axis6/axis7")
    print("  8BitDo A/B: button0/button1")
    print("  one gamepad worker launch installed")
    print("Firmware unchanged; no compile/flash required.")


if __name__ == "__main__":
    main()
