#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_mini_hosttime_noreset_v1.py <bloompetz_mini.py>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOMPETZ_HOSTTIME_NORESET_V1"

if marker in s:
    print("BloomPetz Mini host-time/no-reset repair already present")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".pre_hosttime_noreset_v1")
if not backup.exists():
    backup.write_text(s)

# datetime is only needed to obtain the local UTC offset, including DST.
if "import datetime\n" not in s:
    anchor = "import glob\n"
    if anchor not in s:
        raise SystemExit("import anchor not found")
    s = s.replace(anchor, anchor + "import datetime\n", 1)

# Always force the proven HAPPY JARZ serial-open pattern.  This deliberately
# avoids manual DTR/RTS manipulation, which previously caused a second boot.
start = s.find("    def _open_port(self, port: str) -> serial.Serial:\n")
if start < 0:
    start = s.find("    def _open_port(self, port):\n")
if start < 0:
    raise SystemExit("_open_port method not found")
end = s.find("    def ", start + 8)
if end < 0:
    raise SystemExit("could not find end of _open_port method")
open_method = '''    def _open_port(self, port: str) -> serial.Serial:\n        # BLOOMPETZ_HOSTTIME_NORESET_V1\n        # Proven HAPPY JARZ pattern: do not manually toggle DTR/RTS.\n        return serial.Serial(\n            port,\n            BAUD,\n            timeout=0.25,\n            write_timeout=0.25,\n        )\n\n'''
s = s[:start] + open_method + s[end:]

# Add a tiny host-time sender before the serial worker.
worker_anchor = "    def _serial_worker(self):\n"
if worker_anchor not in s:
    raise SystemExit("_serial_worker anchor not found")
host_method = '''    def _send_host_time(self):\n        try:\n            epoch = int(time.time())\n            offset = datetime.datetime.now().astimezone().utcoffset()\n            offset_minutes = int(offset.total_seconds() // 60) if offset else 0\n            self.send(f"SET HOSTTIME {epoch} {offset_minutes}")\n            print(f"[BloomPetz] HOSTTIME SENT: epoch={epoch} offset={offset_minutes}", flush=True)\n        except Exception as exc:\n            print(f"[BloomPetz] HOSTTIME ERROR: {exc}", flush=True)\n\n'''
s = s.replace(worker_anchor, host_method + worker_anchor, 1)

# Track periodic sync inside the worker.
old = '''    def _serial_worker(self):\n        seen_since = None\n        while self.running:\n'''
new = '''    def _serial_worker(self):\n        seen_since = None\n        last_host_time_sent = 0.0\n        while self.running:\n'''
if old not in s:
    raise SystemExit("serial worker initialization anchor not found")
s = s.replace(old, new, 1)

# Send clock immediately after the serial connection stabilizes.
old = '''                self.rx.put(("status", True))\n                time.sleep(0.15)\n                self.send("HELLO")\n                self.send("GET SCREEN")\n                self.send("GET STATUS")\n                continue\n'''
new = '''                self.rx.put(("status", True))\n                time.sleep(0.15)\n                self.send("HELLO")\n                self._send_host_time()\n                last_host_time_sent = time.monotonic()\n                self.send("GET SCREEN")\n                self.send("GET STATUS")\n                continue\n'''
if old not in s:
    raise SystemExit("serial-connect command block anchor not found")
s = s.replace(old, new, 1)

# Refresh while connected even if the ESP32 does not emit serial traffic.
old = '''            port = self.connected_port\n            if not port:\n                self.rx.put(("quit",))\n                return\n\n            if not os.path.exists(port):\n'''
new = '''            port = self.connected_port\n            if not port:\n                self.rx.put(("quit",))\n                return\n\n            now_mono = time.monotonic()\n            if now_mono - last_host_time_sent >= 60.0:\n                self._send_host_time()\n                last_host_time_sent = now_mono\n\n            if not os.path.exists(port):\n'''
if old not in s:
    raise SystemExit("connected-port anchor not found")
s = s.replace(old, new, 1)

p.write_text(s)
print("REPAIRED BLOOMPETZ MINI HOST TIME + NO-RESET SERIAL V1")
print("  host time sent immediately on connect")
print("  host time refreshed every 60 seconds")
print("  local UTC offset follows Pi timezone/DST")
print("  manual DTR/RTS toggles removed")
print(f"patched: {p}")
