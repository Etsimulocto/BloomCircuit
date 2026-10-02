#!/usr/bin/env python3
"""Inject the release firmware version from firmware/VERSION into a staged sketch."""

from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_release_version.py <staged .ino>")

sketch = Path(sys.argv[1])
controller_dir = Path(__file__).resolve().parent.parent
version_file = controller_dir / "firmware" / "VERSION"
version = version_file.read_text(encoding="utf-8").strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    raise SystemExit(f"invalid firmware VERSION: {version!r}")

s = sketch.read_text(encoding="utf-8")
pattern = r'static const char \*HJ_FW_VERSION = "[^"]+";'
replacement = f'static const char *HJ_FW_VERSION = "{version}";'
s, count = re.subn(pattern, replacement, s, count=1)
if count != 1:
    raise SystemExit("release version patch failed: HJ_FW_VERSION marker not found")

sketch.write_text(s, encoding="utf-8")
print(f"Applied HAPPY JARZ firmware release version {version}.")
