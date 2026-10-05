#!/usr/bin/env python3
"""Fix BloomPetz creator cursor rendering and SLOT menu behavior.

Applies after the ASCII creator + swapped creator controls patches.
- Removes the hard-coded '_' pseudo-cursor from Name/Type/Design rows.
- Keeps SLOT selection inside the menu instead of bouncing straight HOME.
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_CREATOR_MENU_FIX_V1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"Patch marker not found: {label}")
    return s.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_creator_menu_fix.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Creator/menu fix already applied.")
        return

    # Remove the fake underscore cursor. The candidate character itself is the cursor.
    old_cursor = '''    int room = 16 - line.length() - 2; // '_' + candidate char
    if (room < 0) room = 0;
    if ((int)body.length() > room) body = body.substring(body.length() - room);
    line += body;
    line += '_';
    line += creatorChar;
'''
    new_cursor = '''    int room = 16 - line.length() - 1; // candidate char
    if (room < 0) room = 0;
    if ((int)body.length() > room) body = body.substring(body.length() - room);
    line += body;
    line += creatorChar;
'''
    s = replace_once(s, old_cursor, new_cursor, "creator pseudo-cursor")

    # Change the MENU A-key block so SLOT cycles and redraws the menu instead of exiting HOME.
    old_menu = '''    else if(in==AKEY){
      if(menu==0 && pets[activeSlot].occupied) feedPet(pets[activeSlot]);
      else if(menu==1 && pets[activeSlot].occupied) giveTreat(pets[activeSlot]);
      else if(menu==2){activeSlot=(activeSlot+1)%PET_SLOT_COUNT;saveSlot(activeSlot);}
      uiMode=HOME;drawHome();return;
    }
'''
    new_menu = '''    else if(in==AKEY){
      if(menu==0 && pets[activeSlot].occupied) { feedPet(pets[activeSlot]); uiMode=HOME; drawHome(); return; }
      else if(menu==1 && pets[activeSlot].occupied) { giveTreat(pets[activeSlot]); uiMode=HOME; drawHome(); return; }
      else if(menu==2){
        activeSlot=(activeSlot+1)%PET_SLOT_COUNT;
        saveSlot(activeSlot);
        String m0=(menu==0?"> ":"  ")+String("FEED");
        String m1=(menu==1?"> ":"  ")+String("TREAT");
        String m2=(menu==2?"> ":"  ")+String("SLOT ")+String(activeSlot+1);
        renderDisplay(m0,m1,m2,"A NEXT  B BACK");
        return;
      }
    }
'''
    s = replace_once(s, old_menu, new_menu, "slot menu A behavior")

    # Make the normal menu hint match the SLOT behavior when SLOT is selected.
    old_render = '    renderDisplay(m0,m1,m2,"A ENTER B BACK");\n'
    new_render = '''    if(menu==2) renderDisplay(m0,m1,m2,"A NEXT  B BACK");
    else renderDisplay(m0,m1,m2,"A ENTER B BACK");
'''
    s = replace_once(s, old_render, new_render, "menu footer")

    # Marker near creator state so re-running is harmless.
    s = s.replace("// BLOOMPETZ_ASCII_CREATOR_V1\n", "// BLOOMPETZ_ASCII_CREATOR_V1\n// BLOOMPETZ_CREATOR_MENU_FIX_V1\n", 1)

    p.write_text(s)
    print(f"Creator/menu fix applied to {p}")
    print("No fake '_' cursor; SLOT A cycles in place; B returns HOME from menu.")


if __name__ == "__main__":
    main()
