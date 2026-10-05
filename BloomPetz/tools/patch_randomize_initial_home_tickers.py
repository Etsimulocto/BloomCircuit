#!/usr/bin/env python3
"""Randomize the initial BloomPetz HOME saying/stat indices at boot.

The prior random ticker patch randomized subsequent picks but left both indices
initialized to zero, so the first visible saying/stat could still always be the
first entries (e.g. Hi friend / attachment).

This patch keeps all timing/marquee logic intact and only seeds the initial
indices immediately after randomSeed().
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_RANDOM_INITIAL_HOME_TICKERS_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_randomize_initial_home_tickers.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Initial HOME ticker randomization already applied.")
        return

    required = [
        "BLOOMPETZ_RANDOM_HOME_TICKERS_V1",
        "randomSeed((uint32_t)esp_random());",
        "petSayingIndex",
        "petSayingCount()",
        "homeNameStatIndex",
        "STAT_COUNT",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required random ticker anchors missing: " + ", ".join(missing))

    anchor = "  randomSeed((uint32_t)esp_random());"
    insert = r'''
  // BLOOMPETZ_RANDOM_INITIAL_HOME_TICKERS_V1
  {
    uint16_t sayingCount = petSayingCount();
    if (sayingCount) petSayingIndex = (uint16_t)random((long)sayingCount);
    homeNameStatIndex = (uint16_t)random((long)STAT_COUNT);
  }'''

    if anchor not in s:
        raise SystemExit("randomSeed anchor not found")
    s = s.replace(anchor, anchor + insert, 1)

    p.write_text(s)
    print(f"Randomized initial HOME ticker indices in {p}")
    print("First saying and first stat now start randomly on every boot.")
    print("Later picks still avoid immediate repeats; timing/marquee unchanged.")


if __name__ == "__main__":
    main()
