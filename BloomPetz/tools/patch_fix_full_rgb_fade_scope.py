#!/usr/bin/env python3
"""Fix BloomPetz full-RGB screensaver fade variable declaration order.

The full-RGB fade patch resets bloomSaverFadePrimed inside bloomSaverLightsOff(),
but originally declared bloomSaverFadePrimed later in the sketch. Move that one
state variable above bloomSaverLightsOff() so C++ can see it. No behavior changes.
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_FULL_RGB_FADE_SCOPE_FIX_V1"
DECL = "static bool bloomSaverFadePrimed = false;"
OFF = "static void bloomSaverLightsOff()"
FADE_MARKER = "// BLOOMPETZ_SCREENSAVER_FULL_RGB_FADE_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_fix_full_rgb_fade_scope.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Full-RGB fade scope fix already applied.")
        return
    if FADE_MARKER not in s:
        raise SystemExit("Full-RGB screensaver fade patch not found")
    if OFF not in s:
        raise SystemExit("bloomSaverLightsOff() not found")
    if s.count(DECL) != 1:
        raise SystemExit(f"Expected exactly one fade primed declaration, found {s.count(DECL)}")

    off_pos = s.find(OFF)
    decl_pos = s.find(DECL)
    if decl_pos < off_pos:
        print("bloomSaverFadePrimed is already visible before bloomSaverLightsOff().")
        return

    # Remove the later declaration, then place it immediately before lightsOff().
    s = s[:decl_pos] + s[decl_pos + len(DECL):]
    off_pos = s.find(OFF)
    insert = MARKER + "\n" + DECL + "\n"
    s = s[:off_pos] + insert + s[off_pos:]

    p.write_text(s)
    print(f"Moved bloomSaverFadePrimed above bloomSaverLightsOff() in {p}")
    print("No fade timing, RGB behavior, brightness, or RMT transport changed.")


if __name__ == "__main__":
    main()
