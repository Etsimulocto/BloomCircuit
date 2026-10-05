#!/usr/bin/env python3
"""Force BloomPetz LED shared-type header to the very first line of the sketch.

Repairs the prior header patch, which could insert after the last #include anywhere
in a heavily patched .ino instead of the top include block.

Behavioral firmware is untouched. This only fixes compile-time visibility of:
- Rgb
- LED_COUNT
- BloomSaverRgb
- BLOOMPETZ_LED_COUNT
"""
from pathlib import Path
import re
import sys

HEADER_NAME = "bloompetz_led_types.h"
INCLUDE = f'#include "{HEADER_NAME}"'
MARKER = "// BLOOMPETZ_FORCE_LED_HEADER_FIRST_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_force_led_header_first.py <bloompetz_v0_1.ino>")

    ino = Path(sys.argv[1]).expanduser().resolve()
    header = ino.parent / HEADER_NAME
    if not header.exists():
        raise SystemExit(f"Missing header: {header}")

    h = header.read_text()
    required = ["struct Rgb", "LED_COUNT", "struct BloomSaverRgb", "BLOOMPETZ_LED_COUNT"]
    missing = [x for x in required if x not in h]
    if missing:
        raise SystemExit("Header missing required declarations: " + ", ".join(missing))

    s = ino.read_text()

    # Remove every previous copy of this include/marker, wherever prior patches put it.
    s = re.sub(r'^\s*#include\s+"bloompetz_led_types\.h"\s*\n?', '', s, flags=re.M)
    s = re.sub(r'^\s*// BLOOMPETZ_(?:LED_TYPES_HEADER_FIX_V1|FORCE_LED_HEADER_FIRST_V1)\s*\n?', '', s, flags=re.M)

    # Byte-zero placement. Arduino and the C++ compiler both see these declarations
    # before any generated/user function prototype or LED global can reference them.
    s = INCLUDE + "\n" + MARKER + "\n" + s.lstrip('\n')
    ino.write_text(s)

    print(f"Forced {HEADER_NAME} to line 1 of {ino}")
    print("Verified header contains Rgb, LED_COUNT, BloomSaverRgb, and BLOOMPETZ_LED_COUNT.")
    print("No runtime behavior was changed.")


if __name__ == "__main__":
    main()
