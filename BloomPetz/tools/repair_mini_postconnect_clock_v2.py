#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_mini_postconnect_clock_v2.py <bloompetz_mini.py>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOMPETZ_POSTCONNECT_CLOCK_V2"
if marker in s:
    print("BloomPetz post-connect clock V2 already present")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".pre_postconnect_clock_v2")
if not backup.exists():
    backup.write_text(s)

# 1) Replace _open_port method by method boundary, regardless of which old generation body is present.
pat = re.compile(r"(?ms)^    def _open_port\(self, port: str\) -> serial\.Serial:\n.*?(?=^    def _serial_worker\(self\):)")
new_open = '''    def _open_port(self, port: str) -> serial.Serial:\n        # BLOOMPETZ_POSTCONNECT_CLOCK_V2\n        # Proven HAPPY JARZ pattern: do not touch DTR/RTS.\n        return serial.Serial(\n            port,\n            BAUD,\n            timeout=0.25,\n            write_timeout=0.25,\n        )\n\n    def _host_time_command(self) -> str:\n        # Send epoch UTC plus the host's current UTC offset in minutes.\n        now = time.time()\n        local = time.localtime(now)\n        if local.tm_isdst > 0 and time.daylight:\n            offset_seconds = -time.altzone\n        else:\n            offset_seconds = -time.timezone\n        offset_minutes = int(offset_seconds // 60)\n        return f"SET HOSTTIME {int(now)} {offset_minutes}"\n\n    def _send_host_time(self):\n        cmd = self._host_time_command()\n        self.send(cmd)\n        try:\n            print(f"[BloomPetz] HOSTTIME SENT: {cmd}", flush=True)\n        except Exception:\n            pass\n\n'''
s, n = pat.subn(new_open, s, count=1)
if n != 1:
    raise SystemExit("could not replace _open_port method")

# 2) Add periodic timer state inside _serial_worker.
s, n = re.subn(
    r"(?m)^(    def _serial_worker\(self\):\n        seen_since = None\n)",
    r"\1        last_hosttime_send = 0.0\n",
    s,
    count=1,
)
if n != 1:
    raise SystemExit("could not add host-time timer state")

# 3) Replace only the first post-connect command sequence using a flexible regex.
connect_pat = re.compile(
    r'(?ms)(                self\.rx\.put\(\("status", True\)\)\n)'
    r'.*?'
    r'(                continue\n)'
)
m = connect_pat.search(s)
if not m:
    raise SystemExit("could not locate serial post-connect sequence")

replacement = '''                self.rx.put(("status", True))\n                # Recreate the useful post-connect initialization that the old\n                # accidental second reset used to provide, without resetting the ESP32.\n                time.sleep(0.20)\n                self.send("HELLO")\n                self._send_host_time()\n                time.sleep(0.35)\n                self.send("GET SCREEN")\n                self.send("GET STATUS")\n                # Send once more after the firmware has had time to service HELLO.\n                self._send_host_time()\n                last_hosttime_send = time.monotonic()\n                continue\n'''
s = s[:m.start()] + replacement + s[m.end():]

# 4) While connected, refresh host time every 60 seconds before normal reads.
needle = '''            port = self.connected_port\n            if not port:\n'''
if needle not in s:
    raise SystemExit("connected-port anchor not found")
periodic = '''            if time.monotonic() - last_hosttime_send >= 60.0:\n                self._send_host_time()\n                last_hosttime_send = time.monotonic()\n\n            port = self.connected_port\n            if not port:\n'''
s = s.replace(needle, periodic, 1)

# Syntax validate before touching the live file.
compile(s, str(p), "exec")
p.write_text(s)
print("REPAIRED BLOOMPETZ MINI POST-CONNECT CLOCK V2")
print("  no DTR/RTS reset toggling")
print("  HOSTTIME sent twice after serial attach")
print("  screen/status refreshed after clock sync")
print("  HOSTTIME refreshed every 60 seconds")
print("  Python syntax check: PASS")
print(f"patched: {p}")
