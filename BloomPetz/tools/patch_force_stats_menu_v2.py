#!/usr/bin/env python3
"""Force-repair BloomPetz hardware menu so STATS is actually reachable.

This patch is deliberately tolerant of prior menu patches/local drift.
It assumes the stats browser itself has already been installed (drawStatsCategory,
STATS_BROWSE, etc.). It replaces the live MENU handler and HOME->MENU renderer
with one 5-item menu:
  FEED / TREAT / SLOT / EDIT|CREATE PET / STATS
The display is a 3-row scrolling window plus footer. When STATS is selected,
it is always shown on row 3.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_FORCE_STATS_MENU_V2"


def brace_block(text: str, start: int) -> tuple[int, int]:
    op = text.find('{', start)
    if op < 0:
        raise SystemExit("opening brace not found")
    depth = 0
    ins = False
    esc = False
    for i in range(op, len(text)):
        ch = text[i]
        if ins:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                ins = False
            continue
        if ch == '"': ins = True
        elif ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit("unbalanced brace block")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_force_stats_menu_v2.py <bloompetz_v0_1.ino>")
    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Force stats menu v2 already applied.")
        return

    # The browser must exist before we wire the menu to it.
    required = ["STATS_BROWSE", "drawStatsCategory", "drawStatsDetail"]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Stats browser code is missing: " + ", ".join(missing) +
                         ". Apply patch_add_stats_browser.py first, then rerun this repair.")

    # Reuse existing global mainMenuIndex if present, otherwise add it.
    if not re.search(r"\bmainMenuIndex\b", s):
        anchor = "// UI input handling."
        if anchor not in s:
            raise SystemExit("UI input handling anchor not found")
        s = s.replace(anchor, "static uint8_t mainMenuIndex = 0;\n\n" + anchor, 1)

    # Install/replace deterministic menu helpers under a unique name so old helpers
    # cannot interfere.
    helper = r'''

// BLOOMPETZ_FORCE_STATS_MENU_V2
static String forceMenuLabel(uint8_t idx) {
  switch (idx) {
    case 0: return "FEED";
    case 1: return "TREAT";
    case 2: return "SLOT " + String(activeSlot + 1);
    case 3: return pets[activeSlot].occupied ? "EDIT PET" : "CREATE PET";
    default: return "STATS";
  }
}

static void forceDrawMainMenu() {
  // 5 items, 3 visible rows. For index 4 this intentionally gives 2,3,4,
  // putting STATS on physical/menu line 3.
  uint8_t first = 0;
  if (mainMenuIndex >= 2) first = mainMenuIndex - 2;
  if (first > 2) first = 2;
  String row[3];
  for (uint8_t r=0; r<3; ++r) {
    uint8_t idx = first + r;
    row[r] = String(idx == mainMenuIndex ? "> " : "  ") + forceMenuLabel(idx);
  }
  renderDisplay(row[0], row[1], row[2], "A ENTER B BACK");
}
'''
    anchor = "// UI input handling."
    if anchor not in s:
        raise SystemExit("UI input handling anchor not found")
    s = s.replace(anchor, helper + "\n" + anchor, 1)

    # Replace the live MENU handler wholesale.
    menu_start = s.find("  if (uiMode == MENU) {")
    if menu_start < 0:
        raise SystemExit("MENU handler not found")
    ms, me = brace_block(s, menu_start)
    new_menu = r'''  if (uiMode == MENU) {
    if (in == UP) {
      mainMenuIndex = (mainMenuIndex + 4) % 5;
      forceDrawMainMenu();
      return;
    }
    if (in == DOWN) {
      mainMenuIndex = (mainMenuIndex + 1) % 5;
      forceDrawMainMenu();
      return;
    }
    if (in == BKEY) {
      uiMode = HOME;
      drawHome();
      return;
    }
    if (in == AKEY) {
      if (mainMenuIndex == 0 && pets[activeSlot].occupied) {
        feedPet(pets[activeSlot]); uiMode = HOME; drawHome(); return;
      }
      if (mainMenuIndex == 1 && pets[activeSlot].occupied) {
        giveTreat(pets[activeSlot]); uiMode = HOME; drawHome(); return;
      }
      if (mainMenuIndex == 2) {
        activeSlot = (activeSlot + 1) % PET_SLOT_COUNT;
        saveSlot(activeSlot);
        forceDrawMainMenu();
        return;
      }
      if (mainMenuIndex == 3) {
        beginEditPet();
        return;
      }
      if (mainMenuIndex == 4) {
        statsCategory = 0;
        statsItem = 0;
        uiMode = STATS_BROWSE;
        drawStatsCategory();
        return;
      }
    }
    forceDrawMainMenu();
    return;
  }'''
    s = s[:ms] + new_menu + s[me:]

    # Replace HOME's B-key transition to MENU with our renderer. Work only inside
    # the HOME handler so creator/result/etc remain untouched.
    home_start = s.find("  if (uiMode == HOME) {")
    if home_start < 0:
        raise SystemExit("HOME handler not found")
    hs, he = brace_block(s, home_start)
    home = s[hs:he]

    # Preferred: replace BKEY branch body where it enters MENU.
    pat = re.compile(r"else\s+if\s*\(in\s*==\s*BKEY\)\s*\{(?P<body>.*?)\}", re.S)
    changed = False
    out = []
    last = 0
    for m in pat.finditer(home):
        body = m.group('body')
        if re.search(r"uiMode\s*=\s*MENU", body):
            out.append(home[last:m.start()])
            out.append("else if (in == BKEY) {\n      mainMenuIndex = 0;\n      uiMode = MENU;\n      forceDrawMainMenu();\n      return;\n    }")
            last = m.end()
            changed = True
            break
    if changed:
        out.append(home[last:])
        home = ''.join(out)
    else:
        # Fallback: locate first assignment to MENU and append renderer.
        home2, n = re.subn(r"uiMode\s*=\s*MENU\s*;", "mainMenuIndex=0; uiMode=MENU; forceDrawMainMenu();", home, count=1)
        if n == 0:
            raise SystemExit("HOME -> MENU transition not found")
        home = home2

    s = s[:hs] + home + s[he:]
    p.write_text(s)
    print(f"Forced 5-item STATS menu into {p}")
    print("DOWN sequence: FEED -> TREAT -> SLOT -> EDIT/CREATE PET -> STATS -> FEED")
    print("When selected, STATS is shown on menu line 3.")


if __name__ == "__main__":
    main()
