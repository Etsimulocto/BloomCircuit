#!/usr/bin/env python3
"""Keep OLED browsing completely isolated from proven HAPPY JARZ light controls.

The four original JAR controls are unconditional everywhere:
  A     -> next Light 1 palette color
  B     -> next Light 2 palette color
  UP    -> next light pattern
  DOWN  -> previous light pattern

OLED navigation uses only the previously-unused directional pair:
  RIGHT -> next OLED screen/menu page
  LEFT  -> previous OLED screen/menu page

No OLED/menu state is allowed to capture A/B/UP/DOWN.
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

new = '''  if (inputMode == "JAR") {
    // ORIGINAL LIGHT CONTROLS: always active, regardless of OLED page.
    if (q[IN_A] && !latched[IN_A]) { paletteIndex1=(paletteIndex1+1)%9; Rgb c=palette[paletteIndex1]; hjSetLed(1,c.r,c.g,c.b); oledDirty=true; }
    if (q[IN_B] && !latched[IN_B]) { paletteIndex2=(paletteIndex2+1)%9; Rgb c=palette[paletteIndex2]; hjSetLed(2,c.r,c.g,c.b); oledDirty=true; }
    if (q[IN_UP] && !latched[IN_UP]) { localPatternIndex=(localPatternIndex+1)%6; hjSetPattern(patterns[localPatternIndex]); oledDirty=true; }
    if (q[IN_DOWN] && !latched[IN_DOWN]) { localPatternIndex=(localPatternIndex+5)%6; hjSetPattern(patterns[localPatternIndex]); oledDirty=true; }

    // OLED browsing is isolated to LEFT/RIGHT only. Cycle through HOME plus the
    // five useful status/detail screens; never steal A/B/UP/DOWN.
    if (q[IN_RIGHT] && !latched[IN_RIGHT]) {
      switch (uiScreen) {
        case UI_HOME: uiScreen=UI_CLOCK; break;
        case UI_CLOCK: uiScreen=UI_LIGHTS; break;
        case UI_LIGHTS: uiScreen=UI_GAMES; break;
        case UI_GAMES: uiScreen=UI_SETTINGS; break;
        case UI_SETTINGS: uiScreen=UI_SYSTEM; break;
        default: uiScreen=UI_HOME; break;
      }
      uiCursor=0; uiScroll=0; oledDirty=true;
    }
    if (q[IN_LEFT] && !latched[IN_LEFT]) {
      switch (uiScreen) {
        case UI_HOME: uiScreen=UI_SYSTEM; break;
        case UI_SYSTEM: uiScreen=UI_SETTINGS; break;
        case UI_SETTINGS: uiScreen=UI_GAMES; break;
        case UI_GAMES: uiScreen=UI_LIGHTS; break;
        case UI_LIGHTS: uiScreen=UI_CLOCK; break;
        default: uiScreen=UI_HOME; break;
      }
      uiCursor=0; uiScroll=0; oledDirty=true;
    }
  }
'''

if old not in s:
    raise SystemExit("menu isolation patch failed: expected restored menu input block not found")

s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

recovery = Path(__file__).with_name("patch_happyjarz_led_recovery.py")
if not recovery.exists():
    raise SystemExit(f"menu isolation patch failed: missing LED recovery patch: {recovery}")
subprocess.run([sys.executable, str(recovery), str(p)], check=True)
