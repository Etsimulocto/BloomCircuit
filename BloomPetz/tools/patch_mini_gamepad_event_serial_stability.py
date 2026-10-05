#!/usr/bin/env python3
"""Harden BloomPetz Mini gamepad input and serial startup without touching firmware.

Changes to desktop/bloompetz_mini.py only:
- keep existing /dev/input/js* joystick support
- add modern Linux /dev/input/event* gamepad support using stdlib only
- map D-pad/hat and left stick to UP/DOWN/LEFT/RIGHT
- map BTN_SOUTH / button0 to A and BTN_EAST / button1 to B
- avoid the startup HELLO + GET STATUS burst; request GET SCREEN only after open
  so host startup cannot exercise unrelated firmware command paths during boot
- add console diagnostics when a gamepad is detected

Firmware is intentionally untouched.
"""
from pathlib import Path
import sys

MARKER = "# BLOOMPETZ_GAMEPAD_EVENT_SERIAL_STABILITY_V1"

GAMEPAD_METHOD = r'''    # BLOOMPETZ_GAMEPAD_EVENT_SERIAL_STABILITY_V1
    @staticmethod
    def _event_gamepad_candidates():
        out = []
        for dev in sorted(glob.glob("/dev/input/event*")):
            base = os.path.basename(dev)
            name_path = f"/sys/class/input/{base}/device/name"
            try:
                name = open(name_path, "r", encoding="utf-8", errors="replace").read().strip()
            except Exception:
                name = ""
            low = name.lower()
            words = ("gamepad", "controller", "joystick", "xbox", "8bitdo", "dualshock", "dualsense", "gamesir", "pro controller", "usb game")
            if any(w in low for w in words):
                out.append((dev, name or base))
        return out

    def _event_gamepad_worker(self):
        """Read modern Linux input_event gamepads without pygame/evdev."""
        EV_KEY = 0x01
        EV_ABS = 0x03
        BTN_SOUTH = 304
        BTN_EAST = 305
        BTN_DPAD_UP = 544
        BTN_DPAD_DOWN = 545
        BTN_DPAD_LEFT = 546
        BTN_DPAD_RIGHT = 547
        ABS_X = 0
        ABS_Y = 1
        ABS_HAT0X = 16
        ABS_HAT0Y = 17
        event_size = struct.calcsize("llHHi")
        axis_state = {}
        last_dev = None
        while self.running:
            candidates = self._event_gamepad_candidates()
            if not candidates:
                time.sleep(0.75)
                continue
            dev, name = candidates[0]
            if dev != last_dev:
                print(f"[BloomPetz] gamepad event device: {dev} ({name})", flush=True)
                last_dev = dev
            fd = None
            try:
                fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
                axis_state.clear()
                while self.running and os.path.exists(dev):
                    try:
                        packet = os.read(fd, event_size)
                    except BlockingIOError:
                        time.sleep(0.01)
                        continue
                    except OSError:
                        break
                    if len(packet) != event_size:
                        time.sleep(0.01)
                        continue
                    _sec, _usec, etype, code, value = struct.unpack("llHHi", packet)
                    if etype == EV_KEY and value == 1:
                        if code == BTN_SOUTH:
                            self.send("KEY A")
                        elif code == BTN_EAST:
                            self.send("KEY B")
                        elif code == BTN_DPAD_UP:
                            self.send("KEY UP")
                        elif code == BTN_DPAD_DOWN:
                            self.send("KEY DOWN")
                        elif code == BTN_DPAD_LEFT:
                            self.send("KEY LEFT")
                        elif code == BTN_DPAD_RIGHT:
                            self.send("KEY RIGHT")
                    elif etype == EV_ABS and code in (ABS_X, ABS_Y, ABS_HAT0X, ABS_HAT0Y):
                        # Hat values are usually -1/0/+1; sticks are usually large signed ranges.
                        if code in (ABS_HAT0X, ABS_HAT0Y):
                            pos = -1 if value < 0 else (1 if value > 0 else 0)
                        else:
                            pos = -1 if value < -12000 else (1 if value > 12000 else 0)
                        old = axis_state.get(code, 0)
                        axis_state[code] = pos
                        if pos == 0 or pos == old:
                            continue
                        if code in (ABS_X, ABS_HAT0X):
                            self.send("KEY LEFT" if pos < 0 else "KEY RIGHT")
                        else:
                            self.send("KEY UP" if pos < 0 else "KEY DOWN")
            except PermissionError:
                print(f"[BloomPetz] no permission for gamepad {dev}; user must be in input group", flush=True)
                time.sleep(1.0)
            except OSError:
                time.sleep(0.75)
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            time.sleep(0.35)

'''


def fail(msg):
    raise SystemExit(msg)


def main():
    if len(sys.argv) != 2:
        fail("usage: patch_mini_gamepad_event_serial_stability.py <bloompetz_mini.py>")
    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        fail(f"Mini not found: {p}")
    s = p.read_text()
    if MARKER in s:
        print("Mini gamepad/event serial-stability patch already applied.")
        return
    required = [
        "class BloomPetzMini(tk.Tk):",
        "def send(self, command: str):",
        "threading.Thread(target=self._serial_worker, daemon=True).start()",
        'self.send("HELLO")',
        'self.send("GET SCREEN")',
        'self.send("GET STATUS")',
    ]
    missing = [x for x in required if x not in s]
    if missing:
        fail("Mini anchors missing: " + ", ".join(missing))
    if "import struct\n" not in s:
        anchor = "import subprocess\n"
        if anchor not in s:
            fail("import anchor missing")
        s = s.replace(anchor, anchor + "import struct\n", 1)

    # Start modern event-device worker in addition to any existing js* worker.
    thread_anchor = "        threading.Thread(target=self._serial_worker, daemon=True).start()\n"
    s = s.replace(thread_anchor, thread_anchor + "        threading.Thread(target=self._event_gamepad_worker, daemon=True).start()  # BLOOMPETZ_GAMEPAD_EVENT_SERIAL_STABILITY_V1\n", 1)

    # Insert methods immediately before send().
    send_anchor = "    def send(self, command: str):\n"
    s = s.replace(send_anchor, GAMEPAD_METHOD + send_anchor, 1)

    # Conservative startup: request the mirrored screen only. HELLO/GET STATUS can
    # still be sent manually later if needed, but they no longer execute during boot.
    old = '''                self.send("HELLO")\n                self.send("GET SCREEN")\n                self.send("GET STATUS")\n'''
    new = '''                # BLOOMPETZ_GAMEPAD_EVENT_SERIAL_STABILITY_V1\n                # Keep board boot quiet: opening Mini only asks for the screen.\n                self.send("GET SCREEN")\n'''
    if old not in s:
        fail("startup handshake block missing")
    s = s.replace(old, new, 1)

    backup = p.with_suffix(p.suffix + ".pre_gamepad_event_serial_stability")
    if not backup.exists():
        backup.write_text(p.read_text())
    p.write_text(s)
    print(f"Patched Mini: {p}")
    print("Added modern /dev/input/event* gamepad support plus existing js* support.")
    print("Startup serial handshake reduced to GET SCREEN only.")
    print("Firmware was not changed; no compile/flash is required for this patch.")


if __name__ == "__main__":
    main()
