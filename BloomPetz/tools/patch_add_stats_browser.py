#!/usr/bin/env python3
"""Add a hardware OLED browser for BloomPetz's canonical 200-stat model.

Reads BloomPetz/data/stats/stat_manifest.json plus the 20 category JSON files at
patch time, then injects their exact canonical names into the user's local
working firmware.

UI:
- Main menu becomes FEED / TREAT / SLOT / EDIT|CREATE PET / STATS
- Menu shows a 3-row scrolling window + A ENTER B BACK footer
- STATS category browser: UP/DOWN changes among 20 categories, A opens details,
  B returns to menu
- Detail browser: LEFT/RIGHT moves among the category's 10 named stats,
  B returns to category overview
"""
from pathlib import Path
import json
import re
import sys

MARKER = "// BLOOMPETZ_STATS_BROWSER_V1"


def cpp(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')


def brace_block(text: str, start: int) -> tuple[int, int]:
    open_pos = text.find('{', start)
    if open_pos < 0:
        raise SystemExit("Opening brace not found")
    depth = 0
    in_str = False
    esc = False
    for i in range(open_pos, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit("Unbalanced brace block")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_add_stats_browser.py <bloompetz_v0_1.ino>")

    ino = Path(sys.argv[1]).expanduser().resolve()
    s = ino.read_text()
    if MARKER in s:
        print("Stats browser already applied.")
        return

    # Locate repo from .../BloomPetz/firmware/bloompetz_v0_1/bloompetz_v0_1.ino
    bloompetz = ino.parents[2]
    stats_dir = bloompetz / "data" / "stats"
    manifest_path = stats_dir / "stat_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Stat manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    cats = manifest.get("categories", [])
    if len(cats) != 20:
        raise SystemExit(f"Expected 20 canonical stat categories, found {len(cats)}")

    category_names = []
    stat_names = []
    for expected, cat in enumerate(cats):
        if cat.get("index") != expected or cat.get("offset") != expected * 10:
            raise SystemExit("Canonical stat manifest ordering/offset changed; refusing to guess")
        data = json.loads((stats_dir / cat["file"]).read_text())
        names = data.get("stats", [])
        if len(names) != 10:
            raise SystemExit(f"{cat['file']} must contain exactly 10 stats")
        category_names.append(str(cat.get("name") or data.get("category") or f"Category {expected+1}"))
        stat_names.extend(str(x) for x in names)

    # Extend the existing UiMode enum without assuming creator/ticker additions.
    em = re.search(r"enum\s+UiMode\s*:\s*uint8_t\s*\{([^}]*)\};", s, re.S)
    if not em:
        raise SystemExit("UiMode enum not found")
    body = em.group(1)
    if "STATS_BROWSE" not in body:
        new_body = body.rstrip()
        if not new_body.rstrip().endswith(','):
            new_body += ','
        new_body += " STATS_BROWSE, STATS_DETAIL "
        s = s[:em.start(1)] + new_body + s[em.end(1):]

    cat_cpp = ",\n".join(f'  "{cpp(x)}"' for x in category_names)
    stat_cpp = ",\n".join(f'  "{cpp(x)}"' for x in stat_names)

    block = f'''\n\n{MARKER}\nstatic constexpr uint8_t STAT_CATEGORY_COUNT = 20;\nstatic const char* const STAT_CATEGORY_NAMES[STAT_CATEGORY_COUNT] = {{\n{cat_cpp}\n}};\nstatic const char* const STAT_NAMES[STAT_COUNT] = {{\n{stat_cpp}\n}};\nstatic uint8_t statsCategory = 0;\nstatic uint8_t statsItem = 0;\nstatic uint8_t mainMenuIndex = 0;\n\nstatic String statPercent(float v) {{\n  float pct = constrain(v, 0.0f, 1.0f) * 100.0f;\n  return String(pct, 2) + "%";\n}}\n\nstatic float statCategoryAverage(const PetSave &p, uint8_t cat) {{\n  if (cat >= STAT_CATEGORY_COUNT) return 0.0f;\n  float sum = 0.0f;\n  uint16_t base = (uint16_t)cat * STATS_PER_CATEGORY;\n  for (uint8_t i=0; i<STATS_PER_CATEGORY; ++i) sum += p.stats[base+i];\n  return sum / (float)STATS_PER_CATEGORY;\n}}\n\nstatic void drawStatsCategory() {{\n  PetSave &p = pets[activeSlot];\n  if (!p.occupied) {{\n    renderDisplay("STATS", "NO PET", "CREATE PET FIRST", "B BACK");\n    return;\n  }}\n  String l1 = "STATS " + String(statsCategory+1) + "/20";\n  String l2 = String(STAT_CATEGORY_NAMES[statsCategory]);\n  String l3 = "AVG " + statPercent(statCategoryAverage(p, statsCategory));\n  renderDisplay(l1, l2, l3, "UD MOVE A VIEW");\n}}\n\nstatic void drawStatsDetail() {{\n  PetSave &p = pets[activeSlot];\n  uint16_t idx = (uint16_t)statsCategory * STATS_PER_CATEGORY + statsItem;\n  String l1 = String(STAT_CATEGORY_NAMES[statsCategory]);\n  String l2 = String(statsItem+1) + "/10 " + String(STAT_NAMES[idx]);\n  String l3 = "VALUE " + statPercent(p.stats[idx]);\n  renderDisplay(l1, l2, l3, "<> MOVE B BACK");\n}}\n\nstatic String mainMenuLabel(uint8_t idx) {{\n  switch (idx) {{\n    case 0: return "FEED";\n    case 1: return "TREAT";\n    case 2: return "SLOT " + String(activeSlot+1);\n    case 3: return pets[activeSlot].occupied ? "EDIT PET" : "CREATE PET";\n    default: return "STATS";\n  }}\n}}\n\nstatic void drawMainMenu() {{\n  uint8_t first = 0;\n  if (mainMenuIndex >= 2) first = mainMenuIndex - 2;\n  if (first > 2) first = 2;\n  String rows[3];\n  for (uint8_t r=0; r<3; ++r) {{\n    uint8_t idx = first + r;\n    rows[r] = String(idx == mainMenuIndex ? "> " : "  ") + mainMenuLabel(idx);\n  }}\n  renderDisplay(rows[0], rows[1], rows[2], "A ENTER B BACK");\n}}\n'''

    # Insert helpers before UI input handling so all referenced types/functions exist.
    anchor = "// UI input handling."
    if anchor not in s:
        raise SystemExit("UI input handling anchor not found")
    s = s.replace(anchor, block + "\n" + anchor, 1)

    # Replace the current MENU block using brace matching. This is intentionally
    # independent of whether prior patches made it 3 or 4 items.
    menu_start = s.find("  if (uiMode == MENU) {")
    if menu_start < 0:
        raise SystemExit("MENU handler not found")
    ms, me = brace_block(s, menu_start)
    new_menu = r'''  if (uiMode == MENU) {
    if (in==UP) mainMenuIndex=(mainMenuIndex+4)%5;
    else if(in==DOWN) mainMenuIndex=(mainMenuIndex+1)%5;
    else if(in==BKEY){uiMode=HOME;drawHome();return;}
    else if(in==AKEY){
      if(mainMenuIndex==0 && pets[activeSlot].occupied) { feedPet(pets[activeSlot]); uiMode=HOME; drawHome(); return; }
      else if(mainMenuIndex==1 && pets[activeSlot].occupied) { giveTreat(pets[activeSlot]); uiMode=HOME; drawHome(); return; }
      else if(mainMenuIndex==2){
        activeSlot=(activeSlot+1)%PET_SLOT_COUNT;
        saveSlot(activeSlot);
      }
      else if(mainMenuIndex==3){ beginEditPet(); return; }
      else if(mainMenuIndex==4){
        statsCategory=0; statsItem=0; uiMode=STATS_BROWSE; drawStatsCategory(); return;
      }
    }
    drawMainMenu();
    return;
  }'''
    s = s[:ms] + new_menu + s[me:]

    # Add stat-mode handling immediately after NONE guard in handleInput.
    hm = re.search(r"static void handleInput\(Input in\) \{\s*\n\s*if \(in == NONE\) return;", s)
    if not hm:
        raise SystemExit("handleInput NONE guard not found")
    handlers = r'''
  if (uiMode == STATS_BROWSE) {
    if (in==UP) statsCategory=(statsCategory+STAT_CATEGORY_COUNT-1)%STAT_CATEGORY_COUNT;
    else if (in==DOWN) statsCategory=(statsCategory+1)%STAT_CATEGORY_COUNT;
    else if (in==AKEY) { statsItem=0; uiMode=STATS_DETAIL; drawStatsDetail(); return; }
    else if (in==BKEY) { uiMode=MENU; drawMainMenu(); return; }
    drawStatsCategory();
    return;
  }
  if (uiMode == STATS_DETAIL) {
    if (in==LEFT) statsItem=(statsItem+STATS_PER_CATEGORY-1)%STATS_PER_CATEGORY;
    else if (in==RIGHT) statsItem=(statsItem+1)%STATS_PER_CATEGORY;
    else if (in==BKEY) { uiMode=STATS_BROWSE; drawStatsCategory(); return; }
    drawStatsDetail();
    return;
  }'''
    s = s[:hm.end()] + handlers + s[hm.end():]

    # On HOME -> MENU, replace the existing first menu render with our drawer.
    home_start = s.find("  if (uiMode == HOME) {")
    if home_start < 0:
        raise SystemExit("HOME handler not found")
    hs, he = brace_block(s, home_start)
    home = s[hs:he]
    # Match the BKEY branch's uiMode=MENU followed by any renderDisplay call.
    home2, n = re.subn(
        r"uiMode\s*=\s*MENU\s*;\s*\n\s*renderDisplay\([^;]+\);",
        "uiMode=MENU;\n      drawMainMenu();",
        home,
        count=1,
        flags=re.S,
    )
    if n == 0:
        # Some local variants may already call a menu drawer; just ensure ours is used.
        if "uiMode=MENU" in home or "uiMode = MENU" in home:
            home2 = re.sub(r"uiMode\s*=\s*MENU\s*;", "uiMode=MENU; drawMainMenu();", home, count=1)
        else:
            raise SystemExit("Could not locate HOME -> MENU transition")
    s = s[:hs] + home2 + s[he:]

    ino.write_text(s)
    print(f"Stats browser applied to {ino}")
    print("Loaded 20 canonical categories and 200 exact stat names from data/stats JSON.")
    print("MENU now has STATS; category view uses UP/DOWN + A; detail uses LEFT/RIGHT + B.")


if __name__ == "__main__":
    main()
