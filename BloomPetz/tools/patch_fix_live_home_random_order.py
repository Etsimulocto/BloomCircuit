#!/usr/bin/env python3
"""Fix the ACTUAL live BloomPetz HOME ticker engine to use random order.

Targets the user's current local .ino, where:
- PET_SAYINGS starts at index 0 ("hi friend")
- advancePetSayingIfDue() still increments petSayingIndex sequentially
- HOME stat ticker still increments homeNameStatIndex sequentially

Behavior after patch:
- hardware-seeded Arduino PRNG (if not already present)
- first saying/stat indices randomized during setup
- every later saying/stat pick is randomized
- immediate repeats avoided
- existing 10s timing and marquee behavior preserved
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_LIVE_HOME_RANDOM_ORDER_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_fix_live_home_random_order.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Live HOME random-order fix already applied.")
        return

    required = [
        'static const char* const PET_SAYINGS[]',
        'static uint16_t petSayingIndex = 0;',
        'static uint16_t homeNameStatIndex = 0;',
        'PET_SAYING_COUNT',
        'STAT_COUNT',
        'void setup() {',
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required live ticker anchors missing: " + ", ".join(missing))

    # Ensure hardware RNG include exists.
    if '#include "esp_random.h"' not in s and '#include <esp_random.h>' not in s:
        inc = re.search(r"(?:#include[^\n]*\n)+", s)
        if not inc:
            raise SystemExit("Could not locate include block")
        s = s[:inc.end()] + '#include "esp_random.h"\n' + s[inc.end():]

    # Ensure helper exists. Put it after includes so Arduino's auto-prototypes cannot hide it.
    if 'static uint16_t bloomRandomDifferent(' not in s:
        inc = re.search(r"(?:#include[^\n]*\n)+", s)
        if not inc:
            raise SystemExit("Could not relocate include block")
        helper = r'''

// BLOOMPETZ_LIVE_HOME_RANDOM_ORDER_V1
static uint16_t bloomRandomDifferent(uint16_t current, uint16_t count) {
  if (count <= 1U) return 0U;
  uint16_t next = current;
  while (next == current) next = (uint16_t)random((long)count);
  return next;
}
'''
        s = s[:inc.end()] + helper + s[inc.end():]
    else:
        # Existing helper came from an earlier patch; still stamp this exact-live marker.
        inc = re.search(r"(?:#include[^\n]*\n)+", s)
        if not inc:
            raise SystemExit("Include block missing")
        s = s[:inc.end()] + "\n" + MARKER + "\n" + s[inc.end():]

    # Fix the actual live saying engine seen in the user's grep.
    old_saying = 'petSayingIndex = (uint16_t)((petSayingIndex + 1U) % PET_SAYING_COUNT);'
    new_saying = 'petSayingIndex = bloomRandomDifferent(petSayingIndex, PET_SAYING_COUNT);'
    if old_saying in s:
        s = s.replace(old_saying, new_saying, 1)
    elif new_saying not in s:
        raise SystemExit("Could not find live sequential petSayingIndex advance")

    # Fix the actual live stat engine seen in the user's grep.
    old_stat = 'homeNameStatIndex = (uint16_t)((homeNameStatIndex + 1U) % STAT_COUNT);'
    new_stat = 'homeNameStatIndex = bloomRandomDifferent(homeNameStatIndex, STAT_COUNT);'
    if old_stat in s:
        s = s.replace(old_stat, new_stat, 1)
    elif new_stat not in s:
        raise SystemExit("Could not find live sequential homeNameStatIndex advance")

    # Seed PRNG if an earlier patch did not already do so.
    setup_anchor = 'void setup() {'
    setup_pos = s.find(setup_anchor)
    if setup_pos < 0:
        raise SystemExit("setup() not found")

    # Inspect a reasonable chunk of setup for an existing randomSeed.
    setup_chunk = s[setup_pos:setup_pos + 2500]
    if 'randomSeed(' not in setup_chunk:
        s = s.replace(setup_anchor, setup_anchor + '\n  randomSeed((uint32_t)esp_random());', 1)

    # Randomize the INITIAL indices after the seed, before HOME can ever render.
    # Make this idempotent with a dedicated initializer marker.
    init_marker = '// BLOOMPETZ_RANDOM_INITIAL_HOME_INDICES_V1'
    if init_marker not in s:
        setup_pos = s.find(setup_anchor)
        setup_chunk_end = min(len(s), setup_pos + 3000)
        setup_chunk = s[setup_pos:setup_chunk_end]
        m = re.search(r'\n\s*randomSeed\([^;]+\);', setup_chunk)
        if not m:
            raise SystemExit("randomSeed() not found in setup after insertion")
        absolute_end = setup_pos + m.end()
        init = (
            '\n  ' + init_marker +
            '\n  petSayingIndex = (PET_SAYING_COUNT > 0) ? (uint16_t)random((long)PET_SAYING_COUNT) : 0;'
            '\n  homeNameStatIndex = (STAT_COUNT > 0) ? (uint16_t)random((long)STAT_COUNT) : 0;'
        )
        s = s[:absolute_end] + init + s[absolute_end:]

    # Validate the two sequential forms are gone.
    if old_saying in s or old_stat in s:
        raise SystemExit("Sequential live ticker advance still present after patch")

    p.write_text(s)
    print(f"Fixed ACTUAL live HOME ticker order in {p}")
    print("First saying/stat are randomized at boot; later picks are random with no immediate repeats.")
    print("Existing 10s timing and marquee behavior are unchanged.")


if __name__ == '__main__':
    main()
