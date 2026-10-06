#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_dnd_character_stats_v1.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_DND_CHARACTER_STATS_V1"
if marker in s:
    print("DND Character stats repair already present")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".pre_dnd_character_stats_v1")
if not backup.exists():
    backup.write_text(s)

# Require the 288-item equipment generation we are repairing.
if "DND_EQUIP_CATEGORY_NAMES" not in s or "DND_EQUIP_CATEGORIES" not in s:
    raise SystemExit("288-item DND equipment system not found")

# 1) Character menu now has STATS plus the seven equipment/use categories.
old = '''static const uint8_t DND_EQUIP_CATEGORY_COUNT = 7;
static const char* const DND_EQUIP_CATEGORY_NAMES[DND_EQUIP_CATEGORY_COUNT] = {
  "WEAPON","ARMOR","SHIELD","RING 1","RING 2","CHARM","CONSUMABLES"
};'''
new = '''// BLOOM_DND_CHARACTER_STATS_V1
static const uint8_t DND_EQUIP_CATEGORY_COUNT = 8;
static const char* const DND_EQUIP_CATEGORY_NAMES[DND_EQUIP_CATEGORY_COUNT] = {
  "STATS","WEAPON","ARMOR","SHIELD","RING 1","RING 2","CHARM","CONSUMABLES"
};'''
if old not in s:
    raise SystemExit("Character category list anchor not found")
s = s.replace(old, new, 1)

# 2) Give Character stats its own DND screen.
s, n = re.subn(
    r'enum\s+DndScreen\s*:\s*uint8_t\s*\{([^}]*)\}',
    lambda m: 'enum DndScreen : uint8_t {' + (
        m.group(1).rstrip().rstrip(',') + ', DND_CHARACTER_STATS=8'
        if 'DND_CHARACTER_STATS' not in m.group(1) else m.group(1)
    ) + '}',
    s, count=1,
)
if n != 1:
    raise SystemExit("DndScreen enum not found")

# 3) Shift equipment category mapping by one because category 0 is now STATS.
start = s.find("static bool dndEquipOwnedItem(uint16_t id, uint8_t category) {")
end = s.find("static bool dndUseConsumable", start)
if start < 0 or end < 0:
    raise SystemExit("dndEquipOwnedItem block not found")
block = s[start:end]
repls = {
    "if (category==0 && type=='W')": "if (category==1 && type=='W')",
    "else if (category==1 && type=='A')": "else if (category==2 && type=='A')",
    "else if (category==2 && type=='D')": "else if (category==3 && type=='D')",
    "else if (category==3 && type=='R')": "else if (category==4 && type=='R')",
    "else if (category==4 && type=='R')": "else if (category==5 && type=='R')",
    "else if (category==5 && type=='C')": "else if (category==6 && type=='C')",
}
for a,b in repls.items():
    if a not in block:
        raise SystemExit(f"equipment mapping anchor not found: {a}")
    block = block.replace(a,b,1)
s = s[:start] + block + s[end:]

# Replace category type/equipped helper bodies wholesale.
def replace_function(src, name, body):
    m = re.search(r'static\s+[^\n]+\s+' + re.escape(name) + r'\s*\([^)]*\)\s*\{', src)
    if not m:
        raise SystemExit(f"function not found: {name}")
    ob = src.find('{', m.start())
    depth = 0
    i = ob
    while i < len(src):
        if src[i] == '{': depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[:ob+1] + "\n" + body.rstrip() + "\n" + src[i:]
        i += 1
    raise SystemExit(f"unterminated function: {name}")

s = replace_function(s, "dndCategoryType", '''  if (category==1) return 'W';
  if (category==2) return 'A';
  if (category==3) return 'D';
  if (category==4 || category==5) return 'R';
  if (category==6) return 'C';
  if (category==7) return 'H';
  return 0;''')

s = replace_function(s, "dndEquippedForCategory", '''  if (category==1) return dndEquipWeapon;
  if (category==2) return dndEquipArmor;
  if (category==3) return dndEquipShield;
  if (category==4) return dndEquipRing1;
  if (category==5) return dndEquipRing2;
  if (category==6) return dndEquipCharm;
  return DND_NO_ITEM;''')

# 4) Add a proper effective-stat Character sheet before category drawing.
anchor = "static String dndCharacterCategoryLine(uint8_t idx) {"
if anchor not in s:
    raise SystemExit("Character category line anchor not found")
stats_helpers = r'''static void dndDrawCharacterStats() {
  String row0 = "LV "+String(dndLevel)+" XP "+String(dndXp)+" RM "+String(dndRoomNumber);
  String row1 = "HP "+String(dndHp)+"/"+String(dndEffectiveMaxHp())+" AC "+String(dndEffectiveArmorClass());
  String row2 = "STR "+String(dndEffectiveStrength())+" DEX "+String(dndEffectiveDexterity())+" G "+String(dndGold);
  String row3 = dndWeapon.name+" "+String(dndWeapon.damageMin)+"-"+String(dndWeapon.damageMax)+" H"+String(dndWeapon.hitBonus)+" B BACK";
  dndRenderFull(dndWindow(row0,dndMenuMarquee,21),
                dndWindow(row1,dndMenuMarquee,21),
                dndWindow(row2,dndMenuMarquee,21),
                dndWindow(row3,dndMenuMarquee,21));
}

'''
s = s.replace(anchor, stats_helpers + anchor, 1)

# Category line: STATS has no equipped suffix; gear categories do.
old = '''  uint16_t eq=dndEquippedForCategory(idx);
  if (eq<DND_ITEM_COUNT) line += " "+String(DND_ITEM_CATALOG[eq].name);
  else if (idx<6) line += " -";'''
new = '''  uint16_t eq=dndEquippedForCategory(idx);
  if (idx>0 && idx<7 && eq<DND_ITEM_COUNT) line += " "+String(DND_ITEM_CATALOG[eq].name);
  else if (idx>0 && idx<7) line += " -";'''
if old not in s:
    raise SystemExit("Character category suffix anchor not found")
s = s.replace(old,new,1)

# Equip-list marker threshold shifted from <6 to equipment categories 1..6.
s = s.replace(
    '(dndEquippedForCategory(dndEquipCategory)==id && dndEquipCategory<6)',
    '(dndEquipCategory>0 && dndEquipCategory<7 && dndEquippedForCategory(dndEquipCategory)==id)',
    1,
)

# 5) Input behavior: A on STATS opens character sheet; A on others opens owned gear.
old = '''    else if (in==AKEY) { dndEquipOwnedIndex=0; dndScreen=DND_EQUIP_LIST; dndMenuMarquee=0; dndDrawEquipList(); return; }'''
new = '''    else if (in==AKEY) {
      if (dndEquipCategory==0) {
        dndScreen=DND_CHARACTER_STATS; dndMenuMarquee=0; dndMenuMarqueeMs=millis();
        dndDrawCharacterStats(); return;
      }
      dndEquipOwnedIndex=0; dndScreen=DND_EQUIP_LIST; dndMenuMarquee=0; dndDrawEquipList(); return;
    }'''
if old not in s:
    raise SystemExit("Character A-key handler anchor not found")
s = s.replace(old,new,1)

# New stats screen returns to Character categories.
anchor = "  if (dndScreen==DND_EQUIP_LIST) {"
if anchor not in s:
    raise SystemExit("DND equip-list handler anchor not found")
handler = r'''  if (dndScreen==DND_CHARACTER_STATS) {
    if (in==BKEY || in==AKEY) {
      dndScreen=DND_EQUIP_CATEGORIES; dndMenuMarquee=0; dndMenuMarqueeMs=millis();
      dndDrawCharacterCategories();
    }
    return;
  }

'''
s = s.replace(anchor, handler + anchor, 1)

# Marquee refresh for long weapon/stat rows while Character stats is open.
needle = "else if (dndScreen==DND_EQUIP_LIST) dndDrawEquipList();"
if needle not in s:
    raise SystemExit("DND equip-list redraw anchor not found")
s = s.replace(needle, needle + "\n    else if (dndScreen==DND_CHARACTER_STATS) dndDrawCharacterStats();", 1)

p.write_text(s)
print("RESTORED DND CHARACTER STATS V1")
print("  Character now starts with STATS, followed by 7 gear/use categories")
print("  STATS shows level/XP/room, HP, effective AC/STR/DEX, gold, weapon damage/hit")
print("  displayed combat stats include equipped gear bonuses")
print("  A or B returns from stats to Character categories")
print("patched:", p)
