#!/usr/bin/env python3
"""Use Linux joystick semantic maps for BloomPetz Mini gamepad input.

Why:
- The Happy Jarz notes prove the user's 8BitDo controller is exposed as /dev/input/js0.
- Earlier Mini code guessed axis/button indexes. This patch asks the kernel for the
  joystick axis/button maps, then routes semantic codes (ABS_X, ABS_HAT0X,
  BTN_SOUTH, BTN_EAST, etc.) into the existing KEY protocol.
- No firmware changes.
"""
from pathlib import Path
import sys

MARKER = "# BLOOMPETZ_JS0_SEMANTIC_GAMEPAD_V1"

METHOD = r'''    # BLOOMPETZ_JS0_SEMANTIC_GAMEPAD_V1
    def _gamepad_worker(self):
        import array
        import fcntl

        # Linux input/joystick semantic codes.
        ABS_X = 0x00
        ABS_Y = 0x01
        ABS_HAT0X = 0x10
        ABS_HAT0Y = 0x11
        BTN_SOUTH = 0x130
        BTN_EAST = 0x131
        BTN_A = 0x130
        BTN_B = 0x131

        # ioctl encoding from linux/ioctl.h; JSIOCGAXMAP / JSIOCGBTNMAP.
        IOC_NRBITS = 8
        IOC_TYPEBITS = 8
        IOC_SIZEBITS = 14
        IOC_NRSHIFT = 0
        IOC_TYPESHIFT = IOC_NRSHIFT + IOC_NRBITS
        IOC_SIZESHIFT = IOC_TYPESHIFT + IOC_TYPEBITS
        IOC_DIRSHIFT = IOC_SIZESHIFT + IOC_SIZEBITS
        IOC_READ = 2

        def _ior(type_chr, nr, size):
            return ((IOC_READ << IOC_DIRSHIFT) |
                    (ord(type_chr) << IOC_TYPESHIFT) |
                    (nr << IOC_NRSHIFT) |
                    (size << IOC_SIZESHIFT))

        JSIOCGAXMAP = _ior('j', 0x32, 0x40)   # __u8[ABS_CNT]
        JSIOCGBTNMAP = _ior('j', 0x34, 0x400) # __u16[KEY_MAX-BTN_MISC+1]

        while self.running:
            devices = sorted(glob.glob("/dev/input/js*"))
            if not devices:
                time.sleep(0.75)
                continue

            dev = devices[0]
            fd = None
            try:
                fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)

                axmap = array.array('B', [0] * 0x40)
                btnmap = array.array('H', [0] * 0x200)
                try:
                    fcntl.ioctl(fd, JSIOCGAXMAP, axmap, True)
                    fcntl.ioctl(fd, JSIOCGBTNMAP, btnmap, True)
                    print(f"[BloomPetz] joystick: {dev} semantic mapping active", flush=True)
                except OSError as exc:
                    print(f"[BloomPetz] joystick map ioctl failed on {dev}: {exc}", flush=True)
                    axmap = None
                    btnmap = None

                axis_state = {}
                while self.running and os.path.exists(dev):
                    try:
                        packet = os.read(fd, 8)
                    except BlockingIOError:
                        time.sleep(0.01)
                        continue
                    except OSError:
                        break

                    if len(packet) != 8:
                        time.sleep(0.01)
                        continue

                    _ms, value, etype, number = struct.unpack("IhBB", packet)
                    etype &= ~0x80  # JS_EVENT_INIT

                    if etype == 0x01:  # JS_EVENT_BUTTON
                        if not value:
                            continue
                        code = btnmap[number] if btnmap is not None and number < len(btnmap) else None
                        if code in (BTN_SOUTH, BTN_A):
                            self.send("KEY A")
                            print("[BloomPetz] pad -> A", flush=True)
                        elif code in (BTN_EAST, BTN_B):
                            self.send("KEY B")
                            print("[BloomPetz] pad -> B", flush=True)

                    elif etype == 0x02:  # JS_EVENT_AXIS
                        code = axmap[number] if axmap is not None and number < len(axmap) else None
                        if code not in (ABS_X, ABS_Y, ABS_HAT0X, ABS_HAT0Y):
                            continue

                        # Hats are full-scale too through js API; sticks use same threshold.
                        pos = -1 if value < -16000 else (1 if value > 16000 else 0)
                        old = axis_state.get(code, 0)
                        axis_state[code] = pos
                        if pos == 0 or pos == old:
                            continue

                        if code in (ABS_X, ABS_HAT0X):
                            key = "LEFT" if pos < 0 else "RIGHT"
                        else:
                            key = "UP" if pos < 0 else "DOWN"
                        self.send(f"KEY {key}")
                        print(f"[BloomPetz] pad -> {key}", flush=True)

            except PermissionError:
                print(f"[BloomPetz] no permission for {dev}", flush=True)
                time.sleep(1.0)
            except OSError as exc:
                print(f"[BloomPetz] joystick open/read error {dev}: {exc}", flush=True)
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
        fail("usage: patch_mini_js0_semantic_gamepad.py <bloompetz_mini.py>")
    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        fail(f"Mini not found: {p}")
    s = p.read_text()
    if MARKER in s:
        print("js0 semantic gamepad patch already applied.")
        return

    start = s.find("    def _gamepad_worker(self):\n")
    if start < 0:
        fail("existing _gamepad_worker() not found; apply room/gamepad patch first")

    # End at the next class-level method after _gamepad_worker.
    candidates = []
    for anchor in (
        "    @staticmethod\n    def _event_gamepad_candidates():\n",
        "    # BLOOMPETZ_GAMEPAD_EVENT_SERIAL_STABILITY_V1\n",
        "    def send(self, command: str):\n",
    ):
        pos = s.find(anchor, start + 1)
        if pos >= 0:
            candidates.append(pos)
    if not candidates:
        fail("could not locate end of existing _gamepad_worker(); refusing")
    end = min(candidates)

    old = s[start:end]
    if "glob.glob(\"/dev/input/js*\")" not in old:
        fail("existing gamepad worker does not look like js* reader; refusing")

    repaired = s[:start] + METHOD + s[end:]
    backup = p.with_suffix(p.suffix + ".pre_js0_semantic")
    if not backup.exists():
        backup.write_text(s)
    p.write_text(repaired)

    print(f"Patched Mini js0 gamepad mapping: {p}")
    print("Uses kernel semantic axis/button maps instead of guessed indexes.")
    print("No firmware compile/flash required.")


if __name__ == "__main__":
    main()
