#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_mini_hosttime_only_v3.py <bloompetz_mini.py>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()

marker = "BLOOMPETZ_HOSTTIME_ONLY_V3"
if marker in s:
    print("host-time-only repair already present")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".pre_hosttime_only_v3")
if not backup.exists():
    backup.write_text(s)

# Add a small helper immediately before _serial_worker. Do not touch _open_port.
anchor = "    def _serial_worker(self):\n"
if anchor not in s:
    raise SystemExit("_serial_worker anchor not found")

helper = '''    # BLOOMPETZ_HOSTTIME_ONLY_V3\n    def _send_host_time(self):\n        now = int(time.time())\n        lt = time.localtime(now)\n        if getattr(time, "daylight", 0) and lt.tm_isdst > 0:\n            offset_seconds = -int(time.altzone)\n        else:\n            offset_seconds = -int(time.timezone)\n        offset_minutes = int(offset_seconds // 60)\n        cmd = f"SET HOSTTIME {now} {offset_minutes}"\n        self.send(cmd)\n        print(f"[BloomPetz] HOSTTIME SENT: {cmd}", flush=True)\n\n'''
s = s.replace(anchor, helper + anchor, 1)

# Inject host time directly into the existing, proven connect sequence.
# Match HELLO regardless of nearby GET SCREEN/GET STATUS formatting.
pat = r'(?m)^(\s*)self\.send\("HELLO"\)\s*$'
m = re.search(pat, s)
if not m:
    raise SystemExit('self.send("HELLO") connect anchor not found')
indent = m.group(1)
replacement = f'{indent}self.send("HELLO")\n{indent}self._send_host_time()'
s = s[:m.start()] + replacement + s[m.end():]

# Add a second time send after GET STATUS if present in the same current source.
pat2 = r'(?m)^(\s*)self\.send\("GET STATUS"\)\s*$'
m2 = re.search(pat2, s)
if m2:
    indent2 = m2.group(1)
    replacement2 = f'{indent2}self.send("GET STATUS")\n{indent2}self._send_host_time()'
    s = s[:m2.start()] + replacement2 + s[m2.end():]

p.write_text(s)

# Syntax validation before claiming success.
import py_compile
py_compile.compile(str(p), doraise=True)

print("REPAIRED Mini host-time send only")
print("  _open_port left untouched")
print("  SET HOSTTIME added to existing connect sequence")
print("  Python syntax check: PASS")
print(f"patched: {p}")
