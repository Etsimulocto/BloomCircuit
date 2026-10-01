#!/usr/bin/env python3
"""Give HAPPY JARZ two mutually exclusive local control modes.

HOME screen = original proven jar controls only:
  A     -> next Light 1 palette color
  B     -> next Light 2 palette color
  UP    -> next light pattern
  DOWN  -> previous light pattern
  RIGHT -> enter OLED main menu

OLED menu/detail screens = menu controls only:
  UP/DOWN -> move menu cursor (main menu)
  A       -> select highlighted item (main menu)
  B       -> back; from main menu returns HOME
  LEFT    -> back; from main menu returns HOME
  RIGHT   -> no light action

The same physical touch is never allowed to execute both a light action and a
menu action. This replaces the whole JAR-control block structurally so staged
OLED edits cannot stack a second control set on top of the original controls.
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
      // HOME MODE: original known-good jar controls only.
      if (q[IN_A] && !latched[IN_A]) {
        paletteIndex1=(paletteIndex1+1)%9;
        Rgb c=palette[paletteIndex1];
        hjSetLed(1,c.r,c.g,c.b);
        oledDirty=true;
      }
      if (q[IN_B] && !latched[IN_B]) {
        paletteIndex2=(paletteIndex2+1)%9;
        Rgb c=palette[paletteIndex2];
        hjSetLed(2,c.r,c.g,c.b);
        oledDirty=true;
      }
      if (q[IN_UP] && !latched[IN_UP]) {
        localPatternIndex=(localPatternIndex+1)%6;
        hjSetPattern(patterns[localPatternIndex]);
        oledDirty=true;
      }
      if (q[IN_DOWN] && !latched[IN_DOWN]) {
        localPatternIndex=(localPatternIndex+5)%6;
        hjSetPattern(patterns[localPatternIndex]);
        oledDirty=true;
      }
      if (q[IN_RIGHT] && !latched[IN_RIGHT]) {
        uiOpenMainMenu();
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

# Replace exactly the JAR-mode block immediately before the edge-event comment.
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
