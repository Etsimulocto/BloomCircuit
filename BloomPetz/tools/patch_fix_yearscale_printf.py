#!/usr/bin/env python3
"""Repair the broken BP|ACTION Serial.printf string introduced by year-scale growth patch."""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_YEAR_SCALE_PRINTF_FIX_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_fix_yearscale_printf.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Year-scale printf repair already applied.")
        return

    broken = '''  Serial.printf("BP|ACTION|name=%s|response_ms=%lu|gain_pct=%.4f|rewarded=%u|energy=%.1f
", ACTION_NAMES[selectedAction], (unsigned long)responseMs, gain * 100.0f, firstRewardToday?1:0, p.foodEnergy);'''

    fixed = '''  // BLOOMPETZ_YEAR_SCALE_PRINTF_FIX_V1
  Serial.printf("BP|ACTION|name=%s|response_ms=%lu|gain_pct=%.4f|rewarded=%u|energy=%.1f\\n", ACTION_NAMES[selectedAction], (unsigned long)responseMs, gain * 100.0f, firstRewardToday?1:0, p.foodEnergy);'''

    if broken not in s:
        raise SystemExit("Broken BP|ACTION printf pattern not found; refusing to guess")

    s = s.replace(broken, fixed, 1)
    p.write_text(s)
    print(f"Fixed broken BP|ACTION printf newline in {p}")
    print("Year-scale stat math unchanged; only the C++ string literal was repaired.")


if __name__ == "__main__":
    main()
