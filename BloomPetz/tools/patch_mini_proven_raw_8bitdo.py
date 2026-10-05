#!/usr/bin/env python3
"""BloomPetz Mini: use the proven raw 8BitDo /dev/input/js0 mapping directly.

Bench evidence from jstest --event on this exact Pi/controller:
  axis 6 = D-pad horizontal
  axis 7 = D-pad vertical
  button 0 = A
  button 1 = B

Why this replaces the jstest subprocess worker:
`jstest --event` is interactive CLI software and may buffer output when stdout is
piped into another process. Reading Linux joystick events directly avoids that
entire layer and uses the same /dev/input/js0 device that was physically proven.

Desktop-only. Firmware is not modified.
"""
from pathlib import Path
import re
import sys

MARKER = "# BLOOMPETZ_PROVEN_RAW_8BITDO_V1"

METHOD = r'''    # BLOOMPETZ_PROVEN_RAW_8BITDO_V1
    def _gamepad_worker(self):
        """Read the proven 8BitDo mapping directly from Linux /dev/input/js0."""
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
                    print("[BloomPetz] waiting for gamepad /dev/input/js0", flush=True)
                    announced_missing = True
                time.sleep(0.5)
                continue

            announced_missing = False
            fd = None
            try:
                fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
                print("[BloomPetz] GAMEPAD LIVE: /dev/input/js0 raw 8BitDo map", flush=True)
                print("[BloomPetz] map: axis6=L/R axis7=U/D button0=A button1=B", flush=True)
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
                        # Fire once on press; release is ignored.
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

                    # One KEY event per fresh direction press. Returning to zero arms it again.
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
        fail("usage: patch_mini_proven_raw_8bitdo.py <bloompetz_mini.py>")

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        fail(f"Mini not found: {p}")
    s = p.read_text()

    if MARKER in s:
        print("Proven raw 8BitDo patch already applied.")
        return
    if "class BloomPetzMini(tk.Tk):" not in s:
        fail("BloomPetzMini class missing")
    if "    def send(self, command: str):\n" not in s:
        fail("send() anchor missing")

    # Replace the existing gamepad worker, regardless of which earlier experiment installed it.
    start = s.find("    def _gamepad_worker(self):\n")
    if start >= 0:
        candidates = []
        for token in (
            "    @staticmethod\n    def _event_gamepad_candidates():\n",
            "    # BLOOMPETZ_GAMEPAD_EVENT_SERIAL_STABILITY_V1\n",
            "    def _event_gamepad_worker(self):\n",
            "    def send(self, command: str):\n",
        ):
            pos = s.find(token, start + 1)
            if pos >= 0:
                candidates.append(pos)
        if not candidates:
            fail("could not determine end of current _gamepad_worker(); refusing")
        end = min(candidates)
        s = s[:start] + METHOD + "\n" + s[end:]
    else:
        send_pos = s.find("    def send(self, command: str):\n")
        s = s[:send_pos] + METHOD + "\n" + s[send_pos:]

    # Ensure exactly one worker launch exists. Remove earlier launch variants first.
    lines = s.splitlines(True)
    cleaned = []
    for line in lines:
        if "threading.Thread(target=self._gamepad_worker" in line:
            continue
        cleaned.append(line)
    s = "".join(cleaned)

    serial_launch = "        threading.Thread(target=self._serial_worker, daemon=True).start()\n"
    if serial_launch not in s:
        fail("serial worker launch anchor missing")
    s = s.replace(
        serial_launch,
        serial_launch + "        threading.Thread(target=self._gamepad_worker, daemon=True).start()  # BLOOMPETZ_PROVEN_RAW_8BITDO_V1\n",
        1,
    )

    # Earlier event-device worker can remain harmlessly defined, but do not launch it.
    s = re.sub(
        r'^\s*threading\.Thread\(target=self\._event_gamepad_worker[^\n]*\n',
        '', s, flags=re.M
    )

    # Mark the evolved local Mini without changing behavior.
    future = "from __future__ import annotations\n"
    if future in s:
        s = s.replace(future, future + "\n" + MARKER + "\n", 1)
    else:
        s = MARKER + "\n" + s

    backup = p.with_suffix(p.suffix + ".pre_proven_raw_8bitdo")
    if not backup.exists():
        backup.write_text(p.read_text())
    p.write_text(s)

    print(f"Patched Mini: {p}")
    print("Direct raw gamepad mapping installed:")
    print("  axis 6 -> LEFT/RIGHT")
    print("  axis 7 -> UP/DOWN")
    print("  button 0 -> A")
    print("  button 1 -> B")
    print("Ensured one _gamepad_worker thread starts with Mini.")
    print("Firmware unchanged; no flash required for this patch.")


if __name__ == "__main__":
    main()
