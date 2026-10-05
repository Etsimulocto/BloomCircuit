#!/usr/bin/env python3
"""Replace the BLOOM SYSTEM DND placeholder with the first playable DND slice.

Targets the current BloomPetz firmware after:
- startup splash/slot picker
- BLOOM SYSTEM launcher
- USB host clock

V0.1 hardware milestone:
- 4x4 HUD + 12x4 map, rendered through the existing 16x4 text display
- @ player, free D-pad movement
- tap A then a direction within 700 ms to attack that direction
- bump/collision rolls for enemies, chest, trap, gold, potion
- rat/goblin/skeleton autonomous slow movement
- top HUD event marquee for action/roll/result/reward
- bottom 3 HUD rows rotate vertically and marquee horizontally
- B menu with Character / Inventory / Symbols / System Menu
- symbol glossary

This deliberately does NOT add save migration, procedural rooms, equipment swapping,
or the full item system yet. The goal is to prove the core movement/combat loop on hardware.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOM_DND_PLAYABLE_V0_1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"Could not find expected {label}; refusing to guess")
    return s.replace(old, new, 1)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_dnd_playable_v0_1.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("DND playable v0.1 already applied.")
        return

    required = [
        "// BLOOMPETZ_USB_HOST_TIME_V1",
        "DND_PLACEHOLDER",
        "static void drawDndPlaceholder()",
        "static void handleInput(Input in)",
        "static void enterBloomSystemMenu()",
        "renderDisplay(",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required live anchors missing: " + ", ".join(missing))

    old_placeholder = '''static void drawDndPlaceholder() {
  renderDisplay("DND", "COMING NEXT...", "ASCII DUNGEONS", "B BACK");
}
'''
    if old_placeholder not in s:
        raise SystemExit("Exact DND placeholder renderer not found; refusing to guess")

    block = r'''// BLOOM_DND_PLAYABLE_V0_1
static constexpr uint8_t DND_MAP_W = 12;
static constexpr uint8_t DND_MAP_H = 4;
static constexpr uint8_t DND_HUD_W = 4;
static constexpr uint8_t DND_ENEMY_COUNT = 3;
static constexpr uint8_t DND_EVENT_CAP = 8;
static constexpr uint8_t DND_MENU_COUNT = 4;
static constexpr uint8_t DND_SYMBOL_COUNT = 14;

enum DndScreen : uint8_t { DND_PLAY=0, DND_MENU=1, DND_SYMBOLS=2, DND_INFO=3 };

struct DndEnemy {
  char glyph;
  const char *name;
  int8_t x;
  int8_t y;
  int8_t hp;
  uint16_t moveMinMs;
  uint16_t moveMaxMs;
  uint32_t nextMoveMs;
  bool alive;
};

static DndScreen dndScreen = DND_PLAY;
static char dndMap[DND_MAP_H][DND_MAP_W + 1];
static int8_t dndPlayerX = 1;
static int8_t dndPlayerY = 1;
static int16_t dndHp = 18;
static int16_t dndMaxHp = 18;
static int8_t dndStrength = 3;
static int8_t dndDexterity = 2;
static int8_t dndArmorClass = 12;
static uint16_t dndXp = 0;
static uint16_t dndGold = 0;
static uint8_t dndLevel = 1;
static uint8_t dndKeys = 0;
static uint32_t dndAttackArmedUntilMs = 0;
static uint8_t dndMenuIndex = 0;
static uint8_t dndSymbolIndex = 0;
static uint16_t dndMenuMarquee = 0;
static uint32_t dndMenuMarqueeMs = 0;
static String dndInfoTitle;
static String dndInfoBody;

static DndEnemy dndEnemies[DND_ENEMY_COUNT];

static String dndEvents[DND_EVENT_CAP];
static uint8_t dndEventHead = 0;
static uint8_t dndEventTail = 0;
static String dndCurrentEvent = "EXPLORE";
static uint16_t dndEventMarquee = 0;
static uint32_t dndEventMarqueeMs = 0;
static uint32_t dndEventUntilMs = 0;

static uint8_t dndStatusFirst = 0;
static uint16_t dndStatusMarquee[3] = {0,0,0};
static uint32_t dndStatusMarqueeMs[3] = {0,0,0};
static uint32_t dndStatusRotateMs = 0;
static uint32_t dndLastRenderMs = 0;

static const char* const DND_MENU_ITEMS[DND_MENU_COUNT] = {
  "CHARACTER", "INVENTORY", "SYMBOLS", "SYSTEM MENU"
};

static const char DND_SYMBOL_GLYPHS[DND_SYMBOL_COUNT] = {
  '@', '#', '.', '+', '/', '^', 'c', '$', '!', 'r', 'g', 's', 'x', '*'
};
static const char* const DND_SYMBOL_NAMES[DND_SYMBOL_COUNT] = {
  "PLAYER", "WALL", "FLOOR", "CLOSED DOOR", "OPEN DOOR", "TRAP",
  "CHEST", "GOLD", "POTION", "RAT", "GOBLIN", "SKELETON", "HIT", "MAGIC"
};

static String dndWindow(const String &src, uint16_t off, uint8_t width) {
  if (src.length() <= width) {
    String out = src;
    while (out.length() < width) out += ' ';
    return out;
  }
  String looped = src + "    " + src + "    ";
  uint16_t cycle = (uint16_t)(src.length() + 4U);
  uint16_t start = cycle ? (off % cycle) : 0;
  return looped.substring(start, start + width);
}

static void dndQueue(const String &msg) {
  uint8_t next = (uint8_t)((dndEventTail + 1U) % DND_EVENT_CAP);
  if (next == dndEventHead) dndEventHead = (uint8_t)((dndEventHead + 1U) % DND_EVENT_CAP);
  dndEvents[dndEventTail] = msg;
  dndEventTail = next;
}

static void dndServiceEventQueue() {
  uint32_t now = millis();
  if ((int32_t)(now - dndEventUntilMs) >= 0 && dndEventHead != dndEventTail) {
    dndCurrentEvent = dndEvents[dndEventHead];
    dndEventHead = (uint8_t)((dndEventHead + 1U) % DND_EVENT_CAP);
    dndEventMarquee = 0;
    dndEventMarqueeMs = now;
    dndEventUntilMs = now + 1100UL;
  }
  if (dndCurrentEvent.length() > DND_HUD_W && now - dndEventMarqueeMs >= 280UL) {
    dndEventMarqueeMs = now;
    dndEventMarquee++;
  }
}

static String dndStatusText(uint8_t idx) {
  switch (idx % 7U) {
    case 0: return "HEALTH " + String(dndHp) + "/" + String(dndMaxHp);
    case 1: return "ARMOR CLASS " + String(dndArmorClass);
    case 2: return "LEVEL " + String(dndLevel);
    case 3: return "EXPERIENCE " + String(dndXp);
    case 4: return "GOLD " + String(dndGold);
    case 5: return "IRON SWORD";
    default: return "KEYS " + String(dndKeys);
  }
}

static void dndServiceHudScroll() {
  uint32_t now = millis();
  if (now - dndStatusRotateMs >= 1900UL) {
    dndStatusRotateMs = now;
    dndStatusFirst = (uint8_t)((dndStatusFirst + 1U) % 7U);
    for (uint8_t i=0;i<3;++i) dndStatusMarquee[i] = 0;
  }
  for (uint8_t row=0; row<3; ++row) {
    String msg = dndStatusText((uint8_t)(dndStatusFirst + row));
    if (msg.length() > DND_HUD_W && now - dndStatusMarqueeMs[row] >= 340UL) {
      dndStatusMarqueeMs[row] = now;
      dndStatusMarquee[row]++;
    }
  }
}

static int8_t dndEnemyAt(int8_t x, int8_t y) {
  for (uint8_t i=0; i<DND_ENEMY_COUNT; ++i) {
    if (dndEnemies[i].alive && dndEnemies[i].x == x && dndEnemies[i].y == y) return (int8_t)i;
  }
  return -1;
}

static bool dndWalkable(int8_t x, int8_t y) {
  if (x < 0 || x >= DND_MAP_W || y < 0 || y >= DND_MAP_H) return false;
  char t = dndMap[y][x];
  return t != '#';
}

static void dndDrawPlay() {
  String rows[DND_MAP_H];
  for (uint8_t y=0; y<DND_MAP_H; ++y) {
    String mapPart;
    for (uint8_t x=0; x<DND_MAP_W; ++x) {
      char c = dndMap[y][x];
      int8_t ei = dndEnemyAt((int8_t)x, (int8_t)y);
      if (dndPlayerX == (int8_t)x && dndPlayerY == (int8_t)y) c = '@';
      else if (ei >= 0) c = dndEnemies[ei].glyph;
      mapPart += c;
    }
    String hud;
    if (y == 0) hud = dndWindow(dndCurrentEvent, dndEventMarquee, DND_HUD_W);
    else hud = dndWindow(dndStatusText((uint8_t)(dndStatusFirst + y - 1)), dndStatusMarquee[y-1], DND_HUD_W);
    rows[y] = hud + mapPart;
  }
  renderDisplay(rows[0], rows[1], rows[2], rows[3]);
}

static void dndDamagePlayer(int amount, const String &source) {
  if (amount < 0) amount = 0;
  dndHp -= amount;
  if (dndHp < 0) dndHp = 0;
  dndQueue(source + " HIT");
  dndQueue("DAMAGE " + String(amount));
  if (dndHp <= 0) {
    dndQueue("YOU FALL");
    dndHp = dndMaxHp;
    dndPlayerX = 1;
    dndPlayerY = 1;
    dndGold = (uint16_t)(dndGold / 2U);
    dndQueue("WAKE AT CAMP");
  }
}

static void dndAttackEnemy(uint8_t idx, const String &verb) {
  if (idx >= DND_ENEMY_COUNT || !dndEnemies[idx].alive) return;
  DndEnemy &e = dndEnemies[idx];
  int roll = (int)random(1, 21);
  int total = roll + dndStrength;
  dndQueue(verb + " " + String(e.name));
  dndQueue("ROLL D20 " + String(roll));
  dndQueue("TOTAL " + String(total));
  int target = 10 + (e.glyph == 's' ? 2 : (e.glyph == 'g' ? 1 : 0));
  if (roll == 1 || total < target) {
    dndQueue("MISS");
    return;
  }
  int dmg = (int)random(2, 7) + (dndStrength / 2);
  if (roll == 20) {
    dmg *= 2;
    dndQueue("CRITICAL");
  }
  e.hp -= dmg;
  dndQueue("DAMAGE " + String(dmg));
  if (e.hp <= 0) {
    e.alive = false;
    uint16_t xp = (e.glyph == 's') ? 10 : (e.glyph == 'g' ? 7 : 4);
    uint16_t gold = (uint16_t)random(1, 7);
    dndXp += xp;
    dndGold += gold;
    dndQueue(String(e.name) + " DOWN");
    dndQueue("+" + String(xp) + " XP");
    dndQueue("+" + String(gold) + " GOLD");
  }
}

static void dndAttackDirection(int8_t dx, int8_t dy) {
  dndAttackArmedUntilMs = 0;
  int8_t tx = dndPlayerX + dx;
  int8_t ty = dndPlayerY + dy;
  dndQueue("ATTACK");
  int8_t ei = dndEnemyAt(tx, ty);
  if (ei >= 0) dndAttackEnemy((uint8_t)ei, "ATTACK");
  else dndQueue("SWING AIR");
}

static void dndInteractTile(int8_t x, int8_t y) {
  int8_t ei = dndEnemyAt(x, y);
  if (ei >= 0) {
    dndAttackEnemy((uint8_t)ei, "BUMP");
    return;
  }
  char &tile = dndMap[y][x];
  if (tile == 'c') {
    int roll = (int)random(1, 21) + dndDexterity;
    dndQueue("OPEN CHEST");
    dndQueue("ROLL " + String(roll));
    if (roll >= 10) {
      tile = '$';
      dndQueue("CHEST OPEN");
      dndQueue("TREASURE!");
    } else dndQueue("LOCK HOLDS");
    return;
  }
  if (tile == '^') {
    int raw = (int)random(1, 21);
    int total = raw + dndDexterity;
    dndQueue("TRAP!");
    dndQueue("DEX ROLL " + String(total));
    tile = '.';
    if (total < 12) dndDamagePlayer((int)random(2, 6), "TRAP");
    else dndQueue("DODGED");
    return;
  }
  if (tile == '$') {
    uint16_t g = (uint16_t)random(5, 18);
    dndGold += g;
    tile = '.';
    dndQueue("TAKE GOLD");
    dndQueue("+" + String(g) + " GOLD");
    dndPlayerX = x; dndPlayerY = y;
    return;
  }
  if (tile == '!') {
    int heal = (int)random(4, 10);
    dndHp += heal;
    if (dndHp > dndMaxHp) dndHp = dndMaxHp;
    tile = '.';
    dndQueue("DRINK POTION");
    dndQueue("HEAL " + String(heal));
    dndPlayerX = x; dndPlayerY = y;
    return;
  }
  if (tile == '+') {
    tile = '/';
    dndQueue("OPEN DOOR");
    dndPlayerX = x; dndPlayerY = y;
    return;
  }
  dndPlayerX = x;
  dndPlayerY = y;
}

static void dndMovePlayer(int8_t dx, int8_t dy) {
  int8_t nx = dndPlayerX + dx;
  int8_t ny = dndPlayerY + dy;
  if (!dndWalkable(nx, ny)) {
    dndQueue("WALL");
    return;
  }
  dndInteractTile(nx, ny);
}

static void dndServiceEnemies() {
  if (dndScreen != DND_PLAY) return;
  uint32_t now = millis();
  for (uint8_t i=0; i<DND_ENEMY_COUNT; ++i) {
    DndEnemy &e = dndEnemies[i];
    if (!e.alive || (int32_t)(now - e.nextMoveMs) < 0) continue;
    e.nextMoveMs = now + (uint32_t)random(e.moveMinMs, e.moveMaxMs + 1U);

    int dxp = dndPlayerX - e.x;
    int dyp = dndPlayerY - e.y;
    if (abs(dxp) + abs(dyp) == 1) {
      int raw = (int)random(1, 21);
      int total = raw + (e.glyph == 's' ? 3 : (e.glyph == 'g' ? 2 : 1));
      dndQueue(String(e.name) + " ATTACK");
      dndQueue("ROLL " + String(total));
      if (total >= dndArmorClass) dndDamagePlayer((int)random(1, 5), String(e.name));
      else dndQueue("MISS");
      continue;
    }

    int8_t dx = 0, dy = 0;
    bool chase = abs(dxp) + abs(dyp) <= 7;
    if (chase) {
      if (abs(dxp) >= abs(dyp) && dxp != 0) dx = dxp > 0 ? 1 : -1;
      else if (dyp != 0) dy = dyp > 0 ? 1 : -1;
    } else {
      uint8_t r = (uint8_t)random(4);
      dx = r == 0 ? 1 : (r == 1 ? -1 : 0);
      dy = r == 2 ? 1 : (r == 3 ? -1 : 0);
    }
    int8_t nx = e.x + dx;
    int8_t ny = e.y + dy;
    if (!dndWalkable(nx, ny)) continue;
    if (nx == dndPlayerX && ny == dndPlayerY) continue;
    if (dndEnemyAt(nx, ny) >= 0) continue;
    char t = dndMap[ny][nx];
    if (t == 'c' || t == '^' || t == '$' || t == '!' || t == '+') continue;
    e.x = nx; e.y = ny;
  }
}

static String dndMenuWindow(uint8_t idx) {
  String s = String(idx == dndMenuIndex ? ">" : " ") + DND_MENU_ITEMS[idx];
  uint16_t off = (idx == dndMenuIndex) ? dndMenuMarquee : 0;
  return dndWindow(s, off, 16);
}

static void dndDrawMenu() {
  uint8_t first = dndMenuIndex > 1 ? dndMenuIndex - 1 : 0;
  if (first > DND_MENU_COUNT - 3) first = DND_MENU_COUNT - 3;
  renderDisplay(dndMenuWindow(first), dndMenuWindow(first+1), dndMenuWindow(first+2), "A ENTER B BACK");
}

static void dndDrawSymbols() {
  String title = String(DND_SYMBOL_GLYPHS[dndSymbolIndex]) + " " + DND_SYMBOL_NAMES[dndSymbolIndex];
  renderDisplay("SYMBOLS", dndWindow(title, dndMenuMarquee, 16),
                String(dndSymbolIndex+1) + "/" + String(DND_SYMBOL_COUNT), "UD MOVE B BACK");
}

static void dndDrawInfo() {
  renderDisplay(dndWindow(dndInfoTitle, dndMenuMarquee, 16),
                dndWindow(dndInfoBody, dndMenuMarquee, 16), "", "B BACK");
}

static void dndOpenMenu() {
  dndScreen = DND_MENU;
  dndMenuIndex = 0;
  dndMenuMarquee = 0;
  dndMenuMarqueeMs = millis();
  dndDrawMenu();
}

static void dndStartGame() {
  const char *rows[DND_MAP_H] = {
    "############",
    "#..c...^...#",
    "#....+....!#",
    "############"
  };
  for (uint8_t y=0; y<DND_MAP_H; ++y) {
    strncpy(dndMap[y], rows[y], DND_MAP_W);
    dndMap[y][DND_MAP_W] = '\0';
  }
  dndPlayerX = 1; dndPlayerY = 1;
  dndHp = dndMaxHp = 18;
  dndStrength = 3; dndDexterity = 2; dndArmorClass = 12;
  dndXp = 0; dndGold = 0; dndLevel = 1; dndKeys = 0;
  uint32_t now = millis();
  dndEnemies[0] = {'r', "RAT",      3, 2, 5, 650, 1000, now + 700, true};
  dndEnemies[1] = {'g', "GOBLIN",   8, 1, 9, 950, 1450, now + 1100, true};
  dndEnemies[2] = {'s', "SKELETON", 9, 2, 12, 1250, 1850, now + 1500, true};
  dndScreen = DND_PLAY;
  dndEventHead = dndEventTail = 0;
  dndCurrentEvent = "EXPLORE";
  dndEventUntilMs = now + 900;
  dndEventMarquee = 0;
  dndStatusFirst = 0;
  dndStatusRotateMs = now;
  dndAttackArmedUntilMs = 0;
  for (uint8_t i=0;i<3;++i) { dndStatusMarquee[i]=0; dndStatusMarqueeMs[i]=now; }
  dndQueue("DND BEGINS");
  dndQueue("A THEN DIRECTION ATTACKS");
  dndDrawPlay();
}

static void drawDndPlaceholder() {
  // Launcher compatibility: selecting DND now starts the real playable slice.
  dndStartGame();
}

static void dndHandleInput(Input in) {
  if (dndScreen == DND_PLAY) {
    if (in == BKEY) { dndOpenMenu(); return; }
    if (in == AKEY) {
      dndAttackArmedUntilMs = millis() + 700UL;
      dndCurrentEvent = "AIM";
      dndEventMarquee = 0;
      dndEventUntilMs = millis() + 700UL;
      dndDrawPlay();
      return;
    }
    bool armed = (int32_t)(dndAttackArmedUntilMs - millis()) > 0;
    if (in == UP) { if (armed) dndAttackDirection(0,-1); else dndMovePlayer(0,-1); }
    else if (in == DOWN) { if (armed) dndAttackDirection(0,1); else dndMovePlayer(0,1); }
    else if (in == LEFT) { if (armed) dndAttackDirection(-1,0); else dndMovePlayer(-1,0); }
    else if (in == RIGHT) { if (armed) dndAttackDirection(1,0); else dndMovePlayer(1,0); }
    dndDrawPlay();
    return;
  }

  if (dndScreen == DND_MENU) {
    if (in == BKEY) { dndScreen = DND_PLAY; dndDrawPlay(); return; }
    if (in == UP) dndMenuIndex = (uint8_t)((dndMenuIndex + DND_MENU_COUNT - 1U) % DND_MENU_COUNT);
    else if (in == DOWN) dndMenuIndex = (uint8_t)((dndMenuIndex + 1U) % DND_MENU_COUNT);
    else if (in == AKEY) {
      if (dndMenuIndex == 0) {
        dndInfoTitle = "CHARACTER";
        dndInfoBody = "HP " + String(dndHp) + "/" + String(dndMaxHp) + " STR " + String(dndStrength) + " DEX " + String(dndDexterity) + " AC " + String(dndArmorClass);
        dndScreen = DND_INFO;
        dndMenuMarquee = 0;
        dndDrawInfo();
        return;
      }
      if (dndMenuIndex == 1) {
        dndInfoTitle = "INVENTORY";
        dndInfoBody = "IRON SWORD  GOLD " + String(dndGold) + "  KEYS " + String(dndKeys);
        dndScreen = DND_INFO;
        dndMenuMarquee = 0;
        dndDrawInfo();
        return;
      }
      if (dndMenuIndex == 2) {
        dndScreen = DND_SYMBOLS;
        dndSymbolIndex = 0;
        dndMenuMarquee = 0;
        dndDrawSymbols();
        return;
      }
      if (dndMenuIndex == 3) {
        enterBloomSystemMenu();
        return;
      }
    }
    dndMenuMarquee = 0;
    dndMenuMarqueeMs = millis();
    dndDrawMenu();
    return;
  }

  if (dndScreen == DND_SYMBOLS) {
    if (in == BKEY) { dndScreen = DND_MENU; dndMenuMarquee=0; dndDrawMenu(); return; }
    if (in == UP) dndSymbolIndex = (uint8_t)((dndSymbolIndex + DND_SYMBOL_COUNT - 1U) % DND_SYMBOL_COUNT);
    else if (in == DOWN) dndSymbolIndex = (uint8_t)((dndSymbolIndex + 1U) % DND_SYMBOL_COUNT);
    dndMenuMarquee = 0;
    dndMenuMarqueeMs = millis();
    dndDrawSymbols();
    return;
  }

  if (dndScreen == DND_INFO) {
    if (in == BKEY || in == AKEY) { dndScreen = DND_MENU; dndMenuMarquee=0; dndDrawMenu(); }
    return;
  }
}

static void dndServiceGame() {
  if (uiMode != DND_PLACEHOLDER) return;
  if (dndScreen == DND_PLAY) {
    dndServiceEventQueue();
    dndServiceHudScroll();
    dndServiceEnemies();
    uint32_t now = millis();
    if (now - dndLastRenderMs >= 120UL) {
      dndLastRenderMs = now;
      dndDrawPlay();
    }
    return;
  }
  uint32_t now = millis();
  if (now - dndMenuMarqueeMs >= 320UL) {
    dndMenuMarqueeMs = now;
    dndMenuMarquee++;
    if (dndScreen == DND_MENU) dndDrawMenu();
    else if (dndScreen == DND_SYMBOLS) dndDrawSymbols();
    else if (dndScreen == DND_INFO) dndDrawInfo();
  }
}

'''

    # Replace placeholder function with the entire DND engine plus compatible launcher entry.
    s = replace_once(s, old_placeholder, block, "DND placeholder")

    # Replace launcher placeholder input handling with DND gameplay routing.
    old_handler = '''  if (uiMode == DND_PLACEHOLDER) {
    if (in == BKEY || in == AKEY) enterBloomSystemMenu();
    return;
  }
'''
    new_handler = '''  if (uiMode == DND_PLACEHOLDER) {
    dndHandleInput(in);
    return;
  }
'''
    s = replace_once(s, old_handler, new_handler, "DND placeholder input handler")

    # Service autonomous enemies, HUD marquees, and event queue continuously.
    loop_anchor = "void loop() {\n"
    if loop_anchor not in s:
        raise SystemExit("loop() anchor not found")
    s = s.replace(loop_anchor, loop_anchor + "  dndServiceGame();\n", 1)

    p.write_text(s)
    print(f"Playable DND v0.1 applied to {p}")
    print("Launch DND from BLOOM SYSTEM: 4x4 HUD + 12x4 map, @ player, enemies, rolls, chest/trap/loot.")
    print("Controls: D-pad move; A then direction within 700ms attacks; B opens DND menu.")
    print("DND menu: Character / Inventory / Symbols / System Menu.")
    print("This is the first hardware movement/combat slice; saves/procedural rooms/equipment swapping come next.")


if __name__ == "__main__":
    main()
