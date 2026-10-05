#!/usr/bin/env python3
"""Upgrade BLOOM DND to infinite disposable rooms with universal room-depth scaling.

Targets the live local bloompetz_v0_1.ino after the current playable DND/full-width
work. Replaces ONLY the DND engine block; BLOOM SYSTEM/BloomPetz remain untouched.

Current architecture after this patch:
- actual room buffer: 30x16
- visible map camera: 14x4
- HUD: 7x4
- total physical line: 21 chars
- entering any + door discards the current room, increments ROOM, and generates a
  fresh random room. There is intentionally no return/backtracking.
- ROOM N is the universal generated-stat volatility range: each generated value
  gets an independent random modifier in [-N,+N] (internally capped at 120 only
  to keep integer ranges sane on absurdly deep runs).
- enemy six core stats, HP, AC, hit bonus, damage, XP, and gold are generated from
  room depth; traps/chests/gold/potions use room depth; found weapons generate
  room-scaled damage and hit bonus and auto-equip.
- death returns the run to ROOM 1, preserves deepest-room record, halves gold,
  restores HP, and generates a fresh room.
- DND continues to publish BP|SCREEN so Raspberry Pi Mini mirrors the exact 21
  logical columns.

The patch is intentionally block-level because the old DND prototype accumulated
several geometry/render patches. It uses exact block markers and refuses to write
if the live boundaries cannot be identified safely.
"""
from pathlib import Path
import sys

START = "// BLOOM_DND_PLAYABLE_V0_1"
END = "// BLOOMPETZ_USB_HOST_TIME_V1"
MARKER = "// BLOOM_DND_INFINITE_ROOMS_DEPTH_V1"

ENGINE = r'''// BLOOM_DND_PLAYABLE_V0_1
// BLOOM_DND_INFINITE_ROOMS_DEPTH_V1
static constexpr uint8_t DND_VIEW_W = 14;
static constexpr uint8_t DND_VIEW_H = 4;
static constexpr uint8_t DND_HUD_W = 7;
static constexpr uint8_t DND_ROOM_W = 30;
static constexpr uint8_t DND_ROOM_H = 16;
static constexpr uint8_t DND_ENEMY_COUNT = 8;
static constexpr uint8_t DND_EVENT_CAP = 10;
static constexpr uint8_t DND_MENU_COUNT = 4;
static constexpr uint8_t DND_SYMBOL_COUNT = 15;

enum DndScreen : uint8_t { DND_PLAY=0, DND_MENU=1, DND_SYMBOLS=2, DND_INFO=3 };

struct DndEnemy {
  char glyph;
  const char *name;
  int8_t x;
  int8_t y;
  int16_t str;
  int16_t dex;
  int16_t con;
  int16_t intel;
  int16_t wis;
  int16_t cha;
  int16_t hp;
  int16_t maxHp;
  int16_t ac;
  int16_t hitBonus;
  int16_t damageMin;
  int16_t damageMax;
  uint16_t xpReward;
  uint16_t goldReward;
  uint16_t moveMinMs;
  uint16_t moveMaxMs;
  uint32_t nextMoveMs;
  bool alive;
};

struct DndWeapon {
  String name;
  int16_t damageMin;
  int16_t damageMax;
  int16_t hitBonus;
  uint16_t foundRoom;
};

static DndScreen dndScreen = DND_PLAY;
static char dndMap[DND_ROOM_H][DND_ROOM_W + 1];
static int8_t dndPlayerX = 2;
static int8_t dndPlayerY = 2;
static int8_t dndCamX = 0;
static int8_t dndCamY = 0;

static int16_t dndHp = 18;
static int16_t dndMaxHp = 18;
static int16_t dndStrength = 3;
static int16_t dndDexterity = 2;
static int16_t dndArmorClass = 12;
static uint32_t dndXp = 0;
static uint32_t dndGold = 0;
static uint16_t dndLevel = 1;
static uint16_t dndKeys = 0;
static uint16_t dndRoomNumber = 1;
static uint16_t dndDeepestRoom = 1;
static DndWeapon dndWeapon = {"IRON SWORD", 2, 6, 0, 1};

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
  '@', '#', '.', '+', '/', '^', 'c', '$', '!', 'w', 'r', 'g', 's', 'x', '*'
};
static const char* const DND_SYMBOL_NAMES[DND_SYMBOL_COUNT] = {
  "PLAYER", "WALL", "FLOOR", "DOOR TO NEXT ROOM", "OPEN DOOR", "TRAP",
  "CHEST", "GOLD", "POTION", "WEAPON", "RAT", "GOBLIN", "SKELETON", "HIT", "MAGIC"
};

static int dndDepthForRoll() {
  // ROOM is the scaling source. Cap only prevents absurd integer ranges far beyond
  // normal play; ROOM/deepest counters themselves remain unbounded uint16 values.
  return dndRoomNumber > 120 ? 120 : (int)dndRoomNumber;
}

static int dndSignedRoomMod() {
  int depth = dndDepthForRoll();
  return (int)random(-depth, depth + 1);
}

static int dndScaled(int baseValue, int minimumValue) {
  long v = (long)baseValue + (long)dndSignedRoomMod();
  if (v < minimumValue) v = minimumValue;
  if (v > 30000) v = 30000;
  return (int)v;
}

static int dndEnemyScaled(int baseValue, int minimumValue) {
  // Independent +/-ROOM volatility plus a gentle average upward pressure. ROOM 30
  // can still roll weak individual stats, but the population trends stronger.
  int depth = dndDepthForRoll();
  long v = (long)baseValue + (long)(depth / 3) + (long)dndSignedRoomMod();
  if (v < minimumValue) v = minimumValue;
  if (v > 30000) v = 30000;
  return (int)v;
}

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
    dndEventUntilMs = now + 1050UL;
  }
  if (dndCurrentEvent.length() > DND_HUD_W && now - dndEventMarqueeMs >= 260UL) {
    dndEventMarqueeMs = now;
    dndEventMarquee++;
  }
}

static String dndStatusText(uint8_t idx) {
  switch (idx % 9U) {
    case 0: return "ROOM " + String(dndRoomNumber);
    case 1: return "HEALTH " + String(dndHp) + "/" + String(dndMaxHp);
    case 2: return "ARMOR CLASS " + String(dndArmorClass);
    case 3: return "LEVEL " + String(dndLevel);
    case 4: return "EXPERIENCE " + String(dndXp);
    case 5: return "GOLD " + String(dndGold);
    case 6: return dndWeapon.name + " " + String(dndWeapon.damageMin) + "-" + String(dndWeapon.damageMax);
    case 7: return "DEEPEST " + String(dndDeepestRoom);
    default: return "KEYS " + String(dndKeys);
  }
}

static void dndServiceHudScroll() {
  uint32_t now = millis();
  if (now - dndStatusRotateMs >= 1900UL) {
    dndStatusRotateMs = now;
    dndStatusFirst = (uint8_t)((dndStatusFirst + 1U) % 9U);
    for (uint8_t i=0;i<3;++i) dndStatusMarquee[i] = 0;
  }
  for (uint8_t row=0; row<3; ++row) {
    String msg = dndStatusText((uint8_t)(dndStatusFirst + row));
    if (msg.length() > DND_HUD_W && now - dndStatusMarqueeMs[row] >= 330UL) {
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

static bool dndInside(int x, int y) {
  return x >= 0 && x < DND_ROOM_W && y >= 0 && y < DND_ROOM_H;
}

static bool dndWalkable(int8_t x, int8_t y) {
  if (!dndInside(x, y)) return false;
  return dndMap[(uint8_t)y][(uint8_t)x] != '#';
}

static void dndUpdateCamera() {
  int cx = dndPlayerX - (DND_VIEW_W / 2);
  int cy = dndPlayerY - (DND_VIEW_H / 2);
  int maxX = DND_ROOM_W - DND_VIEW_W;
  int maxY = DND_ROOM_H - DND_VIEW_H;
  if (cx < 0) cx = 0;
  if (cy < 0) cy = 0;
  if (cx > maxX) cx = maxX;
  if (cy > maxY) cy = maxY;
  dndCamX = (int8_t)cx;
  dndCamY = (int8_t)cy;
}

static void dndRenderFull(const String &r0, const String &r1,
                          const String &r2, const String &r3) {
  if (uiMode != DND_PLACEHOLDER) return;
  String rows[4] = {
    r0.substring(0, 21), r1.substring(0, 21),
    r2.substring(0, 21), r3.substring(0, 21)
  };
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tr);
  oled.drawStr(0, 13, rows[0].c_str());
  oled.drawStr(0, 29, rows[1].c_str());
  oled.drawStr(0, 45, rows[2].c_str());
  oled.drawStr(0, 61, rows[3].c_str());
  oled.sendBuffer();

  bool changed = false;
  for (uint8_t i=0; i<4; ++i) {
    if (screenLines[i] != rows[i]) {
      screenLines[i] = rows[i];
      changed = true;
    }
  }
  if (changed) {
    Serial.print("BP|SCREEN|1="); Serial.print(screenLines[0]);
    Serial.print("|2="); Serial.print(screenLines[1]);
    Serial.print("|3="); Serial.print(screenLines[2]);
    Serial.print("|4="); Serial.println(screenLines[3]);
  }
}

static void dndDrawPlay() {
  dndUpdateCamera();
  String rows[DND_VIEW_H];
  for (uint8_t vy=0; vy<DND_VIEW_H; ++vy) {
    int ry = dndCamY + vy;
    String mapPart;
    for (uint8_t vx=0; vx<DND_VIEW_W; ++vx) {
      int rx = dndCamX + vx;
      char c = dndMap[ry][rx];
      int8_t ei = dndEnemyAt((int8_t)rx, (int8_t)ry);
      if (dndPlayerX == rx && dndPlayerY == ry) c = '@';
      else if (ei >= 0) c = dndEnemies[(uint8_t)ei].glyph;
      mapPart += c;
    }
    String hud;
    if (vy == 0) hud = dndWindow(dndCurrentEvent, dndEventMarquee, DND_HUD_W);
    else hud = dndWindow(dndStatusText((uint8_t)(dndStatusFirst + vy - 1)), dndStatusMarquee[vy-1], DND_HUD_W);
    rows[vy] = hud + mapPart;
  }
  dndRenderFull(rows[0], rows[1], rows[2], rows[3]);
}

static void dndClearEnemies() {
  for (uint8_t i=0;i<DND_ENEMY_COUNT;++i) dndEnemies[i].alive = false;
}

static bool dndTileFreeForSpawn(int x, int y) {
  if (x <= 0 || x >= DND_ROOM_W-1 || y <= 0 || y >= DND_ROOM_H-1) return false;
  if (dndMap[y][x] != '.') return false;
  if (x == dndPlayerX && y == dndPlayerY) return false;
  if (dndEnemyAt((int8_t)x,(int8_t)y) >= 0) return false;
  return true;
}

static bool dndFindFreeTile(int8_t &x, int8_t &y) {
  for (uint16_t tries=0; tries<250; ++tries) {
    int tx = (int)random(1, DND_ROOM_W-1);
    int ty = (int)random(1, DND_ROOM_H-1);
    if (dndTileFreeForSpawn(tx, ty)) {
      x = (int8_t)tx; y = (int8_t)ty; return true;
    }
  }
  return false;
}

static void dndPlaceTile(char glyph, uint8_t count) {
  for (uint8_t i=0;i<count;++i) {
    int8_t x=0,y=0;
    if (dndFindFreeTile(x,y)) dndMap[(uint8_t)y][(uint8_t)x] = glyph;
  }
}

static void dndBuildEnemy(uint8_t idx, char glyph, const char *name,
                          int baseHp, int baseAc, int baseDamageMin, int baseDamageMax,
                          uint16_t moveMin, uint16_t moveMax) {
  if (idx >= DND_ENEMY_COUNT) return;
  int8_t x=0,y=0;
  if (!dndFindFreeTile(x,y)) return;
  DndEnemy &e = dndEnemies[idx];
  e.glyph = glyph; e.name = name; e.x = x; e.y = y;
  e.str   = dndEnemyScaled(3, 1);
  e.dex   = dndEnemyScaled(3, 1);
  e.con   = dndEnemyScaled(3, 1);
  e.intel = dndEnemyScaled(2, 1);
  e.wis   = dndEnemyScaled(2, 1);
  e.cha   = dndEnemyScaled(2, 1);
  e.maxHp = dndEnemyScaled(baseHp, 1);
  e.hp = e.maxHp;
  e.ac = dndEnemyScaled(baseAc, 1);
  e.hitBonus = dndEnemyScaled(1, -20);
  e.damageMin = dndEnemyScaled(baseDamageMin, 1);
  e.damageMax = dndEnemyScaled(baseDamageMax, e.damageMin);
  e.xpReward = (uint16_t)dndEnemyScaled(baseHp + baseAc, 1);
  e.goldReward = (uint16_t)dndEnemyScaled(baseDamageMax + 2, 0);
  int speedSwing = dndSignedRoomMod() * 8;
  int mn = (int)moveMin - speedSwing;
  int mx = (int)moveMax + speedSwing;
  if (mn < 220) mn = 220;
  if (mx < mn + 100) mx = mn + 100;
  if (mx > 5000) mx = 5000;
  e.moveMinMs = (uint16_t)mn;
  e.moveMaxMs = (uint16_t)mx;
  e.nextMoveMs = millis() + (uint32_t)random(e.moveMinMs, e.moveMaxMs + 1U);
  e.alive = true;
}

static void dndGenerateRoom(bool announce) {
  dndClearEnemies();
  for (uint8_t y=0; y<DND_ROOM_H; ++y) {
    for (uint8_t x=0; x<DND_ROOM_W; ++x) {
      dndMap[y][x] = (x==0 || y==0 || x==DND_ROOM_W-1 || y==DND_ROOM_H-1) ? '#' : '.';
    }
    dndMap[y][DND_ROOM_W] = '\0';
  }

  // Fresh entry point every room. Old geometry is intentionally discarded.
  dndPlayerX = (int8_t)random(2, DND_ROOM_W-2);
  dndPlayerY = (int8_t)random(2, DND_ROOM_H-2);

  // Scatter short wall scars/pillars while keeping a generous open-room feel.
  uint8_t scars = (uint8_t)(10 + (dndRoomNumber % 10));
  for (uint8_t i=0;i<scars;++i) {
    int x = (int)random(2, DND_ROOM_W-2);
    int y = (int)random(2, DND_ROOM_H-2);
    int len = (int)random(1, 5);
    bool horiz = random(2) == 0;
    for (int j=0;j<len;++j) {
      int xx = x + (horiz ? j : 0);
      int yy = y + (horiz ? 0 : j);
      if (xx>0 && xx<DND_ROOM_W-1 && yy>0 && yy<DND_ROOM_H-1 &&
          abs(xx-dndPlayerX)+abs(yy-dndPlayerY) > 3) dndMap[yy][xx] = '#';
    }
  }

  // 2-4 one-way exits. Stepping through any one destroys this room and creates
  // the next random room. No return edge is stored.
  uint8_t doors = (uint8_t)random(2,5);
  for (uint8_t i=0;i<doors;++i) {
    uint8_t side = (uint8_t)random(4);
    if (side == 0) dndMap[0][random(2,DND_ROOM_W-2)] = '+';
    else if (side == 1) dndMap[DND_ROOM_H-1][random(2,DND_ROOM_W-2)] = '+';
    else if (side == 2) dndMap[random(2,DND_ROOM_H-2)][0] = '+';
    else dndMap[random(2,DND_ROOM_H-2)][DND_ROOM_W-1] = '+';
  }

  // Interactive content scales in both frequency and stats with depth.
  dndPlaceTile('c', (uint8_t)random(1,4));
  dndPlaceTile('^', (uint8_t)random(1,5));
  dndPlaceTile('$', (uint8_t)random(0,3));
  dndPlaceTile('!', (uint8_t)random(0,3));
  if (random(100) < 35) dndPlaceTile('w', 1);

  uint8_t enemyCount = (uint8_t)(3 + (dndRoomNumber / 8));
  if (enemyCount > DND_ENEMY_COUNT) enemyCount = DND_ENEMY_COUNT;
  for (uint8_t i=0;i<enemyCount;++i) {
    uint8_t kind = (uint8_t)random(100);
    if (kind < 40) dndBuildEnemy(i, 'r', "RAT", 5, 9, 1, 4, 520, 900);
    else if (kind < 75) dndBuildEnemy(i, 'g', "GOBLIN", 9, 11, 2, 6, 820, 1350);
    else dndBuildEnemy(i, 's', "SKELETON", 12, 12, 3, 7, 1050, 1700);
  }

  dndUpdateCamera();
  if (announce) {
    dndQueue("ROOM " + String(dndRoomNumber));
    dndQueue("DEPTH MOD +/-" + String(dndRoomNumber));
  }
}

static void dndNextRoom() {
  if (dndRoomNumber < 65535) dndRoomNumber++;
  if (dndRoomNumber > dndDeepestRoom) dndDeepestRoom = dndRoomNumber;
  dndGenerateRoom(true);
}

static void dndGenerateWeapon() {
  static const char* const names[] = {"IRON SWORD", "DAGGER", "AXE", "SPEAR", "MACE"};
  const char *name = names[random(5)];
  int baseMin = 2, baseMax = 6;
  if (String(name) == "DAGGER") { baseMin=1; baseMax=5; }
  else if (String(name) == "AXE") { baseMin=3; baseMax=8; }
  else if (String(name) == "SPEAR") { baseMin=2; baseMax=7; }
  else if (String(name) == "MACE") { baseMin=3; baseMax=7; }

  DndWeapon w;
  w.name = String(name);
  w.damageMin = dndScaled(baseMin, 1);
  w.damageMax = dndScaled(baseMax, w.damageMin);
  w.hitBonus = dndScaled(0, -20);
  w.foundRoom = dndRoomNumber;
  dndWeapon = w;
  dndQueue("FOUND " + dndWeapon.name);
  dndQueue("DMG " + String(dndWeapon.damageMin) + "-" + String(dndWeapon.damageMax));
  dndQueue("HIT " + String(dndWeapon.hitBonus));
}

static void dndDamagePlayer(int amount, const String &source) {
  if (amount < 0) amount = 0;
  dndHp -= amount;
  if (dndHp < 0) dndHp = 0;
  dndQueue(source + " HIT");
  dndQueue("DAMAGE " + String(amount));
  if (dndHp <= 0) {
    dndQueue("YOU FALL");
    dndGold /= 2U;
    dndRoomNumber = 1;
    dndHp = dndMaxHp;
    dndGenerateRoom(false);
    dndQueue("BACK TO ROOM 1");
  }
}

static void dndAttackEnemy(uint8_t idx, const String &verb) {
  if (idx >= DND_ENEMY_COUNT || !dndEnemies[idx].alive) return;
  DndEnemy &e = dndEnemies[idx];
  int roll = (int)random(1,21);
  int total = roll + dndStrength + dndWeapon.hitBonus;
  dndQueue(verb + " " + String(e.name));
  dndQueue("ROLL " + String(roll));
  dndQueue("TOTAL " + String(total));
  if (roll == 1 || total < e.ac) { dndQueue("MISS AC " + String(e.ac)); return; }
  int dmg = (int)random(dndWeapon.damageMin, dndWeapon.damageMax + 1) + (dndStrength / 2);
  if (roll == 20) { dmg *= 2; dndQueue("CRITICAL"); }
  e.hp -= dmg;
  dndQueue("DAMAGE " + String(dmg));
  if (e.hp <= 0) {
    e.alive = false;
    dndXp += e.xpReward;
    dndGold += e.goldReward;
    dndQueue(String(e.name) + " DOWN");
    dndQueue("+" + String(e.xpReward) + " XP");
    dndQueue("+" + String(e.goldReward) + " GOLD");
  }
}

static void dndAttackDirection(int8_t dx, int8_t dy) {
  dndAttackArmedUntilMs = 0;
  int8_t tx = dndPlayerX + dx;
  int8_t ty = dndPlayerY + dy;
  dndQueue("ATTACK");
  int8_t ei = dndEnemyAt(tx,ty);
  if (ei >= 0) dndAttackEnemy((uint8_t)ei,"ATTACK");
  else dndQueue("SWING AIR");
}

static void dndInteractTile(int8_t x, int8_t y) {
  int8_t ei = dndEnemyAt(x,y);
  if (ei >= 0) { dndAttackEnemy((uint8_t)ei,"BUMP"); return; }
  char &tile = dndMap[(uint8_t)y][(uint8_t)x];

  if (tile == '+') {
    dndQueue("THROUGH DOOR");
    dndNextRoom();
    return;
  }
  if (tile == 'c') {
    int difficulty = dndScaled(10 + (dndRoomNumber/3), 2);
    int roll = (int)random(1,21) + dndDexterity;
    dndQueue("OPEN CHEST"); dndQueue("ROLL " + String(roll));
    if (roll >= difficulty) {
      int loot = (int)random(100);
      tile = loot < 35 ? 'w' : (loot < 72 ? '$' : '!');
      dndQueue("CHEST OPEN");
    } else dndQueue("LOCK " + String(difficulty));
    return;
  }
  if (tile == '^') {
    int difficulty = dndScaled(12 + (dndRoomNumber/4), 3);
    int total = (int)random(1,21) + dndDexterity;
    int damage = dndScaled(4 + (dndRoomNumber/4), 1);
    tile = '.';
    dndQueue("TRAP " + String(difficulty));
    if (total < difficulty) dndDamagePlayer(damage,"TRAP");
    else dndQueue("DODGED");
    return;
  }
  if (tile == '$') {
    int g = dndScaled(8 + (dndRoomNumber/2), 1);
    dndGold += (uint32_t)g;
    tile='.'; dndPlayerX=x; dndPlayerY=y;
    dndQueue("+" + String(g) + " GOLD");
    return;
  }
  if (tile == '!') {
    int heal = dndScaled(6 + (dndRoomNumber/3), 1);
    dndHp += heal; if (dndHp > dndMaxHp) dndHp = dndMaxHp;
    tile='.'; dndPlayerX=x; dndPlayerY=y;
    dndQueue("HEAL " + String(heal));
    return;
  }
  if (tile == 'w') {
    tile='.'; dndPlayerX=x; dndPlayerY=y;
    dndGenerateWeapon();
    return;
  }
  dndPlayerX=x; dndPlayerY=y;
}

static void dndMovePlayer(int8_t dx, int8_t dy) {
  int8_t nx = dndPlayerX + dx;
  int8_t ny = dndPlayerY + dy;
  if (!dndWalkable(nx,ny)) { dndQueue("WALL"); return; }
  dndInteractTile(nx,ny);
}

static void dndServiceEnemies() {
  if (dndScreen != DND_PLAY) return;
  uint32_t now = millis();
  for (uint8_t i=0;i<DND_ENEMY_COUNT;++i) {
    DndEnemy &e=dndEnemies[i];
    if (!e.alive || (int32_t)(now-e.nextMoveMs)<0) continue;
    e.nextMoveMs = now + (uint32_t)random(e.moveMinMs,e.moveMaxMs+1U);
    int dxp=dndPlayerX-e.x, dyp=dndPlayerY-e.y;
    if (abs(dxp)+abs(dyp)==1) {
      int raw=(int)random(1,21);
      int total=raw+e.hitBonus+(e.dex/3);
      dndQueue(String(e.name)+" ATTACK");
      dndQueue("ROLL "+String(total));
      if (total >= dndArmorClass) {
        int dmg=(int)random(e.damageMin,e.damageMax+1);
        dndDamagePlayer(dmg,String(e.name));
      } else dndQueue("MISS");
      continue;
    }
    int8_t dx=0,dy=0;
    bool chase=abs(dxp)+abs(dyp)<=10;
    if (chase) {
      if (abs(dxp)>=abs(dyp) && dxp!=0) dx=dxp>0?1:-1;
      else if (dyp!=0) dy=dyp>0?1:-1;
    } else {
      uint8_t r=(uint8_t)random(4);
      dx=r==0?1:(r==1?-1:0); dy=r==2?1:(r==3?-1:0);
    }
    int8_t nx=e.x+dx, ny=e.y+dy;
    if (!dndWalkable(nx,ny)) continue;
    if (nx==dndPlayerX && ny==dndPlayerY) continue;
    if (dndEnemyAt(nx,ny)>=0) continue;
    char t=dndMap[(uint8_t)ny][(uint8_t)nx];
    if (t=='c'||t=='^'||t=='$'||t=='!'||t=='w'||t=='+') continue;
    e.x=nx; e.y=ny;
  }
}

static String dndMenuWindow(uint8_t idx) {
  String s=String(idx==dndMenuIndex?">":" ")+DND_MENU_ITEMS[idx];
  uint16_t off=(idx==dndMenuIndex)?dndMenuMarquee:0;
  return dndWindow(s,off,21);
}

static void dndDrawMenu() {
  uint8_t first=dndMenuIndex>1?dndMenuIndex-1:0;
  if (first>DND_MENU_COUNT-3) first=DND_MENU_COUNT-3;
  dndRenderFull(dndMenuWindow(first),dndMenuWindow(first+1),dndMenuWindow(first+2),"A ENTER B BACK");
}

static void dndDrawSymbols() {
  String title=String(DND_SYMBOL_GLYPHS[dndSymbolIndex])+" "+DND_SYMBOL_NAMES[dndSymbolIndex];
  dndRenderFull("SYMBOLS",dndWindow(title,dndMenuMarquee,21),
                String(dndSymbolIndex+1)+"/"+String(DND_SYMBOL_COUNT),"UD MOVE B BACK");
}

static void dndDrawInfo() {
  dndRenderFull(dndWindow(dndInfoTitle,dndMenuMarquee,21),
                dndWindow(dndInfoBody,dndMenuMarquee,21),"","B BACK");
}

static void dndOpenMenu() {
  dndScreen=DND_MENU; dndMenuIndex=0; dndMenuMarquee=0; dndMenuMarqueeMs=millis();
  dndDrawMenu();
}

static void dndStartGame() {
  dndHp=dndMaxHp=18;
  dndStrength=3; dndDexterity=2; dndArmorClass=12;
  dndXp=0; dndGold=0; dndLevel=1; dndKeys=0;
  dndRoomNumber=1; dndDeepestRoom=1;
  dndWeapon={"IRON SWORD",2,6,0,1};
  dndScreen=DND_PLAY;
  dndEventHead=dndEventTail=0;
  dndCurrentEvent="EXPLORE";
  dndEventUntilMs=millis()+700UL;
  dndEventMarquee=0; dndStatusFirst=0; dndStatusRotateMs=millis();
  dndAttackArmedUntilMs=0;
  for (uint8_t i=0;i<3;++i) { dndStatusMarquee[i]=0; dndStatusMarqueeMs[i]=millis(); }
  dndGenerateRoom(false);
  dndQueue("DND BEGINS");
  dndQueue("ROOM 1 MOD +/-1");
  dndDrawPlay();
}

static void drawDndPlaceholder() {
  dndStartGame();
}

static void dndHandleInput(Input in) {
  if (dndScreen==DND_PLAY) {
    if (in==BKEY) { dndOpenMenu(); return; }
    if (in==AKEY) {
      dndAttackArmedUntilMs=millis()+700UL;
      dndCurrentEvent="AIM"; dndEventMarquee=0; dndEventUntilMs=millis()+700UL;
      dndDrawPlay(); return;
    }
    bool armed=(int32_t)(dndAttackArmedUntilMs-millis())>0;
    if (in==UP) { if(armed)dndAttackDirection(0,-1); else dndMovePlayer(0,-1); }
    else if (in==DOWN) { if(armed)dndAttackDirection(0,1); else dndMovePlayer(0,1); }
    else if (in==LEFT) { if(armed)dndAttackDirection(-1,0); else dndMovePlayer(-1,0); }
    else if (in==RIGHT) { if(armed)dndAttackDirection(1,0); else dndMovePlayer(1,0); }
    dndDrawPlay(); return;
  }

  if (dndScreen==DND_MENU) {
    if (in==BKEY) { dndScreen=DND_PLAY; dndDrawPlay(); return; }
    if (in==UP) dndMenuIndex=(uint8_t)((dndMenuIndex+DND_MENU_COUNT-1U)%DND_MENU_COUNT);
    else if (in==DOWN) dndMenuIndex=(uint8_t)((dndMenuIndex+1U)%DND_MENU_COUNT);
    else if (in==AKEY) {
      if (dndMenuIndex==0) {
        dndInfoTitle="CHARACTER";
        dndInfoBody="ROOM "+String(dndRoomNumber)+" HP "+String(dndHp)+"/"+String(dndMaxHp)+
                    " STR "+String(dndStrength)+" DEX "+String(dndDexterity)+" AC "+String(dndArmorClass);
        dndScreen=DND_INFO; dndMenuMarquee=0; dndDrawInfo(); return;
      }
      if (dndMenuIndex==1) {
        dndInfoTitle="INVENTORY";
        dndInfoBody=dndWeapon.name+" "+String(dndWeapon.damageMin)+"-"+String(dndWeapon.damageMax)+
                    " HIT "+String(dndWeapon.hitBonus)+" GOLD "+String(dndGold);
        dndScreen=DND_INFO; dndMenuMarquee=0; dndDrawInfo(); return;
      }
      if (dndMenuIndex==2) {
        dndScreen=DND_SYMBOLS; dndSymbolIndex=0; dndMenuMarquee=0; dndDrawSymbols(); return;
      }
      if (dndMenuIndex==3) { enterBloomSystemMenu(); return; }
    }
    dndMenuMarquee=0; dndMenuMarqueeMs=millis(); dndDrawMenu(); return;
  }

  if (dndScreen==DND_SYMBOLS) {
    if (in==BKEY) { dndScreen=DND_MENU; dndMenuMarquee=0; dndDrawMenu(); return; }
    if (in==UP) dndSymbolIndex=(uint8_t)((dndSymbolIndex+DND_SYMBOL_COUNT-1U)%DND_SYMBOL_COUNT);
    else if (in==DOWN) dndSymbolIndex=(uint8_t)((dndSymbolIndex+1U)%DND_SYMBOL_COUNT);
    dndMenuMarquee=0; dndMenuMarqueeMs=millis(); dndDrawSymbols(); return;
  }

  if (dndScreen==DND_INFO) {
    if (in==BKEY || in==AKEY) { dndScreen=DND_MENU; dndMenuMarquee=0; dndDrawMenu(); }
    return;
  }
}

static void dndServiceGame() {
  if (uiMode!=DND_PLACEHOLDER) return;
  if (dndScreen==DND_PLAY) {
    dndServiceEventQueue(); dndServiceHudScroll(); dndServiceEnemies();
    uint32_t now=millis();
    if (now-dndLastRenderMs>=120UL) { dndLastRenderMs=now; dndDrawPlay(); }
    return;
  }
  uint32_t now=millis();
  if (now-dndMenuMarqueeMs>=320UL) {
    dndMenuMarqueeMs=now; dndMenuMarquee++;
    if (dndScreen==DND_MENU) dndDrawMenu();
    else if (dndScreen==DND_SYMBOLS) dndDrawSymbols();
    else if (dndScreen==DND_INFO) dndDrawInfo();
  }
}

'''


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_dnd_infinite_rooms_depth_scaling.py <bloompetz_v0_1.ino>")
    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"firmware not found: {p}")
    s = p.read_text()
    if MARKER in s:
        print("Infinite-room/depth DND patch already applied.")
        return
    start = s.find(START)
    if start < 0:
        raise SystemExit("DND playable start marker missing; refusing to guess")
    end = s.find(END, start + len(START))
    if end < 0:
        raise SystemExit("USB host-time marker after DND block missing; refusing to guess")

    # Validate current evolved DND before replacing it.
    required = [
        "static void dndServiceGame()",
        "static void dndHandleInput(Input in)",
        "static void dndRenderFull(",
        "DND_PLACEHOLDER",
    ]
    chunk = s[start:end]
    missing = [x for x in required if x not in chunk]
    if missing:
        raise SystemExit("current DND block missing expected anchors: " + ", ".join(missing))

    s = s[:start] + ENGINE + s[end:]
    p.write_text(s)
    print(f"Infinite DND rooms + room-depth scaling applied: {p}")
    print("Room buffer: 30x16; camera: 14x4; HUD: 7x4; doors are one-way/disposable.")
    print("ROOM N independently modifies generated enemy/entity/loot/weapon values by +/-N.")
    print("Compile before flash; this is a major DND engine replacement.")


if __name__ == "__main__":
    main()
