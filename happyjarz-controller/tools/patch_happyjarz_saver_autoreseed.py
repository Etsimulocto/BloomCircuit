#!/usr/bin/env python3
"""Auto-reseed procedural HAPPY JARZ art savers whenever they are selected.

Runs after patch_happyjarz_saver_controls.py.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_saver_autoreseed.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

needle = '  hjScreensaverMode = (uint8_t)((hjScreensaverMode + 1U) % HJ_SCREENSAVER_COUNT);\n'
replacement = needle + '  if (hjScreensaverMode == 1) hjReseedSpiral(); else if (hjScreensaverMode == 2) hjReseedTrippy();\n'
if needle not in s:
    raise SystemExit("saver autoreseed patch failed: next-mode line not found")
s = s.replace(needle, replacement, 1)

needle = '  hjScreensaverMode = (uint8_t)((hjScreensaverMode + HJ_SCREENSAVER_COUNT - 1U) % HJ_SCREENSAVER_COUNT);\n'
replacement = needle + '  if (hjScreensaverMode == 1) hjReseedSpiral(); else if (hjScreensaverMode == 2) hjReseedTrippy();\n'
if needle not in s:
    raise SystemExit("saver autoreseed patch failed: previous-mode line not found")
s = s.replace(needle, replacement, 1)

p.write_text(s, encoding="utf-8")
