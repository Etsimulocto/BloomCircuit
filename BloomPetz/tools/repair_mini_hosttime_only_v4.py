#!/usr/bin/env python3
from pathlib import Path
import ast
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_mini_hosttime_only_v4.py <bloompetz_mini.py>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()

if "HOSTTIME ONLY V4" in s:
    print("Mini host-time V4 already present")
    raise SystemExit(0)

# Leave serial-open behavior completely untouched. We only patch _serial_worker
# after a successful self.ser assignment, using the actual assignment as anchor.
anchor = '''                with self.ser_lock:\n                    self.ser = s\n                    self.connected_port = port\n'''
if anchor not in s:
    raise SystemExit("live serial assignment anchor not found")

insert = anchor + '''                # HOSTTIME ONLY V4 - restore clock sync without touching serial reset behavior\n                try:\n                    now = time.time()\n                    local = time.localtime(now)\n                    utc = time.gmtime(now)\n                    # mktime interprets tuples as local time; difference yields local UTC offset incl. DST.\n                    offset_minutes = int((time.mktime(local) - time.mktime(utc)) / 60)\n                    cmd = f"SET HOSTTIME {int(now)} {offset_minutes}"\n                    self.send(cmd)\n                    print(f"[BloomPetz] HOSTTIME SENT: {cmd}", flush=True)\n                except Exception as exc:\n                    print(f"[BloomPetz] HOSTTIME ERROR: {exc}", flush=True)\n'''
s = s.replace(anchor, insert, 1)

# Add a conservative periodic refresh in the connected loop, without restructuring it.
# We key it off an instance field initialized lazily.
loop_anchor = '''            port = self.connected_port\n            if not port:\n'''
if loop_anchor not in s:
    raise SystemExit("connected-loop anchor not found")

loop_insert = '''            # HOSTTIME ONLY V4 periodic refresh; does not reset/reopen the device.\n            if not hasattr(self, "_last_hosttime_send"):\n                self._last_hosttime_send = 0.0\n            if time.monotonic() - self._last_hosttime_send >= 60.0:\n                try:\n                    now = time.time()\n                    local = time.localtime(now)\n                    utc = time.gmtime(now)\n                    offset_minutes = int((time.mktime(local) - time.mktime(utc)) / 60)\n                    cmd = f"SET HOSTTIME {int(now)} {offset_minutes}"\n                    self.send(cmd)\n                    self._last_hosttime_send = time.monotonic()\n                    print(f"[BloomPetz] HOSTTIME SENT: {cmd}", flush=True)\n                except Exception as exc:\n                    print(f"[BloomPetz] HOSTTIME ERROR: {exc}", flush=True)\n\n'''
s = s.replace(loop_anchor, loop_insert + loop_anchor, 1)

# Mark file in a harmless comment.
s = s.replace("from __future__ import annotations\n", "from __future__ import annotations\n# HOSTTIME ONLY V4\n", 1)

ast.parse(s)
p.write_text(s)
print("REPAIRED Mini host-time send V4")
print("  serial open/reset behavior untouched")
print("  host time sent immediately after live serial assignment")
print("  host time refreshed every 60 seconds")
print("  Python syntax check: PASS")
