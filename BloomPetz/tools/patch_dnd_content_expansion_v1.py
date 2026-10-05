#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_dnd_content_expansion_v1.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_DND_CONTENT_EXPANSION_V1"
if marker in s:
    print("DND content expansion already present")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".pre_dnd_content_expansion_v1")
if not backup.exists():
    backup.write_text(s)

# -----------------------------------------------------------------------------
# 1) 48 enemy species.  Keep simultaneous actor count unchanged; this expands
#    the species/content pool only.
# -----------------------------------------------------------------------------
anchor = '''struct DndEnemy {
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
'''
if anchor not in s:
    raise SystemExit("DndEnemy struct anchor not found")

enemy_block = anchor + r'''

// BLOOM_DND_CONTENT_EXPANSION_V1
// 48 species; only the existing small actor array is instantiated at once.
struct DndEnemyDef {
  char glyph;
  const char *name;
  uint8_t tier;
  int16_t hp;
  int16_t ac;
  int16_t dmgMin;
  int16_t dmgMax;
  uint16_t moveMin;
  uint16_t moveMax;
};

static const DndEnemyDef DND_ENEMY_CATALOG[48] = {
  {'r',"RAT",0,5,9,1,4,520,900},
  {'b',"BAT",0,4,10,1,3,360,650},
  {'s',"SLIME",0,7,8,1,3,850,1350},
  {'g',"GOBLIN",0,9,11,2,6,820,1350},
  {'k',"KOBOLD",0,8,11,2,5,720,1180},
  {'w',"WOLF",0,10,11,2,6,520,900},
  {'p',"SPIDER",0,7,12,1,5,430,800},
  {'z',"ZOMBIE",0,12,9,2,6,1050,1750},

  {'s',"SKELETON",1,12,12,3,7,1050,1700},
  {'o',"ORC",1,16,12,3,8,900,1450},
  {'h',"HOBGOBLIN",1,15,13,3,7,760,1260},
  {'c',"CULTIST",1,13,12,2,8,820,1380},
  {'m',"MIMIC",1,18,11,3,9,1100,1750},
  {'v',"VIPER",1,11,13,2,7,430,760},
  {'f',"FUNGUS",1,17,10,2,7,1200,1900},
  {'d',"DARKLING",1,14,14,3,8,650,1080},

  {'t',"TROLL",2,26,13,4,11,1150,1800},
  {'O',"OGRE",2,30,12,5,13,1250,1950},
  {'G',"GHOUL",2,22,14,4,10,720,1200},
  {'W',"WRAITH",2,20,15,4,11,560,980},
  {'e',"ELEMENTAL",2,24,15,5,12,760,1250},
  {'n',"NAGA",2,25,14,4,12,690,1160},
  {'B',"BUGBEAR",2,27,14,5,12,860,1420},
  {'a',"ASSASSIN",2,19,16,5,12,390,720},

  {'M',"MINOTAUR",3,38,15,6,15,880,1450},
  {'C',"CHIMERA",3,36,16,6,16,640,1080},
  {'L',"LICH",3,34,17,7,17,820,1380},
  {'D',"DEMON",3,40,17,7,18,650,1100},
  {'V',"VAMPIRE",3,35,18,6,17,500,880},
  {'Y',"WYVERN",3,42,16,7,18,580,1000},
  {'K',"DEATH KNIGHT",3,45,18,7,19,760,1260},
  {'H',"HYDRA",3,50,16,8,20,900,1450},

  {'R',"STONE GOLEM",4,62,19,9,22,1300,2050},
  {'F',"FROST GIANT",4,68,18,10,24,1150,1850},
  {'I',"INFERNAL",4,60,20,10,25,760,1260},
  {'P',"PHANTOM",4,52,21,9,23,430,790},
  {'Q',"QUEEN SPIDER",4,58,20,9,24,520,900},
  {'X',"VOID HORROR",4,70,21,11,27,650,1100},
  {'A',"ABOMINATION",4,76,19,11,28,980,1580},
  {'N',"NIGHTMARE",4,64,22,10,27,390,720},

  {'J',"JUGGERNAUT",5,88,21,12,31,950,1520},
  {'S',"STORM LORD",5,82,23,12,32,560,960},
  {'E',"ELDER LICH",5,78,24,13,34,720,1200},
  {'U',"UNDERKING",5,94,23,13,35,820,1340},
  {'Z',"VOID TITAN",5,110,24,14,38,960,1560},
  {'T',"ANCIENT DRAGON",5,120,25,15,40,660,1120},
  {'!',"CHAOS BEAST",5,105,25,15,39,520,920},
  {'*',"BLOOM WARDEN",5,128,26,16,42,620,1040}
};
static const uint8_t DND_ENEMY_SPECIES_COUNT = 48;
'''
s = s.replace(anchor, enemy_block, 1)

# Replace the 3-species spawn chooser with a 48-species tier-aware chooser.
old_spawn = '''    uint8_t kind = (uint8_t)random(100);
    if (kind < 40) dndBuildEnemy(i, 'r', "RAT", 5, 9, 1, 4, 520, 900);
    else if (kind < 75) dndBuildEnemy(i, 'g', "GOBLIN", 9, 11, 2, 6, 820, 1350);
    else dndBuildEnemy(i, 's', "SKELETON", 12, 12, 3, 7, 1050, 1700);
'''
new_spawn = '''    // 48-species content pool. Deeper rooms unlock higher tiers, while a
    // little under-tier randomness keeps old creatures appearing later.
    uint8_t maxTier = (uint8_t)(dndRoomNumber / 8U);
    if (maxTier > 5U) maxTier = 5U;
    uint8_t wantedTier = maxTier;
    if (maxTier > 0U && random(100) < 28) wantedTier = (uint8_t)random(maxTier + 1U);
    uint8_t choices[48];
    uint8_t choiceCount = 0;
    for (uint8_t eidx=0; eidx<DND_ENEMY_SPECIES_COUNT; ++eidx) {
      if (DND_ENEMY_CATALOG[eidx].tier == wantedTier) choices[choiceCount++] = eidx;
    }
    uint8_t pick = choices[choiceCount ? (uint8_t)random(choiceCount) : 0];
    const DndEnemyDef &def = DND_ENEMY_CATALOG[pick];
    dndBuildEnemy(i, def.glyph, def.name, def.hp, def.ac,
                  def.dmgMin, def.dmgMax, def.moveMin, def.moveMax);
'''
if old_spawn not in s:
    raise SystemExit("3-enemy spawn chooser anchor not found")
s = s.replace(old_spawn, new_spawn, 1)

# -----------------------------------------------------------------------------
# 2) 48 symbol/entity reference entries.
# -----------------------------------------------------------------------------
s, count = re.subn(
    r'(static\s+const\s+uint8_t\s+DND_SYMBOL_COUNT\s*=\s*)\d+(\s*;)',
    r'\g<1>48\g<2>', s, count=1)
if count == 0:
    # Some generations use a preprocessor constant.
    s, count = re.subn(r'(#define\s+DND_SYMBOL_COUNT\s+)\d+', r'\g<1>48', s, count=1)
if count == 0:
    raise SystemExit("DND_SYMBOL_COUNT declaration not found")

old_symbols = '''static const char DND_SYMBOL_GLYPHS[DND_SYMBOL_COUNT] = {
  '@', '#', '.', '+', '/', '^', 'c', '$', '!', 'w', 'r', 'g', 's', 'x', '*'
};
static const char* const DND_SYMBOL_NAMES[DND_SYMBOL_COUNT] = {
  "PLAYER", "WALL", "FLOOR", "DOOR TO NEXT ROOM", "OPEN DOOR", "TRAP",
  "CHEST", "GOLD", "POTION", "WEAPON", "RAT", "GOBLIN", "SKELETON", "HIT", "MAGIC"
};
'''
new_symbols = '''static const char DND_SYMBOL_GLYPHS[DND_SYMBOL_COUNT] = {
  '@','#','.','+','/','^','c','$','!','w','k','?','~','*','x','r',
  'b','s','g','K','W','p','z','o','h','C','m','v','f','d','t','O',
  'G','R','e','n','B','a','M','L','D','V','Y','H','X','T','Z','&'
};
static const char* const DND_SYMBOL_NAMES[DND_SYMBOL_COUNT] = {
  "PLAYER","WALL","FLOOR","NEXT ROOM DOOR","OPEN DOOR","TRAP","CHEST","GOLD",
  "POTION","WEAPON","KEY","MYSTERY","WATER OR HAZARD","MAGIC OR RELIC","HIT MARK","RAT",
  "BAT","SLIME","GOBLIN","KOBOLD","WOLF","SPIDER","ZOMBIE","ORC",
  "HOBGOBLIN","CULTIST","MIMIC","VIPER","FUNGUS","DARKLING","TROLL","OGRE",
  "GHOUL","STONE GOLEM","ELEMENTAL","NAGA","BUGBEAR","ASSASSIN","MINOTAUR","LICH",
  "DEMON","VAMPIRE","WYVERN","HYDRA","VOID HORROR","ANCIENT DRAGON","VOID TITAN","SPECIAL ENTITY"
};
'''
if old_symbols not in s:
    raise SystemExit("15-symbol arrays anchor not found")
s = s.replace(old_symbols, new_symbols, 1)

# -----------------------------------------------------------------------------
# 3) 48 room themes layered over the existing 8 geometry generators.
# -----------------------------------------------------------------------------
room_names_anchor = '''static const char* const DND_ROOM_STYLE_NAMES[8] = {
  "RUINS", "HALL", "CORRIDORS", "CHAMBERS",
  "TRAP RUN", "TREASURE", "DEN", "VOID"
};
'''
if room_names_anchor not in s:
    raise SystemExit("room style names anchor not found")
room_theme_block = room_names_anchor + r'''
static const char* const DND_ROOM_THEME_NAMES[48] = {
  "CRUMBLING RUINS","TORCH HALL","BROKEN CORRIDORS","DUST CHAMBERS","SPIKE RUN","COIN VAULT","RAT DEN","BLACK VOID",
  "MOSS RUINS","BANNER HALL","BONE CORRIDORS","CRYPT CHAMBERS","BLADE RUN","JEWEL VAULT","GOBLIN DEN","ECHO VOID",
  "FROST RUINS","IRON HALL","WEB CORRIDORS","MUMMY CHAMBERS","FIRE RUN","RELIC VAULT","WOLF DEN","STARLESS VOID",
  "SUNKEN RUINS","ROYAL HALL","ROOT CORRIDORS","RUNE CHAMBERS","POISON RUN","DRAGON VAULT","TROLL DEN","DEEP VOID",
  "ASH RUINS","MIRROR HALL","SHADOW CORRIDORS","BLOOD CHAMBERS","CHAOS RUN","ANCIENT VAULT","DEMON DEN","DREAM VOID",
  "BLOOM RUINS","CROWN HALL","CRYSTAL CORRIDORS","WARDEN CHAMBERS","VOID RUN","FINAL VAULT","TITAN DEN","BLOOM VOID"
};
static uint8_t dndRoomThemeIndex = 0;
'''
s = s.replace(room_names_anchor, room_theme_block, 1)

# Set one of 48 themes each room while retaining the proven geometry system.
gen_anchor = '''static void dndGenerateRoom(bool announce) {
  dndClearEnemies();
'''
if gen_anchor not in s:
    raise SystemExit("dndGenerateRoom anchor not found")
s = s.replace(gen_anchor, '''static void dndGenerateRoom(bool announce) {
  dndClearEnemies();
  // Theme is content flavor; geometry still uses the proven 8-style engine.
  dndRoomThemeIndex = (uint8_t)((dndRoomNumber - 1U + (uint16_t)random(48)) % 48U);
''', 1)

# Announce theme as part of room entry.
old_announce = '''    dndQueue("ROOM " + String(dndRoomNumber));
    dndQueue("DEPTH MOD +/-" + String(dndRoomNumber));
'''
new_announce = '''    dndQueue("ROOM " + String(dndRoomNumber));
    dndQueue(String(DND_ROOM_THEME_NAMES[dndRoomThemeIndex]));
    dndQueue("DEPTH MOD +/-" + String(dndRoomNumber));
'''
if old_announce not in s:
    raise SystemExit("room announce anchor not found")
s = s.replace(old_announce, new_announce, 1)

# -----------------------------------------------------------------------------
# 4) Player progression: HP is no longer permanently 18. Level from XP and
#    room milestones increases max HP, STR, DEX, and AC gradually.
# -----------------------------------------------------------------------------
status_anchor = '''static String dndStatusText(uint8_t idx) {
'''
if status_anchor not in s:
    raise SystemExit("dndStatusText anchor not found")
progress_helpers = r'''static uint16_t dndLevelFromXp(uint32_t xp) {
  // Smooth tiny-RPG curve: level 2 at 40 XP, then increasingly expensive.
  uint16_t level = 1;
  uint32_t need = 40;
  uint32_t spent = 0;
  while (level < 99 && xp >= spent + need) {
    spent += need;
    level++;
    need += 20U + (uint32_t)level * 8U;
  }
  return level;
}

static void dndCheckLevelUp() {
  uint16_t target = dndLevelFromXp(dndXp);
  while (dndLevel < target) {
    dndLevel++;
    int hpGain = 2 + (int)(dndLevel % 3U);
    dndMaxHp += hpGain;
    dndHp += hpGain;
    if ((dndLevel % 2U) == 0U) dndStrength++;
    if ((dndLevel % 3U) == 0U) dndDexterity++;
    if ((dndLevel % 4U) == 0U) dndArmorClass++;
    dndQueue("LEVEL " + String(dndLevel));
    dndQueue("MAX HP +" + String(hpGain));
  }
}

'''
s = s.replace(status_anchor, progress_helpers + status_anchor, 1)

# Enemy kill immediately checks level progression.
old_kill = '''    dndXp += e.xpReward;
    dndGold += e.goldReward;
    dndQueue(String(e.name) + " DOWN");
'''
new_kill = '''    dndXp += e.xpReward;
    dndGold += e.goldReward;
    dndCheckLevelUp();
    dndQueue(String(e.name) + " DOWN");
'''
if old_kill not in s:
    raise SystemExit("enemy reward anchor not found")
s = s.replace(old_kill, new_kill, 1)

# New game still starts at 18, but no longer stays capped there; it grows.
old_start = '''  dndHp=dndMaxHp=18;
  dndStrength=3; dndDexterity=2; dndArmorClass=12;
'''
new_start = '''  // 18 HP is the level-1 starting point, not a permanent cap.
  dndHp=dndMaxHp=18;
  dndStrength=3; dndDexterity=2; dndArmorClass=12;
'''
if old_start not in s:
    raise SystemExit("new-game HP anchor not found")
s = s.replace(old_start, new_start, 1)

# Add theme and species-pool information to CHARACTER info without adding a new UI.
old_char = '''        dndInfoBody="ROOM "+String(dndRoomNumber)+" HP "+String(dndHp)+"/"+String(dndMaxHp)+
                    " STR "+String(dndStrength)+" DEX "+String(dndDexterity)+" AC "+String(dndArmorClass);
'''
new_char = '''        dndInfoBody="LV "+String(dndLevel)+" ROOM "+String(dndRoomNumber)+" HP "+String(dndHp)+"/"+String(dndMaxHp)+
                    " STR "+String(dndStrength)+" DEX "+String(dndDexterity)+" AC "+String(dndArmorClass)+
                    " "+String(DND_ROOM_THEME_NAMES[dndRoomThemeIndex]);
'''
if old_char in s:
    s = s.replace(old_char, new_char, 1)

p.write_text(s)
print("PATCHED DND CONTENT EXPANSION V1")
print("  48 enemy species")
print("  48 symbol/entity reference entries")
print("  48 room themes over proven 8 geometry archetypes")
print("  player level/HP/stat progression from XP")
print("  simultaneous enemy count unchanged")
print("patched:", p)
