#!/usr/bin/env python3
"""Fix Arduino auto-prototype visibility for BloomPetz APA106 RMT helpers.

The RMT screensaver patch originally declared BloomSaverRgb and the LED constants
late in the .ino, after earlier functions. Arduino's sketch preprocessor generates
function prototypes before that late declaration, so prototypes using BloomSaverRgb
fail to compile.

This repair moves only the type/constants to the top-level declaration area directly
after the include block. The proven HAPPY JARZ RMT functions/timing remain unchanged.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_RMT_PROTOTYPE_VISIBILITY_FIX_V1"

DECL = '''// BLOOMPETZ_RMT_PROTOTYPE_VISIBILITY_FIX_V1
// Must remain above Arduino-generated function prototypes.
static constexpr uint8_t BLOOMPETZ_LED_DATA_PIN = 7;
static constexpr uint8_t BLOOMPETZ_LED_COUNT = 2;
static constexpr uint8_t BLOOMPETZ_LED_NORMAL_MAX_PERCENT = 50;
static constexpr uint8_t BLOOMPETZ_SAVER_LED_PERCENT = 25;
struct BloomSaverRgb { uint8_t r, g, b; };

'''

LATE = '''static constexpr uint8_t BLOOMPETZ_LED_DATA_PIN = 7;
static constexpr uint8_t BLOOMPETZ_LED_COUNT = 2;
static constexpr uint8_t BLOOMPETZ_LED_NORMAL_MAX_PERCENT = 50;
static constexpr uint8_t BLOOMPETZ_SAVER_LED_PERCENT = 25;

struct BloomSaverRgb { uint8_t r, g, b; };
'''


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_fix_rmt_prototypes.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("RMT prototype visibility fix already applied.")
        return

    required = [
        "// BLOOMPETZ_SCREENSAVER_RMT_FIX_V1",
        '#include "esp32-hal-rmt.h"',
        "static void bloomSaverWriteFrame(",
        "static BloomSaverRgb bloomSaverRandomColorRmt()",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required RMT patch anchors missing: " + ", ".join(missing))

    if LATE not in s:
        raise SystemExit("Exact late BloomSaverRgb/constants block not found; refusing to guess")

    # Remove the late declaration first so only one definition remains.
    s = s.replace(LATE, "", 1)

    # Put the declarations immediately after the contiguous include block.
    inc = re.search(r"(?:#include[^\n]*\n)+", s)
    if not inc:
        raise SystemExit("Include block not found")
    s = s[:inc.end()] + "\n" + DECL + s[inc.end():]

    # Sanity: exactly one struct and one set of constants should remain.
    if s.count("struct BloomSaverRgb") != 1:
        raise SystemExit("BloomSaverRgb definition count is not 1 after repair")
    if s.count("BLOOMPETZ_LED_COUNT = 2") != 1:
        raise SystemExit("BLOOMPETZ_LED_COUNT definition count is not 1 after repair")

    p.write_text(s)
    print(f"Moved BloomSaverRgb + APA106 constants above Arduino auto-prototypes in {p}")
    print("RMT transport/timing unchanged. Saver=25%; normal ceiling=50%.")


if __name__ == "__main__":
    main()
