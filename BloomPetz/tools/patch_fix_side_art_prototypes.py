#!/usr/bin/env python3
"""Fix Arduino auto-prototype ordering for BloomPetz side-scroll art.

Run after patch_side_scroll_art.py has already been applied to the local sketch.
Arduino's sketch preprocessor may auto-generate function prototypes before the
SideParticle struct, causing `SideParticle was not declared in this scope`.
This inserts explicit prototypes immediately after the struct definition so the
preprocessor leaves them in the correct place.
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_SIDE_SCROLL_ART_PROTOTYPES_FIX_V1"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_fix_side_art_prototypes.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Side-art prototype fix already applied.")
        return

    if "// BLOOMPETZ_SIDE_SCROLL_ART_V1" not in s:
        raise SystemExit("Side-scroll art patch not found. Apply patch_side_scroll_art.py first.")

    anchor = '''struct SideParticle {
  int8_t x;
  int8_t y;
  uint8_t speed;
  uint8_t shape;
};
'''

    if anchor not in s:
        raise SystemExit("SideParticle struct anchor not found; refusing to guess.")

    fixed = anchor + '''
// BLOOMPETZ_SIDE_SCROLL_ART_PROTOTYPES_FIX_V1
// Explicit prototypes prevent Arduino from auto-generating these above the
// SideParticle type declaration.
static void randomizeSideParticle(SideParticle &p, bool rightSide, bool startAnywhere);
static void initSideArt();
static void stepSideArt();
static void drawOneSideParticle(const SideParticle &p);
static void drawSideArt();
'''

    s = s.replace(anchor, fixed, 1)
    p.write_text(s)
    print(f"Side-art prototype fix applied to {p}")
    print("Recompile now; no need to re-run the original side-art patch.")


if __name__ == "__main__":
    main()
