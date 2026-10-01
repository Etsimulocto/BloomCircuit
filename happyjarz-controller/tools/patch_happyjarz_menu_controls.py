#!/usr/bin/env python3
"""Restore known-good HAPPY JARZ local controls while retaining OLED menus.

HOME preserves the original proven control map exactly:
  A     -> next Light 1 palette color
  B     -> next Light 2 palette color
  UP    -> next light pattern
  DOWN  -> previous light pattern

RIGHT, previously unused by the JAR light-control layer, opens the OLED menu.
Inside the menu only, UP/DOWN/A/B become navigation controls. B returns HOME.
LEFT remains available for future use and does not steal a proven light action.

After restoring the menu controls, apply the LED recovery patch so USB wobble/
reconnects do not flash diagnostic blue/green and desktop light commands always
return the local UI to HOME.
"""

from pathlib import Path
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_menu_controls.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

old = '''  if (inputMode == "JAR") {
    if (uiScreen == UI_HOME) {
      if (q[IN_A] && !latched[IN_A]) { uiOpenMainMenu(); }
      else {
        if (q[IN_B] && !latched[IN_B]) { paletteIndex2=(paletteIndex2+1)%9; Rgb c=palette[paletteIndex2]; hjSetLed(2,c.r,c.g,c.b); oledDirty=true; }
        if (q[IN_UP] && !latched[IN_UP]) { localPatternIndex=(localPatternIndex+1)%6; hjSetPattern(patterns[localPatternIndex]); oledDirty=true; }
        if (q[IN_DOWN] && !latched[IN_DOWN]) { localPatternIndex=(localPatternIndex+5)%6; hjSetPattern(patterns[localPatternIndex]); oledDirty=true; }
        if (q[IN_LEFT] && !latched[IN_LEFT]) { paletteIndex1=(paletteIndex1+8)%9; Rgb c=palette[paletteIndex1]; hjSetLed(1,c.r,c.g,c.b); oledDirty=true; }
        if (q[IN_RIGHT] && !latched[IN_RIGHT]) { paletteIndex1=(paletteIndex1+1)%9; Rgb c=palette[paletteIndex1]; hjSetLed(1,c.r,c.g,c.b); oledDirty=true; }
      }
    } else if (uiScreen == UI_MAIN_MENU) {
      if (q[IN_UP] && !latched[IN_UP]) { uiCursor=(uiCursor+4)%5; oledDirty=true; }
      if (q[IN_DOWN] && !latched[IN_DOWN]) { uiCursor=(uiCursor+1)%5; oledDirty=true; }
      if (q[IN_A] && !latched[IN_A]) { uiSelectMain(); }
      if (q[IN_B] && !latched[IN_B]) { uiGoHome(); }
    } else {
      if (q[IN_B] && !latched[IN_B]) { uiOpenMainMenu(); }
      if (q[IN_A] && !latched[IN_A] && uiScreen == UI_LIGHTS) { uiGoHome(); }
    }
  }
'''

new = '''  if (inputMode == "JAR") {
    if (uiScreen == UI_HOME) {
      // Preserve the original known-good local controls exactly.
      if (q[IN_A] && !latched[IN_A]) { paletteIndex1=(paletteIndex1+1)%9; Rgb c=palette[paletteIndex1]; hjSetLed(1,c.r,c.g,c.b); oledDirty=true; }
      if (q[IN_B] && !latched[IN_B]) { paletteIndex2=(paletteIndex2+1)%9; Rgb c=palette[paletteIndex2]; hjSetLed(2,c.r,c.g,c.b); oledDirty=true; }
      if (q[IN_UP] && !latched[IN_UP]) { localPatternIndex=(localPatternIndex+1)%6; hjSetPattern(patterns[localPatternIndex]); oledDirty=true; }
      if (q[IN_DOWN] && !latched[IN_DOWN]) { localPatternIndex=(localPatternIndex+5)%6; hjSetPattern(patterns[localPatternIndex]); oledDirty=true; }

      // RIGHT was unused in the original light-control layer, so it owns MENU.
      if (q[IN_RIGHT] && !latched[IN_RIGHT]) { uiOpenMainMenu(); }
    } else if (uiScreen == UI_MAIN_MENU) {
      if (q[IN_UP] && !latched[IN_UP]) { uiCursor=(uiCursor+4)%5; oledDirty=true; }
      if (q[IN_DOWN] && !latched[IN_DOWN]) { uiCursor=(uiCursor+1)%5; oledDirty=true; }
      if (q[IN_A] && !latched[IN_A]) { uiSelectMain(); }
      if (q[IN_B] && !latched[IN_B]) { uiGoHome(); }
    } else {
      // Detail/status pages are view-only for now. B backs to main menu.
      if (q[IN_B] && !latched[IN_B]) { uiOpenMainMenu(); }
    }
  }
'''

if old not in s:
    raise SystemExit("menu control restore failed: expected OLED menu input block not found")

s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

recovery = Path(__file__).with_name("patch_happyjarz_led_recovery.py")
if not recovery.exists():
    raise SystemExit(f"menu control restore failed: missing LED recovery patch: {recovery}")
subprocess.run([sys.executable, str(recovery), str(p)], check=True)
