#!/usr/bin/env python3
"""Move BloomPetz LED shared types/counts into a header so Arduino auto-prototypes see them.

This fixes Arduino .ino preprocessing errors where generated prototypes reference
Rgb/BloomSaverRgb and their array bounds before those symbols are visible.

Behavioral code is untouched: ticker randomization, LED animation, brightness and RMT
transport remain unchanged.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_LED_TYPES_HEADER_FIX_V1"
HEADER_NAME = "bloompetz_led_types.h"


def find_one(text, pattern, label):
    matches = list(re.finditer(pattern, text, re.M))
    if not matches:
        raise SystemExit(f"Could not locate {label}")
    # Use the first live declaration; later duplicates, if any, are removed below too.
    return matches[0].group(0).strip()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_led_types_to_header.py <bloompetz_v0_1.ino>")

    ino = Path(sys.argv[1]).expanduser().resolve()
    s = ino.read_text()

    if MARKER in s:
        print("LED header visibility fix already applied.")
        return

    rgb_line = find_one(s, r"^\s*struct\s+Rgb\s*\{[^\n]*\};\s*$", "struct Rgb")
    led_count_line = find_one(s, r"^\s*static\s+constexpr\s+uint8_t\s+LED_COUNT\s*=\s*[^;]+;\s*$", "LED_COUNT")
    saver_rgb_line = find_one(s, r"^\s*struct\s+BloomSaverRgb\s*\{[^\n]*\};\s*$", "struct BloomSaverRgb")
    saver_count_line = find_one(s, r"^\s*static\s+constexpr\s+uint8_t\s+BLOOMPETZ_LED_COUNT\s*=\s*[^;]+;\s*$", "BLOOMPETZ_LED_COUNT")

    # Remove every in-sketch declaration of these four symbols so the header is authoritative.
    patterns = [
        r"^\s*struct\s+Rgb\s*\{[^\n]*\};\s*\n?",
        r"^\s*static\s+constexpr\s+uint8_t\s+LED_COUNT\s*=\s*[^;]+;\s*\n?",
        r"^\s*struct\s+BloomSaverRgb\s*\{[^\n]*\};\s*\n?",
        r"^\s*static\s+constexpr\s+uint8_t\s+BLOOMPETZ_LED_COUNT\s*=\s*[^;]+;\s*\n?",
    ]
    for pat in patterns:
        s = re.sub(pat, "", s, flags=re.M)

    # Create/update a sibling header. Since it is included before Arduino-generated
    # prototypes, custom parameter types and array bounds are visible in time.
    header = ino.parent / HEADER_NAME
    header_text = f'''#pragma once
#include <Arduino.h>

// Shared LED declarations required before Arduino auto-generated prototypes.
{rgb_line}
{led_count_line}
{saver_rgb_line}
{saver_count_line}
'''
    header.write_text(header_text)

    include_line = f'#include "{HEADER_NAME}"'
    if include_line not in s:
        # Insert immediately after the existing include block.
        incs = list(re.finditer(r"^#include[^\n]*$", s, re.M))
        if not incs:
            raise SystemExit("Could not locate include block")
        pos = incs[-1].end()
        s = s[:pos] + "\n" + include_line + s[pos:]

    # Put the marker right after the header include so reruns are harmless.
    if MARKER not in s:
        s = s.replace(include_line, include_line + "\n" + MARKER, 1)

    ino.write_text(s)

    print(f"Moved LED shared types/counts into {header}")
    print("Arduino auto-generated prototypes will now see Rgb/BloomSaverRgb and both LED counts.")
    print("No ticker, fade, brightness, or RMT behavior was changed.")


if __name__ == "__main__":
    main()
