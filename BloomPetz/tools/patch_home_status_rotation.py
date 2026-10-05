#!/usr/bin/env python3
"""Move BloomPetz energy off the name row and rotate compact live stats in the bottom row.

Applies to the locally patched working sketch.
- Name row becomes pet name only.
- Bottom row rotates every ~1500 ms through:
    E###  = current energy
    T#/3  = treats used today
    A#/8  = daily actions completed
- Keeps A/B instructions on the same line.
"""
from pathlib import Path
import sys
import re

MARKER = "// BLOOMPETZ_HOME_STATUS_ROTATION_V1"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_home_status_rotation.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Home status rotation already applied.")
        return

    # Insert helper state/functions immediately before drawHome().
    anchor = "static void drawHome() {"
    if anchor not in s:
        raise SystemExit("drawHome() anchor not found")

    block = r'''
// BLOOMPETZ_HOME_STATUS_ROTATION_V1
static uint8_t homeStatusPhase = 0;
static unsigned long lastHomeStatusMs = 0;

static uint8_t dailyActionCount(const PetSave &p) {
  uint8_t n = 0;
  for (uint8_t i=0; i<ACTION_COUNT; ++i) {
    if (p.dailyActionMask & (1U << i)) ++n;
  }
  return n;
}

static String homeStatusToken(const PetSave &p) {
  if (homeStatusPhase == 0) return String("E") + String((int)p.foodEnergy);
  if (homeStatusPhase == 1) return String("T") + String(p.treatsToday) + "/3";
  return String("A") + String(dailyActionCount(p)) + "/8";
}

static String homeBottomLine(const PetSave &p) {
  return String("A DO ") + homeStatusToken(p) + " B MENU";
}

'''
    s = s.replace(anchor, block + anchor, 1)

    # Replace the old drawHome occupied-body ending in a targeted way.
    old = '''  String marker = actionDone(p,selectedAction) ? "*" : ">";
  String line3 = marker + String(ACTION_NAMES[selectedAction]);
  String line4 = actionDone(p,selectedAction) ? "A AGAIN B MENU" : "A DO    B MENU";
  renderDisplay(p.art, String(p.name)+" E"+String((int)p.foodEnergy), line3, line4);
'''
    new = '''  String marker = actionDone(p,selectedAction) ? "*" : ">";
  String line3 = marker + String(ACTION_NAMES[selectedAction]);
  renderDisplay(p.art, String(p.name), line3, homeBottomLine(p));
'''
    if old in s:
        s = s.replace(old, new, 1)
    else:
        # Be tolerant of minor spacing changes in the user's locally patched sketch.
        pat = re.compile(
            r'  String marker = actionDone\(p,selectedAction\) \? "\\\*" : ">";\n'
            r'  String line3 = marker \+ String\(ACTION_NAMES\[selectedAction\]\);\n'
            r'  String line4 = .*?;\n'
            r'  renderDisplay\(p\.art, String\(p\.name\)\+" E"\+String\(\(int\)p\.foodEnergy\), line3, line4\);\n',
            re.S,
        )
        m = pat.search(s)
        if not m:
            raise SystemExit("Expected drawHome energy/name block not found")
        s = s[:m.start()] + new + s[m.end():]

    # Add a lightweight HOME-only rotation in loop(). Prefer to place it after serviceSerial().
    loop_anchor = "void loop() {\n  serviceSerial();"
    if loop_anchor not in s:
        raise SystemExit("loop/serviceSerial anchor not found")

    loop_new = '''void loop() {
  serviceSerial();
  if (uiMode == HOME && pets[activeSlot].occupied && millis() - lastHomeStatusMs >= 1500) {
    lastHomeStatusMs = millis();
    homeStatusPhase = (homeStatusPhase + 1) % 3;
    drawHome();
  }'''
    s = s.replace(loop_anchor, loop_new, 1)

    p.write_text(s)
    print(f"Home status rotation applied to {p}")
    print("Name row is clean; bottom row rotates E### / T#/3 / A#/8 every ~1.5s.")


if __name__ == "__main__":
    main()
