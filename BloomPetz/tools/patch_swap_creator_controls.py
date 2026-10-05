#!/usr/bin/env python3
"""Swap BloomPetz creator controls to a more natural layout.

Result:
- UP/DOWN = move between Name / Type / Design / Save
- A/B = cycle printable ASCII character
- LEFT = move back/delete one character
- RIGHT = accept current character / move forward
- RIGHT on SAVE = commit pet
- LEFT on SAVE = return to Design

Safe to run after patch_ascii_pet_creator.py.
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_CREATOR_CONTROLS_AB_ASCII_V1"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_swap_creator_controls.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Creator controls already swapped.")
        return

    old = '''  if (creatorRow == 3) {
    if (in == AKEY) commitCreator();
    else if (in == BKEY) { creatorRow = 2; drawCreator(); }
    return;
  }

  if (in == LEFT) {
    creatorChar = (creatorChar <= 32) ? 126 : (char)(creatorChar - 1);
    drawCreator();
    return;
  }
  if (in == RIGHT) {
    creatorChar = (creatorChar >= 126) ? 32 : (char)(creatorChar + 1);
    drawCreator();
    return;
  }
  if (in == AKEY) {
    String &field = creatorField(creatorRow);
    if (field.length() < creatorMaxLen(creatorRow)) field += creatorChar;
    drawCreator();
    return;
  }
  if (in == BKEY) {
    String &field = creatorField(creatorRow);
    if (field.length()) field.remove(field.length() - 1);
    drawCreator();
    return;
  }
'''

    new = '''  // BLOOMPETZ_CREATOR_CONTROLS_AB_ASCII_V1
  if (creatorRow == 3) {
    if (in == RIGHT) commitCreator();
    else if (in == LEFT) { creatorRow = 2; drawCreator(); }
    return;
  }

  // A/B change the selected printable ASCII character.
  if (in == BKEY) {
    creatorChar = (creatorChar <= 32) ? 126 : (char)(creatorChar - 1);
    drawCreator();
    return;
  }
  if (in == AKEY) {
    creatorChar = (creatorChar >= 126) ? 32 : (char)(creatorChar + 1);
    drawCreator();
    return;
  }

  // LEFT/RIGHT move through the text: back/delete vs accept/advance.
  if (in == LEFT) {
    String &field = creatorField(creatorRow);
    if (field.length()) field.remove(field.length() - 1);
    drawCreator();
    return;
  }
  if (in == RIGHT) {
    String &field = creatorField(creatorRow);
    if (field.length() < creatorMaxLen(creatorRow)) field += creatorChar;
    drawCreator();
    return;
  }
'''

    if old not in s:
        raise SystemExit("Expected ASCII creator control block not found. Apply patch_ascii_pet_creator.py first.")

    s = s.replace(old, new, 1)

    # Update save hint if present.
    s = s.replace('String saveLine = creatorRow == 3 ? ">SAVE A=YES" : " SAVE";',
                  'String saveLine = creatorRow == 3 ? ">SAVE R=YES" : " SAVE";', 1)

    p.write_text(s)
    print(f"Creator controls swapped in {p}")
    print("UP/DOWN rows | A/B ASCII | LEFT delete/back | RIGHT accept/save")


if __name__ == "__main__":
    main()
