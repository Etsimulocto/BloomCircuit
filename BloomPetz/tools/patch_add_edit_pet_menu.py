#!/usr/bin/env python3
"""Add CREATE/EDIT PET to the BloomPetz hardware menu.

Applies after the ASCII creator patches.
- MENU becomes FEED / TREAT / SLOT / EDIT PET (or CREATE PET for empty slot)
- Entering EDIT PET preloads existing Name / Type / Design
- Entering CREATE PET starts blank
- A enters/cycles menu items; B returns home
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_EDIT_PET_MENU_V1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"Patch marker not found: {label}")
    return s.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_add_edit_pet_menu.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()
    if MARKER in s:
        print("CREATE/EDIT PET menu already applied.")
        return

    # Add an edit entry point that preloads the current pet instead of clearing it.
    old_begin = '''static void beginCreator() {
  creatorRow = 0;
  creatorName = "";
  creatorType = "";
  creatorArt = "";
  creatorChar = 'A';
  uiMode = CREATE_PET;
  drawCreator();
}
'''
    new_begin = '''// BLOOMPETZ_EDIT_PET_MENU_V1
static void beginCreator() {
  creatorRow = 0;
  creatorName = "";
  creatorType = "";
  creatorArt = "";
  creatorChar = 'A';
  uiMode = CREATE_PET;
  drawCreator();
}

static void beginEditPet() {
  PetSave &p = pets[activeSlot];
  creatorRow = 0;
  creatorChar = 'A';
  if (p.occupied) {
    creatorName = String(p.name);
    creatorType = String(p.type);
    creatorArt = String(p.art);
  } else {
    creatorName = "";
    creatorType = "";
    creatorArt = "";
  }
  uiMode = CREATE_PET;
  drawCreator();
}
'''
    s = replace_once(s, old_begin, new_begin, "beginCreator")

    # Replace the 3-item menu entry screen with 4 items, using line 4 for CREATE/EDIT PET.
    old_open = '''      uiMode=MENU;
      renderDisplay("> FEED", "  TREAT", "  SLOT", "A ENTER B BACK");
'''
    new_open = '''      uiMode=MENU;
      renderDisplay("> FEED", "  TREAT", "  SLOT", pets[activeSlot].occupied ? "  EDIT PET" : "  CREATE PET");
'''
    s = replace_once(s, old_open, new_open, "menu open")

    # Replace the entire MENU handler with 4-item behavior.
    start = s.find("  if (uiMode == MENU) {")
    if start < 0:
        raise SystemExit("Patch marker not found: MENU block start")
    end_marker = "\n  }\n}\n\nvoid setup()"
    end = s.find(end_marker, start)
    if end < 0:
        raise SystemExit("Patch marker not found: MENU block end")

    new_menu = r'''  if (uiMode == MENU) {
    static uint8_t menu=0;
    if (in==UP) menu=(menu+3)%4;
    else if(in==DOWN) menu=(menu+1)%4;
    else if(in==BKEY){uiMode=HOME;drawHome();return;}
    else if(in==AKEY){
      if(menu==0 && pets[activeSlot].occupied) { feedPet(pets[activeSlot]); uiMode=HOME; drawHome(); return; }
      else if(menu==1 && pets[activeSlot].occupied) { giveTreat(pets[activeSlot]); uiMode=HOME; drawHome(); return; }
      else if(menu==2){
        activeSlot=(activeSlot+1)%PET_SLOT_COUNT;
        saveSlot(activeSlot);
      }
      else if(menu==3){
        beginEditPet();
        return;
      }
    }

    String m0=(menu==0?"> ":"  ")+String("FEED");
    String m1=(menu==1?"> ":"  ")+String("TREAT");
    String m2=(menu==2?"> ":"  ")+String("SLOT ")+String(activeSlot+1);
    String m3=(menu==3?"> ":"  ")+String(pets[activeSlot].occupied ? "EDIT PET" : "CREATE PET");
    renderDisplay(m0,m1,m2,m3);
  }'''

    s = s[:start] + new_menu + s[end + len("\n  }"):]

    p.write_text(s)
    print(f"CREATE/EDIT PET menu applied to {p}")
    print("MENU: FEED / TREAT / SLOT / EDIT PET (CREATE PET when empty)")
    print("EDIT PET preloads Name / Type / Design before saving.")


if __name__ == "__main__":
    main()
