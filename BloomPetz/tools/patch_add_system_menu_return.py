#!/usr/bin/env python3
"""Add RETURN TO SYSTEM as a sixth BloomPetz menu item.

Targets the current live menu after patch_flat_200_stats_menu.py and the shared
BLOOM SYSTEM launcher. This does not reboot the ESP32; it returns directly to
enterBloomSystemMenu() so the user can switch games immediately.
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_RETURN_TO_SYSTEM_MENU_V1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"Could not find expected {label}; refusing to guess")
    return s.replace(old, new, 1)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_add_system_menu_return.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Return-to-system menu patch already applied.")
        return

    required = [
        "// BLOOMPETZ_FLAT_200_STATS_V1",
        "enterBloomSystemMenu()",
        "static String liveMenuLabel(uint8_t idx)",
        "static void drawLiveMenu()",
        "if (uiMode == MENU)",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required live anchors missing: " + ", ".join(missing))

    old_label = '''// BLOOMPETZ_FLAT_200_STATS_V1
static String liveMenuLabel(uint8_t idx) {
  switch (idx) {
    case 0: return "FEED";
    case 1: return "TREAT";
    case 2: return "STATS";
    case 3: return "SLOT " + String(activeSlot + 1);
    default: return pets[activeSlot].occupied ? "EDIT PET" : "CREATE PET";
  }
}
'''
    new_label = '''// BLOOMPETZ_FLAT_200_STATS_V1
''' + MARKER + '''
static String liveMenuLabel(uint8_t idx) {
  switch (idx) {
    case 0: return "FEED";
    case 1: return "TREAT";
    case 2: return "STATS";
    case 3: return "SLOT " + String(activeSlot + 1);
    case 4: return pets[activeSlot].occupied ? "EDIT PET" : "CREATE PET";
    default: return "SYSTEM MENU";
  }
}
'''
    s = replace_once(s, old_label, new_label, "liveMenuLabel()")

    old_draw = '''static void drawLiveMenu() {
  // Three menu rows + footer. STATS lands on physical line 3 when selected.
  uint8_t first = 0;
  if (liveMenuIndex >= 2) first = liveMenuIndex - 2;
  if (first > 2) first = 2;
  String r0 = String((first+0)==liveMenuIndex ? "> " : "  ") + liveMenuLabel(first+0);
  String r1 = String((first+1)==liveMenuIndex ? "> " : "  ") + liveMenuLabel(first+1);
  String r2 = String((first+2)==liveMenuIndex ? "> " : "  ") + liveMenuLabel(first+2);
  renderDisplay(r0, r1, r2, "A ENTER B BACK");
}
'''
    new_draw = '''static void drawLiveMenu() {
  // Three scrolling rows + footer across six BloomPetz menu items.
  uint8_t first = 0;
  if (liveMenuIndex >= 2) first = liveMenuIndex - 2;
  if (first > 3) first = 3;
  String r0 = String((first+0)==liveMenuIndex ? "> " : "  ") + liveMenuLabel(first+0);
  String r1 = String((first+1)==liveMenuIndex ? "> " : "  ") + liveMenuLabel(first+1);
  String r2 = String((first+2)==liveMenuIndex ? "> " : "  ") + liveMenuLabel(first+2);
  renderDisplay(r0, r1, r2, "A ENTER B BACK");
}
'''
    s = replace_once(s, old_draw, new_draw, "drawLiveMenu()")

    s = replace_once(
        s,
        "if (in==UP) liveMenuIndex=(liveMenuIndex+4)%5;\n    else if(in==DOWN) liveMenuIndex=(liveMenuIndex+1)%5;",
        "if (in==UP) liveMenuIndex=(liveMenuIndex+5)%6;\n    else if(in==DOWN) liveMenuIndex=(liveMenuIndex+1)%6;",
        "six-item MENU navigation",
    )

    old_tail = '''      else if(liveMenuIndex==4){
        beginEditPet();
        return;
      }
    }
    drawLiveMenu();
'''
    new_tail = '''      else if(liveMenuIndex==4){
        beginEditPet();
        return;
      }
      else if(liveMenuIndex==5){
        enterBloomSystemMenu();
        return;
      }
    }
    drawLiveMenu();
'''
    s = replace_once(s, old_tail, new_tail, "MENU action tail")

    p.write_text(s)
    print(f"Return-to-system menu added to {p}")
    print("BloomPetz menu: FEED / TREAT / STATS / SLOT / EDIT|CREATE PET / SYSTEM MENU")
    print("A on SYSTEM MENU returns directly to BLOOM SYSTEM without rebooting.")


if __name__ == "__main__":
    main()
