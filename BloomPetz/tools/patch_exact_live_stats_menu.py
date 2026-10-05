#!/usr/bin/env python3
"""Patch the exact live BloomPetz UI layout observed on 2026-10-04.

Targets the local firmware shape where:
  enum UiMode : uint8_t { HOME, SHOW_SEQUENCE, ENTER_SEQUENCE, RESULT, MENU, CREATE_PET };
  HOME opens a hard-coded 4-line FEED/TREAT/SLOT/EDIT PET menu
  MENU uses static uint8_t menu and modulo 4

Adds a 5-item scrolling menu with STATS plus a 20-category / 200-stat browser.
Reads canonical names from BloomPetz/data/stats at patch time.
"""
from pathlib import Path
import json
import sys

MARKER = "// BLOOMPETZ_EXACT_LIVE_STATS_MENU_V1"


def cpp(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_exact_live_stats_menu.py <bloompetz_v0_1.ino>")

    ino = Path(sys.argv[1]).expanduser().resolve()
    s = ino.read_text()

    if MARKER in s:
        print("Exact live STATS menu patch already applied.")
        return

    # Verify exact live anchors from the user's pasted sketch.
    old_enum = "enum UiMode : uint8_t { HOME, SHOW_SEQUENCE, ENTER_SEQUENCE, RESULT, MENU, CREATE_PET };"
    if old_enum not in s:
        raise SystemExit("Exact live UiMode enum not found; refusing to guess")

    old_home_menu = '''    else if (in == BKEY) {
      uiMode=MENU;
      renderDisplay("> FEED", "  TREAT", "  SLOT", pets[activeSlot].occupied ? "  EDIT PET" : "  CREATE PET");
    }
'''
    if old_home_menu not in s:
        raise SystemExit("Exact live HOME->MENU block not found; refusing to guess")

    old_menu = '''  if (uiMode == MENU) {
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
  }
'''
    if old_menu not in s:
        raise SystemExit("Exact live 4-item MENU handler not found; refusing to guess")

    # Load canonical stat metadata from the repo copy on the Pi.
    bloompetz = ino.parents[2]
    stats_dir = bloompetz / "data" / "stats"
    manifest = json.loads((stats_dir / "stat_manifest.json").read_text())
    cats = manifest.get("categories", [])
    if len(cats) != 20:
        raise SystemExit(f"Expected 20 stat categories, found {len(cats)}")

    cat_names = []
    stat_names = []
    for i, cat in enumerate(cats):
        if cat.get("index") != i or cat.get("offset") != i * 10:
            raise SystemExit("Stat manifest order/offset mismatch")
        d = json.loads((stats_dir / cat["file"]).read_text())
        names = d.get("stats", [])
        if len(names) != 10:
            raise SystemExit(f"{cat['file']} does not contain exactly 10 stats")
        cat_names.append(str(cat.get("name") or d.get("category") or f"Category {i+1}"))
        stat_names.extend(str(x) for x in names)

    if len(stat_names) != 200:
        raise SystemExit(f"Expected 200 stat names, found {len(stat_names)}")

    cat_cpp = ",\n".join(f'  "{cpp(x)}"' for x in cat_names)
    stat_cpp = ",\n".join(f'  "{cpp(x)}"' for x in stat_names)

    # Extend UiMode.
    new_enum = "enum UiMode : uint8_t { HOME, SHOW_SEQUENCE, ENTER_SEQUENCE, RESULT, MENU, CREATE_PET, STATS_BROWSE, STATS_DETAIL };"
    s = s.replace(old_enum, new_enum, 1)

    # Insert exact menu/stats helpers immediately before handleInput().
    anchor = "static void handleInput(Input in) {"
    if anchor not in s:
        raise SystemExit("handleInput anchor missing")

    helpers = f'''{MARKER}
static constexpr uint8_t STAT_CATEGORY_COUNT_UI = 20;
static const char* const UI_STAT_CATEGORY_NAMES[STAT_CATEGORY_COUNT_UI] = {{
{cat_cpp}
}};
static const char* const UI_STAT_NAMES[STAT_COUNT] = {{
{stat_cpp}
}};
static uint8_t liveMenuIndex = 0;
static uint8_t liveStatsCategory = 0;
static uint8_t liveStatsItem = 0;

static String uiStatPercent(float v) {{
  return String(v * 100.0f, 4) + "%";
}}

static String liveMenuLabel(uint8_t idx) {{
  switch (idx) {{
    case 0: return "FEED";
    case 1: return "TREAT";
    case 2: return "SLOT " + String(activeSlot + 1);
    case 3: return pets[activeSlot].occupied ? "EDIT PET" : "CREATE PET";
    default: return "STATS";
  }}
}}

static void drawLiveMenu() {{
  // Three menu rows + footer. STATS lands on physical line 3 when selected.
  uint8_t first = 0;
  if (liveMenuIndex >= 2) first = liveMenuIndex - 2;
  if (first > 2) first = 2;
  String r0 = String((first+0)==liveMenuIndex ? "> " : "  ") + liveMenuLabel(first+0);
  String r1 = String((first+1)==liveMenuIndex ? "> " : "  ") + liveMenuLabel(first+1);
  String r2 = String((first+2)==liveMenuIndex ? "> " : "  ") + liveMenuLabel(first+2);
  renderDisplay(r0, r1, r2, "A ENTER B BACK");
}}

static float liveCategoryAverage(const PetSave &p, uint8_t cat) {{
  uint16_t base = (uint16_t)cat * STATS_PER_CATEGORY;
  float sum = 0.0f;
  for (uint8_t i=0; i<STATS_PER_CATEGORY; ++i) sum += p.stats[base+i];
  return sum / (float)STATS_PER_CATEGORY;
}}

static void drawLiveStatsCategory() {{
  PetSave &p = pets[activeSlot];
  if (!p.occupied) {{
    renderDisplay("STATS", "NO PET", "CREATE PET FIRST", "B BACK");
    return;
  }}
  renderDisplay(
    "STATS " + String(liveStatsCategory+1) + "/20",
    String(UI_STAT_CATEGORY_NAMES[liveStatsCategory]),
    "AVG " + uiStatPercent(liveCategoryAverage(p, liveStatsCategory)),
    "UD MOVE A VIEW"
  );
}}

static void drawLiveStatsDetail() {{
  PetSave &p = pets[activeSlot];
  uint16_t idx = (uint16_t)liveStatsCategory * STATS_PER_CATEGORY + liveStatsItem;
  renderDisplay(
    String(UI_STAT_CATEGORY_NAMES[liveStatsCategory]),
    String(liveStatsItem+1) + "/10 " + String(UI_STAT_NAMES[idx]),
    uiStatPercent(p.stats[idx]),
    "<> MOVE B BACK"
  );
}}

'''
    s = s.replace(anchor, helpers + anchor, 1)

    # Add stats-mode handlers immediately after NONE guard.
    none_guard = "  if (in == NONE) return;\n"
    insert = '''  if (uiMode == STATS_BROWSE) {
    if (in == UP) liveStatsCategory = (liveStatsCategory + STAT_CATEGORY_COUNT_UI - 1) % STAT_CATEGORY_COUNT_UI;
    else if (in == DOWN) liveStatsCategory = (liveStatsCategory + 1) % STAT_CATEGORY_COUNT_UI;
    else if (in == AKEY) { liveStatsItem = 0; uiMode = STATS_DETAIL; drawLiveStatsDetail(); return; }
    else if (in == BKEY) { uiMode = MENU; drawLiveMenu(); return; }
    drawLiveStatsCategory();
    return;
  }
  if (uiMode == STATS_DETAIL) {
    if (in == LEFT) liveStatsItem = (liveStatsItem + STATS_PER_CATEGORY - 1) % STATS_PER_CATEGORY;
    else if (in == RIGHT) liveStatsItem = (liveStatsItem + 1) % STATS_PER_CATEGORY;
    else if (in == BKEY) { uiMode = STATS_BROWSE; drawLiveStatsCategory(); return; }
    drawLiveStatsDetail();
    return;
  }
'''
    if none_guard not in s:
        raise SystemExit("NONE guard missing")
    s = s.replace(none_guard, none_guard + insert, 1)

    # Replace exact HOME -> MENU block.
    new_home_menu = '''    else if (in == BKEY) {
      liveMenuIndex = 0;
      uiMode=MENU;
      drawLiveMenu();
    }
'''
    s = s.replace(old_home_menu, new_home_menu, 1)

    # Replace exact live 4-item menu handler.
    new_menu = '''  if (uiMode == MENU) {
    if (in==UP) liveMenuIndex=(liveMenuIndex+4)%5;
    else if(in==DOWN) liveMenuIndex=(liveMenuIndex+1)%5;
    else if(in==BKEY){uiMode=HOME;drawHome();return;}
    else if(in==AKEY){
      if(liveMenuIndex==0 && pets[activeSlot].occupied) { feedPet(pets[activeSlot]); uiMode=HOME; drawHome(); return; }
      else if(liveMenuIndex==1 && pets[activeSlot].occupied) { giveTreat(pets[activeSlot]); uiMode=HOME; drawHome(); return; }
      else if(liveMenuIndex==2){
        activeSlot=(activeSlot+1)%PET_SLOT_COUNT;
        saveSlot(activeSlot);
      }
      else if(liveMenuIndex==3){
        beginEditPet();
        return;
      }
      else if(liveMenuIndex==4){
        liveStatsCategory=0;
        liveStatsItem=0;
        uiMode=STATS_BROWSE;
        drawLiveStatsCategory();
        return;
      }
    }
    drawLiveMenu();
    return;
  }
'''
    s = s.replace(old_menu, new_menu, 1)

    ino.write_text(s)
    print(f"Exact live STATS menu patch applied to {ino}")
    print("Menu is now 5 items: FEED / TREAT / SLOT / EDIT|CREATE PET / STATS")
    print("DOWN reaches STATS; selected STATS appears on OLED line 3.")
    print("STATS opens 20 categories; A opens 10 named stats; values show 4 decimal percent.")


if __name__ == "__main__":
    main()
