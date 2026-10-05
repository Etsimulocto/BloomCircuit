#!/usr/bin/env python3
from pathlib import Path
import sys

SERIAL_WORKER = r'''    def _serial_worker(self):
        seen_since = None
        while self.running:
            if programmer_running():
                time.sleep(POLL_SECONDS)
                continue

            if self.ser is None:
                port = self._choose_port()
                if port is None:
                    if ASSIGNED_PORT:
                        self.rx.put(("quit",))
                        return
                    seen_since = None
                    time.sleep(POLL_SECONDS)
                    continue
                if seen_since is None:
                    seen_since = time.monotonic()
                if time.monotonic() - seen_since < STABLE_SECONDS:
                    time.sleep(POLL_SECONDS)
                    continue
                try:
                    s = self._open_port(port)
                except Exception:
                    time.sleep(0.4)
                    continue
                with self.ser_lock:
                    self.ser = s
                    self.connected_port = port
                self.rx.put(("status", True))
                time.sleep(0.15)
                # Quiet startup: preserve no-reset open and only request current screen.
                self.send("GET SCREEN")
                continue

            port = self.connected_port
            if not port:
                self.rx.put(("quit",))
                return

            if not os.path.exists(port):
                missing_since = time.monotonic()
                while self.running and not os.path.exists(port):
                    if time.monotonic() - missing_since >= DISCONNECT_GRACE_SEC:
                        self.rx.put(("quit",))
                        return
                    time.sleep(POLL_SECONDS)
                continue

            try:
                raw = self.ser.readline() if self.ser else b""
            except Exception:
                if not os.path.exists(port):
                    self.rx.put(("quit",))
                    return
                time.sleep(POLL_SECONDS)
                continue
            if raw:
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if line:
                    self.rx.put(("line", line))

'''

def fail(msg):
    raise SystemExit(msg)

def main():
    if len(sys.argv) != 2:
        fail("usage: repair_restore_serial_worker_keep_noreset.py <bloompetz_mini.py>")
    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if "    def _serial_worker(self):" in s:
        print("_serial_worker already present; no repair needed")
        return

    anchor = "    def close_app(self):\n"
    if anchor not in s:
        fail("close_app anchor missing")

    backup = p.with_suffix(p.suffix + ".pre_restore_serial_worker")
    if not backup.exists():
        backup.write_text(s)

    s = s.replace(anchor, SERIAL_WORKER + anchor, 1)
    p.write_text(s)

    import py_compile
    py_compile.compile(str(p), doraise=True)

    print(f"Repaired Mini: {p}")
    print("  restored: _serial_worker")
    print("  preserved: Happy Jarz simple serial open")
    print("  startup: GET SCREEN only")
    print("  Python syntax check: PASS")
    print("Firmware untouched; no compile/flash required.")

if __name__ == "__main__":
    main()
