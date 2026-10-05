#!/usr/bin/env python3
"""Randomize BloomPetz HOME sayings and HOME stat ticker order.

Behavior:
- seed Arduino random() from ESP32 hardware RNG at boot
- HOME sayings choose a random saying each saying phase
- HOME stats choose a random stat from all 200 each stat phase
- immediate repeats are avoided for both
- existing 10s phase timing and marquee behavior are preserved
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_RANDOM_HOME_TICKERS_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_randomize_home_tickers.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Random HOME tickers already applied.")
        return

    required = [
        "HOME_NAME_STAT_MODE_MS",
        "homeNameStatIndex",
        "petSayingIndex",
        "petSayingCount()",
        "void setup()",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required ticker anchors missing: " + ", ".join(missing))

    # esp_random() is the ESP32 hardware RNG. Add the include once.
    if '#include "esp_random.h"' not in s and '#include <esp_random.h>' not in s:
        inc = re.search(r"(?:#include[^\n]*\n)+", s)
        if not inc:
            raise SystemExit("Could not locate include block")
        s = s[:inc.end()] + '#include "esp_random.h"\n' + s[inc.end():]

    # Generic helper lives early enough to avoid Arduino auto-prototype ordering issues.
    inc = re.search(r"(?:#include[^\n]*\n)+", s)
    if not inc:
        raise SystemExit("Include block missing after esp_random insert")
    helper = r'''

// BLOOMPETZ_RANDOM_HOME_TICKERS_V1
static uint16_t bloomRandomDifferent(uint16_t current, uint16_t count) {
  if (count <= 1U) return 0U;
  uint16_t next = current;
  while (next == current) next = (uint16_t)random((long)count);
  return next;
}
'''
    s = s[:inc.end()] + helper + s[inc.end():]

    # Seed Arduino's PRNG from the ESP32 hardware RNG once during setup.
    setup_anchor = "void setup() {"
    if setup_anchor not in s:
        raise SystemExit("setup() anchor missing")
    s = s.replace(
        setup_anchor,
        setup_anchor + "\n  randomSeed((uint32_t)esp_random());",
        1,
    )

    # HOME stat ticker: replace sequential +1 with random-all-200, no immediate repeat.
    old_stat = "homeNameStatIndex = (uint16_t)((homeNameStatIndex + 1U) % STAT_COUNT);"
    if old_stat in s:
        s = s.replace(
            old_stat,
            "homeNameStatIndex = bloomRandomDifferent(homeNameStatIndex, STAT_COUNT);",
            1,
        )
    elif "homeNameStatIndex = bloomRandomDifferent(homeNameStatIndex, STAT_COUNT);" not in s:
        raise SystemExit("Could not find sequential HOME stat advance")

    # Saying ticker: random was already used, but prevent immediate repeats explicitly.
    old_saying = "if (count) petSayingIndex = (uint16_t)random(count);"
    if old_saying in s:
        s = s.replace(
            old_saying,
            "if (count) petSayingIndex = bloomRandomDifferent(petSayingIndex, count);",
            1,
        )
    elif "petSayingIndex = bloomRandomDifferent(petSayingIndex, count);" not in s:
        # tolerate expanded brace formatting from future local patches
        pat = re.compile(r"if\s*\(count\)\s*petSayingIndex\s*=\s*\(uint16_t\)random\(count\)\s*;")
        if not pat.search(s):
            raise SystemExit("Could not find HOME saying random selection")
        s = pat.sub("if (count) petSayingIndex = bloomRandomDifferent(petSayingIndex, count);", s, count=1)

    p.write_text(s)
    print(f"Randomized HOME tickers in {p}")
    print("Sayings and stats now use hardware-seeded random order with no immediate repeats.")
    print("Existing phase timing and marquee behavior are unchanged.")


if __name__ == "__main__":
    main()
