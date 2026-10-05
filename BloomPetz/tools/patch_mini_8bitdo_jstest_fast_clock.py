#!/usr/bin/env python3
"""Use the proven Happy Jarz jstest/js0 path and shorten host-time attach delay.

Desktop-only patch for the evolved local BloomPetz Mini.
- Uses /dev/input/js0 through the installed `jstest --event` utility.
- Maps the 8BitDo/XInput layout used on this Pi:
    axes 0/1 = left stick, axes 6/7 = D-pad
    button 0 = A, button 1 = B
- Prints every mapped gamepad action so controller traffic is visible.
- Reduces STABLE_SECONDS from 2.0 to 0.25 so SET HOSTTIME reaches the board
  almost immediately after USB enumeration instead of several seconds later.

Firmware is not modified by this patch.
"""
from pathlib import Path
import re
import sys

MARKER = "# BLOOMPETZ_8BITDO_JSTEST_FAST_CLOCK_V1"

METHOD = r'''    # BLOOMPETZ_8BITDO_JSTEST_FAST_CLOCK_V1
    def _gamepad_worker(self):
        """Read the known Happy Jarz controller through `jstest --event /dev/input/js0`."""
        event_re = re.compile(r"type\s+(\d+).*number\s+(\d+).*value\s+(-?\d+)", re.I)
        axis_state = {}
        while self.running:
            devs = sorted(glob.glob("/dev/input/js*"))
            if not devs:
                time.sleep(0.5)
                continue
            dev = devs[0]
            try:
                print(f"[BloomPetz] 8BitDo joystick: {dev} via jstest", flush=True)
                proc = subprocess.Popen(
                    ["jstest", "--event", dev],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                while self.running and proc.poll() is None:
                    line = proc.stdout.readline() if proc.stdout else ""
                    if not line:
                        time.sleep(0.01)
                        continue
                    m = event_re.search(line)
                    if not m:
                        continue
                    etype = int(m.group(1))
                    number = int(m.group(2))
                    value = int(m.group(3))

                    # Linux joystick event types: 1=button, 2=axis.
                    if etype == 1 and value:
                        if number == 0:
                            self.send("KEY A")
                            print("[BloomPetz] pad -> A", flush=True)
                        elif number == 1:
                            self.send("KEY B")
                            print("[BloomPetz] pad -> B", flush=True)

                    elif etype == 2 and number in (0, 1, 6, 7):
                        pos = -1 if value < -16000 else (1 if value > 16000 else 0)
                        old = axis_state.get(number, 0)
                        axis_state[number] = pos
                        if pos == 0 or pos == old:
                            continue
                        if number in (0, 6):
                            key = "LEFT" if pos < 0 else "RIGHT"
                        else:
                            key = "UP" if pos < 0 else "DOWN"
                        self.send(f"KEY {key}")
                        print(f"[BloomPetz] pad -> {key}", flush=True)

                try:
                    proc.terminate()
                except Exception:
                    pass
            except FileNotFoundError:
                print("[BloomPetz] jstest not found; install package: joystick", flush=True)
                time.sleep(2.0)
            except PermissionError:
                print(f"[BloomPetz] no permission for {dev}", flush=True)
                time.sleep(1.0)
            except Exception as exc:
                print(f"[BloomPetz] gamepad error: {exc}", flush=True)
                time.sleep(0.75)
'''


def fail(msg):
    raise SystemExit(msg)


def main():
    if len(sys.argv) != 2:
        fail("usage: patch_mini_8bitdo_jstest_fast_clock.py <bloompetz_mini.py>")

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        fail(f"Mini not found: {p}")
    s = p.read_text()

    if MARKER in s:
        print("8BitDo jstest/fast-clock patch already applied.")
        return

    if "class BloomPetzMini(tk.Tk):" not in s:
        fail("BloomPetzMini class missing")
    if "def send(self, command: str):" not in s:
        fail("send() anchor missing")

    # The host-time layer already exists locally; shortening this attach guard makes
    # its existing _send_host_time() happen almost immediately after USB appears.
    s2, n = re.subn(r"^STABLE_SECONDS\s*=\s*[0-9.]+\s*$", "STABLE_SECONDS = 0.25", s, count=1, flags=re.M)
    if n != 1:
        fail("STABLE_SECONDS anchor missing")
    s = s2

    # Replace whichever gamepad worker is currently installed in the evolved Mini.
    start = s.find("    def _gamepad_worker(self):\n")
    if start < 0:
        fail("_gamepad_worker() missing")

    next_methods = []
    for token in (
        "    @staticmethod\n    def _event_gamepad_candidates():\n",
        "    # BLOOMPETZ_GAMEPAD_EVENT_SERIAL_STABILITY_V1\n",
        "    def _event_gamepad_worker(self):\n",
        "    def send(self, command: str):\n",
    ):
        pos = s.find(token, start + 1)
        if pos >= 0:
            next_methods.append(pos)
    if not next_methods:
        fail("could not locate end of _gamepad_worker(); refusing")
    end = min(next_methods)

    s = s[:start] + METHOD + "\n" + s[end:]

    # Ensure regex is available for the jstest parser.
    if "import re\n" not in s:
        anchor = "import random\n"
        if anchor not in s:
            fail("import anchor missing")
        s = s.replace(anchor, anchor + "import re\n", 1)

    # Add a top-level marker without disturbing imports or runtime behavior.
    s = s.replace("from __future__ import annotations\n", "from __future__ import annotations\n\n" + MARKER + "\n", 1)

    backup = p.with_suffix(p.suffix + ".pre_8bitdo_jstest_fast_clock")
    if not backup.exists():
        backup.write_text(p.read_text())
    p.write_text(s)

    print(f"Patched Mini: {p}")
    print("Gamepad path: jstest --event /dev/input/js0")
    print("Mapping: axes 0/1 + 6/7 => D-pad; buttons 0/1 => A/B")
    print("Host attach delay: STABLE_SECONDS=0.25")
    print("Firmware unchanged by this patch.")


if __name__ == "__main__":
    main()
