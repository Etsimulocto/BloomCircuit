#!/usr/bin/env python3
"""Flatten BloomPetz STATS to a direct 200-stat browser and move STATS to menu row 3.

Apply after patch_exact_live_stats_menu.py.

Final menu order:
  FEED
  TREAT
  STATS
  SLOT
  EDIT PET / CREATE PET

STATS behavior:
- A on STATS opens stat 1/200 directly.
- LEFT/RIGHT cycles through all 200 canonical stats.
- No 20-category gate.
- Line 1 shows STAT n/200.
- Line 2 shows the canonical stat name (marquees when >16 chars).
- Line 3 shows value as 0.0000%.
- B returns to menu.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_FLAT_200_STATS_V1"
REQUIRED = "// BLOOMPETZ_EXACT_LIVE_STATS_MENU_V1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"Could not find expected {label}; refusing to guess")
    return s.replace(old, new, 1)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_flat_200_stats_menu.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Flat 200-stat menu patch already applied.")
        return
    if REQUIRED not in s:
        raise SystemExit("Exact live STATS patch is not present; apply patch_exact_live_stats_menu.py first")

    old_label = '''static String liveMenuLabel(uint8_t idx) {
  switch (idx) {
    case 0: return "FEED";
    case 1: return "TREAT";
    case 2: return "SLOT " + String(activeSlot + 1);
    case 3: return pets[activeSlot].occupied ? "EDIT PET" : "CREATE PET";
    default: return "STATS";
  }
}
'''
    new_label = f'''{MARKER}
static String liveMenuLabel(uint8_t idx) {{
  switch (idx) {{
    case 0: return "FEED";
    case 1: return "TREAT";
    case 2: return "STATS";
    case 3: return "SLOT " + String(activeSlot + 1);
    default: return pets[activeSlot].occupied ? "EDIT PET" : "CREATE PET";
  }}
}}
'''
    s = replace_once(s, old_label, new_label, "liveMenuLabel()")

    old_state = '''static uint8_t liveMenuIndex = 0;
static uint8_t liveStatsCategory = 0;
static uint8_t liveStatsItem = 0;
'''
    new_state = '''static uint8_t liveMenuIndex = 0;
static uint8_t liveStatsCategory = 0;
static uint8_t liveStatsItem = 0;
static uint16_t liveFlatStatIndex = 0;
static uint16_t liveFlatStatMarqueeOffset = 0;
static uint32_t liveFlatStatMarqueeMs = 0;
static constexpr uint32_t LIVE_STAT_MARQUEE_STEP_MS = 350UL;
'''
    s = replace_once(s, old_state, new_state, "stats state globals")

    # Replace category/detail draw functions with one direct 200-stat screen.
    pattern = re.compile(
        r'''static float liveCategoryAverage\(const PetSave &p, uint8_t cat\) \{.*?\n\}\n\nstatic void drawLiveStatsCategory\(\) \{.*?\n\}\n\nstatic void drawLiveStatsDetail\(\) \{.*?\n\}\n''',
        re.S,
    )
    m = pattern.search(s)
    if not m:
        raise SystemExit("Could not find existing category/detail stats renderer block")

    new_stats = r'''static String liveFlatStatNameWindow() {
  String msg = String(UI_STAT_NAMES[liveFlatStatIndex % STAT_COUNT]);
  if (msg.length() <= 16) return msg;
  String looped = msg + "    " + msg + "    ";
  uint16_t cycle = (uint16_t)(msg.length() + 4);
  uint16_t off = cycle ? (liveFlatStatMarqueeOffset % cycle) : 0;
  return looped.substring(off, off + 16);
}

static void drawLiveFlatStat() {
  PetSave &pet = pets[activeSlot];
  if (!pet.occupied) {
    renderDisplay("STATS", "NO PET", "CREATE PET FIRST", "B BACK");
    return;
  }
  uint16_t idx = liveFlatStatIndex % STAT_COUNT;
  renderDisplay(
    "STAT " + String(idx + 1) + "/200",
    liveFlatStatNameWindow(),
    uiStatPercent(pet.stats[idx]),
    "<> MOVE B BACK"
  );
}

static void serviceLiveFlatStatMarquee() {
  if (uiMode != STATS_BROWSE || !pets[activeSlot].occupied) return;
  String msg = String(UI_STAT_NAMES[liveFlatStatIndex % STAT_COUNT]);
  if (msg.length() <= 16) return;
  uint32_t now = millis();
  if (liveFlatStatMarqueeMs == 0) liveFlatStatMarqueeMs = now;
  if (now - liveFlatStatMarqueeMs < LIVE_STAT_MARQUEE_STEP_MS) return;
  liveFlatStatMarqueeMs = now;
  liveFlatStatMarqueeOffset++;
  drawLiveFlatStat();
}
'''
    s = s[:m.start()] + new_stats + s[m.end():]

    old_handlers = '''  if (uiMode == STATS_BROWSE) {
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
    new_handlers = '''  if (uiMode == STATS_BROWSE) {
    if (in == LEFT) liveFlatStatIndex = (uint16_t)((liveFlatStatIndex + STAT_COUNT - 1) % STAT_COUNT);
    else if (in == RIGHT) liveFlatStatIndex = (uint16_t)((liveFlatStatIndex + 1) % STAT_COUNT);
    else if (in == BKEY) { uiMode = MENU; drawLiveMenu(); return; }
    else return;
    liveFlatStatMarqueeOffset = 0;
    liveFlatStatMarqueeMs = millis();
    drawLiveFlatStat();
    return;
  }
  if (uiMode == STATS_DETAIL) {
    uiMode = STATS_BROWSE;
    drawLiveFlatStat();
    return;
  }
'''
    s = replace_once(s, old_handlers, new_handlers, "stats input handlers")

    old_menu_action = '''      else if(liveMenuIndex==2){
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
'''
    new_menu_action = '''      else if(liveMenuIndex==2){
        liveFlatStatIndex=0;
        liveFlatStatMarqueeOffset=0;
        liveFlatStatMarqueeMs=millis();
        uiMode=STATS_BROWSE;
        drawLiveFlatStat();
        return;
      }
      else if(liveMenuIndex==3){
        activeSlot=(activeSlot+1)%PET_SLOT_COUNT;
        saveSlot(activeSlot);
      }
      else if(liveMenuIndex==4){
        beginEditPet();
        return;
      }
'''
    s = replace_once(s, old_menu_action, new_menu_action, "MENU A-key actions")

    # Put the marquee service into loop once.
    if "serviceLiveFlatStatMarquee();" not in s:
        loop = "void loop() {\n"
        if loop not in s:
            raise SystemExit("loop() not found")
        s = s.replace(loop, loop + "  serviceLiveFlatStatMarquee();\n", 1)

    p.write_text(s)
    print(f"Flat 200-stat browser applied to {p}")
    print("Menu order: FEED / TREAT / STATS / SLOT / EDIT|CREATE PET")
    print("STATS opens directly at 1/200; LEFT/RIGHT cycles all 200 stats.")
    print("Long stat names marquee; values display with four decimal percent places.")


if __name__ == "__main__":
    main()
