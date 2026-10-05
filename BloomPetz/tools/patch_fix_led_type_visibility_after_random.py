#!/usr/bin/env python3
"""Repair C++ declaration ordering for BloomPetz LED helpers after ticker patching.

Moves the LED type/count declarations ahead of the functions that use them.
This is intentionally structural only: no ticker, fade, brightness, or RMT behavior changes.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_LED_TYPE_VISIBILITY_REPAIR_V2"


def extract_line(s: str, pattern: str, label: str):
    m = re.search(pattern, s, re.M)
    if not m:
        raise SystemExit(f"Could not locate {label}")
    return m.group(0), m.start(), m.end()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_fix_led_type_visibility_after_random.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()
    if MARKER in s:
        print("LED type visibility repair already applied.")
        return

    # ---------- Main HAPPY JARZ LED transport ----------
    fn1 = s.find("static void writeApa106(")
    if fn1 < 0:
        raise SystemExit("writeApa106() not found")

    # Capture the existing declarations wherever they currently live.
    rgb_m = re.search(r"^\s*struct\s+Rgb\s*\{[^\n]*\};\s*$", s, re.M)
    led_m = re.search(r"^\s*static\s+constexpr\s+uint8_t\s+LED_COUNT\s*=\s*[^;]+;\s*$", s, re.M)
    if not rgb_m:
        raise SystemExit("struct Rgb declaration not found")
    if not led_m:
        raise SystemExit("LED_COUNT declaration not found")

    rgb_line = rgb_m.group(0).strip()
    led_line = led_m.group(0).strip()

    # Remove both originals, then recompute anchor and place them before writeApa106().
    spans = sorted([(rgb_m.start(), rgb_m.end()), (led_m.start(), led_m.end())], reverse=True)
    for a, b in spans:
        s = s[:a] + s[b:]
    fn1 = s.find("static void writeApa106(")
    block1 = f"\n{MARKER}\n{rgb_line}\n{led_line}\n"
    s = s[:fn1] + block1 + s[fn1:]

    # ---------- BloomPetz screensaver RMT layer ----------
    fn2 = s.find("static void bloomSaverWriteFrame(")
    if fn2 < 0:
        raise SystemExit("bloomSaverWriteFrame() not found")

    bs_rgb = re.search(r"^\s*struct\s+BloomSaverRgb\s*\{[^\n]*\};\s*$", s, re.M)
    bs_count = re.search(r"^\s*static\s+constexpr\s+uint8_t\s+BLOOMPETZ_LED_COUNT\s*=\s*[^;]+;\s*$", s, re.M)
    if not bs_rgb:
        raise SystemExit("struct BloomSaverRgb declaration not found")
    if not bs_count:
        raise SystemExit("BLOOMPETZ_LED_COUNT declaration not found")

    bs_rgb_line = bs_rgb.group(0).strip()
    bs_count_line = bs_count.group(0).strip()

    # Preserve related pin/brightness constants where they are; only type + array bound
    # must be visible before this function signature.
    spans = sorted([(bs_rgb.start(), bs_rgb.end()), (bs_count.start(), bs_count.end())], reverse=True)
    for a, b in spans:
        s = s[:a] + s[b:]
    fn2 = s.find("static void bloomSaverWriteFrame(")
    block2 = f"\n{bs_rgb_line}\n{bs_count_line}\n"
    s = s[:fn2] + block2 + s[fn2:]

    p.write_text(s)
    print(f"Repaired LED type visibility in {p}")
    print("Rgb/LED_COUNT now precede writeApa106().")
    print("BloomSaverRgb/BLOOMPETZ_LED_COUNT now precede bloomSaverWriteFrame().")
    print("Ticker randomization, fade behavior, brightness caps, and RMT timing were not changed.")


if __name__ == "__main__":
    main()
