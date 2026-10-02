#!/usr/bin/env python3
"""Give HAPPY JARZ two mutually exclusive local control modes.

HOME screen:
  A     -> enter OLED main menu
  B     -> no HOME action
  UP    -> next light pattern
  DOWN  -> previous light pattern
  LEFT  -> next Light 1 palette color
  RIGHT -> next Light 2 palette color

OLED menu/detail screens = menu controls only:
  UP/DOWN -> move menu cursor (main menu)
  A       -> select highlighted item (main menu)
  B       -> back; from main menu returns HOME
  LEFT    -> back; from main menu returns HOME
  RIGHT   -> no light action

The same physical touch is never allowed to execute both a light action and a
menu action. This replaces the whole JAR-control block structurally so staged
OLED edits cannot stack a second control set on top of the original controls.

The sensory-pattern patch runs later in staging and provides PATTERN_NAMES and
PATTERN_COUNT. HOME UP/DOWN intentionally reference those final library symbols
so the physical controls cycle the same pattern set as the desktop controller.
"""

from pathlib import Path
import re
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_menu_controls.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

new_block = '''  if (inputMode == "JAR") {
    if (uiScreen == UI_HOME) {
      // HOME MODE: A opens menu, LEFT/RIGHT are the two light color buttons.
      if (q[IN_A] && !latched[IN_A]) {
        uiOpenMainMenu();
      }
      // B intentionally has no HOME action.
      if (q[IN_UP] && !latched[IN_UP]) {
        localPatternIndex=(localPatternIndex+1)%PATTERN_COUNT;
        hjSetPattern(PATTERN_NAMES[localPatternIndex]);
        oledDirty=true;
      }
      if (q[IN_DOWN] && !latched[IN_DOWN]) {
        localPatternIndex=(localPatternIndex+PATTERN_COUNT-1)%PATTERN_COUNT;
        hjSetPattern(PATTERN_NAMES[localPatternIndex]);
        oledDirty=true;
      }
      if (q[IN_LEFT] && !latched[IN_LEFT]) {
        paletteIndex1=(paletteIndex1+1)%9;
        Rgb c=palette[paletteIndex1];
        hjSetLed(1,c.r,c.g,c.b);
        oledDirty=true;
      }
      if (q[IN_RIGHT] && !latched[IN_RIGHT]) {
        paletteIndex2=(paletteIndex2+1)%9;
        Rgb c=palette[paletteIndex2];
        hjSetLed(2,c.r,c.g,c.b);
        oledDirty=true;
      }
    } else if (uiScreen == UI_MAIN_MENU) {
      // MENU MODE: no light commands are allowed here.
      if (q[IN_UP] && !latched[IN_UP]) {
        uiCursor=(uiCursor+4)%5;
        oledDirty=true;
      }
      if (q[IN_DOWN] && !latched[IN_DOWN]) {
        uiCursor=(uiCursor+1)%5;
        oledDirty=true;
      }
      if (q[IN_A] && !latched[IN_A]) {
        uiSelectMain();
      }
      if ((q[IN_B] && !latched[IN_B]) || (q[IN_LEFT] && !latched[IN_LEFT])) {
        uiGoHome();
      }
    } else {
      // DETAIL/STATUS MODE: still no light commands. B/LEFT return to menu.
      if ((q[IN_B] && !latched[IN_B]) || (q[IN_LEFT] && !latched[IN_LEFT])) {
        uiOpenMainMenu();
      }
    }
  }
'''

pattern = re.compile(
    r'  if \(inputMode == "JAR"\) \{.*?\n  \}\n\n  // Send edge events for menu/game layers and desktop diagnostics\.',
    re.DOTALL,
)
match = pattern.search(s)
if not match:
    raise SystemExit("menu mode patch failed: current JAR input block not found")

replacement = new_block + '\n  // Send edge events for menu/game layers and desktop diagnostics.'
s = s[:match.start()] + replacement + s[match.end():]
p.write_text(s, encoding="utf-8")

recovery = Path(__file__).with_name("patch_happyjarz_led_recovery.py")
if not recovery.exists():
    raise SystemExit(f"menu mode patch failed: missing LED recovery patch: {recovery}")
subprocess.run([sys.executable, str(recovery), str(p)], check=True)
