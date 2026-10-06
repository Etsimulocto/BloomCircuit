#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_dnd_equipment_catalog_v2.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_DND_EQUIPMENT_CATALOG_V2"
if marker in s:
    print("DND equipment/catalog V2 already present")
    raise SystemExit(0)

required = [
    "BLOOM_DND_INVENTORY_SHOP_V1",
    "BLOOM_SYSTEM_UNIFIED_SAVE_V1",
    "struct DndItemDef",
    "static void dndHandleInput",
]
for token in required:
    if token not in s:
        raise SystemExit(f"required current-build marker not found: {token}")

backup = p.with_suffix(p.suffix + ".pre_dnd_equipment_catalog_v2")
if not backup.exists():
    backup.write_text(s)


def find_function(src: str, signature_regex: str):
    m = re.search(signature_regex, src)
    if not m:
        raise SystemExit(f"function not found: {signature_regex}")
    ob = src.find('{', m.start())
    if ob < 0:
        raise SystemExit(f"opening brace not found: {signature_regex}")
    depth = 0
    i = ob
    while i < len(src):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return m.start(), ob, i + 1
        i += 1
    raise SystemExit(f"closing brace not found: {signature_regex}")


def replace_body(src: str, signature_regex: str, body: str):
    _, ob, end = find_function(src, signature_regex)
    return src[:ob+1] + "\n" + body.rstrip() + "\n" + src[end-1:]


# -----------------------------------------------------------------------------
# 48 authored names in each of six item families = 288 catalog entries.
# Stats are emitted explicitly into the resulting firmware table.
# -----------------------------------------------------------------------------
WEAPONS = [
"RUSTY KNIFE","DAGGER","IRON SWORD","SHORT SWORD","HAND AXE","MACE","SPEAR","WAR AXE",
"LONG SWORD","CROSSBOW","BONE BLADE","SILVER SWORD","FROST BLADE","FLAME SWORD","VOID AXE","DRAGON BLADE",
"BRONZE SABER","HUNTER BOW","WAR HAMMER","TRIDENT","SCIMITAR","RAPIER","BATTLE STAFF","CLEAVER",
"MOON BLADE","SUN SPEAR","THORN WHIP","CRYSTAL MACE","STORM BOW","EMBER AXE","ICE SPEAR","SHADOW DAGGER",
"ROYAL SWORD","GIANT HAMMER","PHANTOM BLADE","RUNE STAFF","BLOOD AXE","STAR PIKE","CHAOS BOW","WARDEN MACE",
"TITAN SWORD","NIGHT REAPER","CELESTIAL SPEAR","INFERNO BLADE","ABYSS HAMMER","WORLD AXE","BLOOM EDGE","CROWN BLADE"]

ARMOR = [
"LEATHER CAP","LEATHER ARMOR","IRON HELM","CHAIN MAIL","IRON ARMOR","STEEL ARMOR","DRAGON SCALE","PADDED COAT",
"HIDE ARMOR","BRONZE MAIL","SCALE MAIL","RANGER COAT","SOLDIER MAIL","KNIGHT PLATE","MITHRIL MAIL","SILVER PLATE",
"FROST MAIL","FLAME MAIL","THORN MAIL","BONE ARMOR","ROYAL PLATE","RUNE ROBE","SHADOW COAT","CRYSTAL MAIL",
"STORM PLATE","EMBER MAIL","MOON ROBE","SUN PLATE","VOID MAIL","BLOOD PLATE","WARDEN ARMOR","PHANTOM MAIL",
"GIANT PLATE","DRAGON PLATE","DEMON MAIL","ANGEL ROBE","CHAOS PLATE","STAR ARMOR","TITAN MAIL","NIGHT PLATE",
"ABYSS ARMOR","CELESTIAL PLATE","INFERNO MAIL","WORLD PLATE","BLOOM MAIL","ANCIENT PLATE","CROWN ARMOR","WARDEN PLATE"]

SHIELDS = [
"WOOD SHIELD","IRON SHIELD","TOWER SHIELD","BUCKLER","BRONZE SHIELD","BONE SHIELD","ROUND SHIELD","KITE SHIELD",
"STEEL SHIELD","SPIKE SHIELD","RANGER SHIELD","SILVER SHIELD","FROST SHIELD","FLAME SHIELD","THORN SHIELD","RUNE SHIELD",
"MOON SHIELD","SUN SHIELD","CRYSTAL SHIELD","STORM SHIELD","EMBER SHIELD","SHADOW SHIELD","ROYAL SHIELD","DRAGON SHIELD",
"PHANTOM SHIELD","BLOOD SHIELD","VOID SHIELD","WARDEN SHIELD","GIANT SHIELD","DEMON SHIELD","ANGEL SHIELD","CHAOS SHIELD",
"STAR SHIELD","TITAN SHIELD","NIGHT SHIELD","ABYSS SHIELD","CELESTIAL SHIELD","INFERNO SHIELD","WORLD SHIELD","BLOOM SHIELD",
"ANCIENT SHIELD","CROWN SHIELD","MIRROR SHIELD","OBSIDIAN SHIELD","AETHER SHIELD","NOVA SHIELD","ETERNAL SHIELD","FINAL SHIELD"]

RINGS = [
"COPPER RING","LUCKY RING","RUBY RING","EMERALD RING","SAPPHIRE RING","SKULL RING","ROYAL SEAL","IRON RING",
"SILVER RING","GOLD RING","AGATE RING","ONYX RING","MOON RING","SUN RING","FROST RING","FLAME RING",
"THORN RING","BONE RING","RUNE RING","CRYSTAL RING","STORM RING","EMBER RING","SHADOW RING","DRAGON RING",
"PHANTOM RING","BLOOD RING","VOID RING","WARDEN RING","GIANT RING","DEMON RING","ANGEL RING","CHAOS RING",
"STAR RING","TITAN RING","NIGHT RING","ABYSS RING","CELESTIAL RING","INFERNO RING","WORLD RING","BLOOM RING",
"ANCIENT RING","CROWN RING","MIRROR RING","AETHER RING","NOVA RING","ETERNAL RING","FATE RING","FINAL RING"]

CHARMS = [
"GOBLIN TOOTH","BONE CHARM","MOON CHARM","SUN CHARM","ANCIENT IDOL","BLACK PEARL","STAR RELIC","VOID HEART",
"CROWN OF BLOOM","RAT TAIL","WOLF FANG","SPIDER EYE","ORC TUSK","TROLL STONE","WYVERN SCALE","DRAGON EYE",
"FROST RELIC","FLAME RELIC","THORN RELIC","RUNE RELIC","CRYSTAL RELIC","STORM RELIC","EMBER RELIC","SHADOW RELIC",
"ROYAL RELIC","PHANTOM RELIC","BLOOD RELIC","WARDEN RELIC","GIANT RELIC","DEMON RELIC","ANGEL RELIC","CHAOS RELIC",
"TITAN RELIC","NIGHT RELIC","ABYSS RELIC","CELESTIAL RELIC","INFERNO RELIC","WORLD RELIC","BLOOM RELIC","ANCIENT HEART",
"CROWN RELIC","MIRROR RELIC","OBSIDIAN IDOL","AETHER HEART","NOVA HEART","ETERNAL IDOL","FATE RELIC","FINAL RELIC"]

CONSUMABLES = [
"BANDAGE","RED POTION","BIG RED POTION","ELIXIR","PHOENIX TONIC","FULL RESTORE","HERB","HEALING HERB",
"MOSS TONIC","HONEY DRAUGHT","IRON TONIC","SILVER TONIC","FROST TONIC","FLAME TONIC","THORN TONIC","RUNE TONIC",
"MOON TONIC","SUN TONIC","CRYSTAL TONIC","STORM TONIC","EMBER TONIC","SHADOW TONIC","ROYAL TONIC","DRAGON TONIC",
"PHANTOM TONIC","BLOOD TONIC","VOID TONIC","WARDEN TONIC","GIANT TONIC","DEMON TONIC","ANGEL TONIC","CHAOS TONIC",
"STAR TONIC","TITAN TONIC","NIGHT TONIC","ABYSS TONIC","CELESTIAL TONIC","INFERNO TONIC","WORLD TONIC","BLOOM TONIC",
"ANCIENT TONIC","CROWN TONIC","MIRROR TONIC","AETHER TONIC","NOVA TONIC","ETERNAL TONIC","FATE TONIC","FINAL TONIC"]

for family in (WEAPONS, ARMOR, SHIELDS, RINGS, CHARMS, CONSUMABLES):
    if len(family) != 48:
        raise SystemExit("internal catalog error: every item family must contain exactly 48 names")


def row(name, typ, i):
    rarity = min(4, i // 10)
    if typ == 'W':
        price = 12 + i * 7 + rarity * 28
        dmin = 1 + i // 7 + rarity
        dmax = dmin + 3 + i // 5 + rarity
        hit = -1 + (i % 5) + rarity
        strength = i // 16
        dex = 1 if i % 9 in (2, 3, 4) else 0
        ac = hp = heal = 0
    elif typ == 'A':
        price = 14 + i * 8 + rarity * 32
        dmin = dmax = hit = heal = 0
        strength = 1 if i >= 36 and i % 3 == 0 else 0
        dex = -1 if i % 12 in (9, 10, 11) else 0
        ac = 1 + i // 8 + rarity
        hp = (i // 12) * 2 + rarity
    elif typ == 'D':
        price = 10 + i * 7 + rarity * 30
        dmin = dmax = heal = 0
        hit = -1 if i % 12 in (10, 11) else 0
        strength = 1 if i >= 32 and i % 5 == 0 else 0
        dex = 1 if i % 12 in (3, 4) else (-1 if i % 12 in (10, 11) else 0)
        ac = 1 + i // 10 + rarity
        hp = i // 16 + rarity
    elif typ == 'R':
        price = 18 + i * 9 + rarity * 38
        dmin = dmax = hit = heal = 0
        strength = (i % 4 == 0) + (1 if i >= 32 and i % 8 == 0 else 0)
        dex = (i % 4 == 1) + (1 if i >= 32 and i % 8 == 1 else 0)
        ac = 1 if i % 4 == 2 else (1 if i >= 40 else 0)
        hp = (2 + rarity * 2) if i % 4 == 3 else rarity
    elif typ == 'C':
        price = 22 + i * 10 + rarity * 42
        dmin = dmax = hit = heal = 0
        strength = rarity + (1 if i % 5 == 0 else 0)
        dex = rarity + (1 if i % 5 == 1 else 0)
        ac = rarity // 2 + (1 if i % 5 == 2 else 0)
        hp = 2 + rarity * 3 + (2 if i % 5 == 3 else 0)
    else:
        price = 8 + i * 5 + rarity * 20
        dmin = dmax = hit = strength = dex = ac = hp = 0
        heal = 5 + i * 2 + rarity * 8
        if name == "FULL RESTORE":
            heal = 9999
    return f'  {{"{name}",\'{typ}\',{price},{dmin},{dmax},{hit},{strength},{dex},{ac},{hp},{heal},{rarity}}}'

rows = []
for typ, names in [('W', WEAPONS), ('A', ARMOR), ('D', SHIELDS), ('R', RINGS), ('C', CHARMS), ('H', CONSUMABLES)]:
    rows.extend(row(name, typ, i) for i, name in enumerate(names))

catalog = ",\n".join(rows)

data_block = r'''// BLOOM_DND_EQUIPMENT_CATALOG_V2
struct DndItemDef {
  const char *name;
  char type;           // W weapon, A armor, D shield, R ring, C charm/relic, H consumable
  uint16_t basePrice;
  int16_t damageMin;
  int16_t damageMax;
  int16_t hitBonus;
  int16_t strBonus;
  int16_t dexBonus;
  int16_t acBonus;
  int16_t hpBonus;
  int16_t healAmount;
  uint8_t rarity;      // 0 common .. 4 legendary
};

static const DndItemDef DND_ITEM_CATALOG[] = {
''' + catalog + r'''
};
static const uint16_t DND_ITEM_COUNT = sizeof(DND_ITEM_CATALOG)/sizeof(DND_ITEM_CATALOG[0]);
static const uint16_t DND_INV_CAP = 288;
static const uint8_t DND_SHOP_COUNT = 4;
static const uint16_t DND_NO_ITEM = 0xFFFFU;

static uint16_t dndShop[DND_SHOP_COUNT] = {0,1,2,3};
static uint8_t dndShopIndex = 0;
static uint16_t dndShopRoom = 0;
static uint16_t dndInventory[DND_INV_CAP];
static uint16_t dndInventoryCount = 0;
static uint16_t dndInventoryIndex = 0;

static uint16_t dndEquipWeapon = DND_NO_ITEM;
static uint16_t dndEquipArmor = DND_NO_ITEM;
static uint16_t dndEquipShield = DND_NO_ITEM;
static uint16_t dndEquipRing1 = DND_NO_ITEM;
static uint16_t dndEquipRing2 = DND_NO_ITEM;
static uint16_t dndEquipCharm = DND_NO_ITEM;
static uint8_t dndEquipCategory = 0;
static uint16_t dndEquipOwnedIndex = 0;
static const uint8_t DND_EQUIP_CATEGORY_COUNT = 7;
static const char* const DND_EQUIP_CATEGORY_NAMES[DND_EQUIP_CATEGORY_COUNT] = {
  "WEAPON","ARMOR","SHIELD","RING 1","RING 2","CHARM","CONSUMABLES"
};
'''

pat = re.compile(
    r'struct\s+DndItemDef\s*\{.*?static\s+uint8_t\s+dndInventoryIndex\s*=\s*0\s*;\s*',
    re.S,
)
s, n = pat.subn(data_block + "\n", s, count=1)
if n != 1:
    raise SystemExit("current DndItemDef/catalog/global block not found")

# Add the two Character equipment screens.
s, n = re.subn(
    r'enum\s+DndScreen\s*:\s*uint8_t\s*\{([^}]*)\}',
    lambda m: 'enum DndScreen : uint8_t {' + (
        m.group(1).rstrip().rstrip(',') + ', DND_EQUIP_CATEGORIES=6, DND_EQUIP_LIST=7'
        if 'DND_EQUIP_CATEGORIES' not in m.group(1) else m.group(1)
    ) + '}',
    s, count=1,
)
if n != 1:
    raise SystemExit("DndScreen enum not found")

# -----------------------------------------------------------------------------
# Replace old name-history inventory/shop helpers with ID inventory + equipment.
# All public helper signatures use primitive IDs so Arduino prototype generation
# never needs DndItemDef before its declaration.
# -----------------------------------------------------------------------------
a = s.find("static uint16_t dndItemPrice(")
b = s.find("static void dndNextRoom()", a)
if a < 0 or b < 0:
    raise SystemExit("old DND inventory/shop helper block not found")

helpers = r'''static uint16_t dndItemPrice(uint16_t id) {
  if (id >= DND_ITEM_COUNT) return 65000U;
  const DndItemDef &it = DND_ITEM_CATALOG[id];
  uint32_t price = (uint32_t)it.basePrice + (uint32_t)dndRoomNumber * (uint32_t)(1U + it.rarity);
  if (price > 65000U) price = 65000U;
  return (uint16_t)price;
}

static uint16_t dndFindItemByName(const String &name, char type=0) {
  for (uint16_t i=0; i<DND_ITEM_COUNT; ++i) {
    if ((!type || DND_ITEM_CATALOG[i].type == type) && name == DND_ITEM_CATALOG[i].name) return i;
  }
  return DND_NO_ITEM;
}

static uint16_t dndRollCatalogIndex() {
  uint8_t maxRarity = (uint8_t)(dndRoomNumber / 8U);
  if (maxRarity > 4U) maxRarity = 4U;
  uint8_t wanted = maxRarity;
  if (maxRarity > 0U && random(100) < 35) wanted = (uint8_t)random(maxRarity + 1U);
  for (uint16_t tries=0; tries<250; ++tries) {
    uint16_t id = (uint16_t)random((long)DND_ITEM_COUNT);
    if (DND_ITEM_CATALOG[id].rarity == wanted) return id;
  }
  return (uint16_t)random((long)DND_ITEM_COUNT);
}

static void dndRollShop(bool force=false) {
  if (!force && dndShopRoom == dndRoomNumber) return;
  dndShopRoom = dndRoomNumber;
  for (uint8_t i=0; i<DND_SHOP_COUNT; ++i) {
    uint16_t id;
    bool duplicate;
    do {
      id = dndRollCatalogIndex();
      duplicate = false;
      for (uint8_t j=0; j<i; ++j) if (dndShop[j] == id) duplicate = true;
    } while (duplicate);
    dndShop[i] = id;
  }
  dndShopIndex = 0;
}

static uint16_t dndInventoryCountId(uint16_t id) {
  uint16_t count = 0;
  for (uint16_t i=0; i<dndInventoryCount; ++i) if (dndInventory[i] == id) count++;
  return count;
}

static bool dndAddInventory(uint16_t id) {
  if (id >= DND_ITEM_COUNT || dndInventoryCount >= DND_INV_CAP) return false;
  dndInventory[dndInventoryCount++] = id;
  return true;
}

static void dndRemoveInventoryAt(uint16_t slot) {
  if (slot >= dndInventoryCount) return;
  for (uint16_t i=slot+1; i<dndInventoryCount; ++i) dndInventory[i-1] = dndInventory[i];
  dndInventoryCount--;
  if (dndInventoryCount == 0) dndInventoryIndex = 0;
  else if (dndInventoryIndex >= dndInventoryCount) dndInventoryIndex = dndInventoryCount - 1U;
}

static uint16_t dndOwnedCountType(char type) {
  uint16_t count = 0;
  for (uint16_t i=0; i<dndInventoryCount; ++i) {
    uint16_t id = dndInventory[i];
    if (id < DND_ITEM_COUNT && DND_ITEM_CATALOG[id].type == type) count++;
  }
  return count;
}

static uint16_t dndNthOwnedSlot(char type, uint16_t nth) {
  uint16_t seen = 0;
  for (uint16_t i=0; i<dndInventoryCount; ++i) {
    uint16_t id = dndInventory[i];
    if (id < DND_ITEM_COUNT && DND_ITEM_CATALOG[id].type == type) {
      if (seen == nth) return i;
      seen++;
    }
  }
  return DND_NO_ITEM;
}

static uint16_t dndNthOwnedId(char type, uint16_t nth) {
  uint16_t slot = dndNthOwnedSlot(type, nth);
  return slot == DND_NO_ITEM ? DND_NO_ITEM : dndInventory[slot];
}

static int dndGearBonus(char field) {
  uint16_t ids[6] = {dndEquipWeapon,dndEquipArmor,dndEquipShield,dndEquipRing1,dndEquipRing2,dndEquipCharm};
  int total = 0;
  for (uint8_t i=0; i<6; ++i) {
    uint16_t id = ids[i];
    if (id >= DND_ITEM_COUNT) continue;
    const DndItemDef &it = DND_ITEM_CATALOG[id];
    if (field=='S') total += it.strBonus;
    else if (field=='D') total += it.dexBonus;
    else if (field=='A') total += it.acBonus;
    else if (field=='H') total += it.hpBonus;
  }
  return total;
}

static int dndEffectiveStrength() { return dndStrength + dndGearBonus('S'); }
static int dndEffectiveDexterity() { return dndDexterity + dndGearBonus('D'); }
static int dndEffectiveArmorClass() { return dndArmorClass + dndGearBonus('A'); }
static int dndEffectiveMaxHp() { return dndMaxHp + dndGearBonus('H'); }

static void dndSyncWeaponFromEquipped() {
  uint16_t id = dndEquipWeapon;
  if (id >= DND_ITEM_COUNT || DND_ITEM_CATALOG[id].type != 'W') {
    id = dndFindItemByName("IRON SWORD", 'W');
    dndEquipWeapon = id;
  }
  if (id < DND_ITEM_COUNT) {
    const DndItemDef &it = DND_ITEM_CATALOG[id];
    dndWeapon.name = String(it.name);
    dndWeapon.damageMin = it.damageMin;
    dndWeapon.damageMax = it.damageMax;
    dndWeapon.hitBonus = it.hitBonus;
    dndWeapon.foundRoom = dndRoomNumber;
  }
}

static String dndItemTypeName(char type) {
  if (type=='W') return "WEAPON";
  if (type=='A') return "ARMOR";
  if (type=='D') return "SHIELD";
  if (type=='R') return "RING";
  if (type=='C') return "CHARM";
  return "CONSUMABLE";
}

static String dndItemStatsLine(uint16_t id) {
  if (id >= DND_ITEM_COUNT) return "NO ITEM";
  const DndItemDef &it = DND_ITEM_CATALOG[id];
  if (it.type=='W') return "DMG "+String(it.damageMin)+"-"+String(it.damageMax)+" HIT "+String(it.hitBonus)+" S"+String(it.strBonus)+" D"+String(it.dexBonus);
  if (it.type=='H') return it.healAmount >= 9999 ? "FULL RESTORE" : "HEAL "+String(it.healAmount);
  String out;
  if (it.strBonus) out += "STR "+String(it.strBonus)+" ";
  if (it.dexBonus) out += "DEX "+String(it.dexBonus)+" ";
  if (it.acBonus) out += "AC "+String(it.acBonus)+" ";
  if (it.hpBonus) out += "HP "+String(it.hpBonus)+" ";
  if (!out.length()) out = "NO BONUS";
  return out;
}

static void dndClampHpForGear() {
  int cap = dndEffectiveMaxHp();
  if (cap < 1) cap = 1;
  if (dndHp > cap) dndHp = cap;
}

static bool dndEquipOwnedItem(uint16_t id, uint8_t category) {
  if (id >= DND_ITEM_COUNT) return false;
  char type = DND_ITEM_CATALOG[id].type;
  if (category==0 && type=='W') dndEquipWeapon=id;
  else if (category==1 && type=='A') dndEquipArmor=id;
  else if (category==2 && type=='D') dndEquipShield=id;
  else if (category==3 && type=='R') {
    if (dndEquipRing2==id && dndInventoryCountId(id)<2) { dndQueue("NEED SECOND RING"); return false; }
    dndEquipRing1=id;
  }
  else if (category==4 && type=='R') {
    if (dndEquipRing1==id && dndInventoryCountId(id)<2) { dndQueue("NEED SECOND RING"); return false; }
    dndEquipRing2=id;
  }
  else if (category==5 && type=='C') dndEquipCharm=id;
  else return false;
  dndSyncWeaponFromEquipped();
  dndClampHpForGear();
  saveBloomSystemState();
  dndQueue("EQUIPPED "+String(DND_ITEM_CATALOG[id].name));
  return true;
}

static bool dndUseConsumable(uint16_t inventorySlot) {
  if (inventorySlot >= dndInventoryCount) return false;
  uint16_t id = dndInventory[inventorySlot];
  if (id >= DND_ITEM_COUNT || DND_ITEM_CATALOG[id].type != 'H') return false;
  int heal = DND_ITEM_CATALOG[id].healAmount;
  int cap = dndEffectiveMaxHp();
  if (heal >= 9999) dndHp = cap;
  else { dndHp += heal; if (dndHp > cap) dndHp = cap; }
  dndQueue("USED "+String(DND_ITEM_CATALOG[id].name));
  dndQueue("HP "+String(dndHp)+"/"+String(cap));
  dndRemoveInventoryAt(inventorySlot);
  saveBloomSystemState();
  return true;
}

static String dndShopLine(uint8_t slot) {
  uint16_t id = dndShop[slot];
  if (id >= DND_ITEM_COUNT) return "?";
  String line = String(slot==dndShopIndex?">":" ")+DND_ITEM_CATALOG[id].name+" "+String(dndItemPrice(id))+"G";
  return dndWindow(line, slot==dndShopIndex?dndMenuMarquee:0, 21);
}

static void dndDrawShop() {
  dndRollShop(false);
  uint8_t first=dndShopIndex>1?dndShopIndex-1:0;
  if (first>DND_SHOP_COUNT-3) first=DND_SHOP_COUNT-3;
  dndRenderFull("SHOP GOLD "+String(dndGold),dndShopLine(first),dndShopLine(first+1),dndShopLine(first+2));
}

static void dndDrawInventory() {
  if (!dndInventoryCount) {
    dndRenderFull("INVENTORY 0/288","NO ITEMS","GOLD "+String(dndGold),"A SHOP B BACK");
    return;
  }
  if (dndInventoryIndex >= dndInventoryCount) dndInventoryIndex = dndInventoryCount-1U;
  uint16_t id=dndInventory[dndInventoryIndex];
  String title="ITEM "+String(dndInventoryIndex+1)+"/"+String(dndInventoryCount);
  String name=id<DND_ITEM_COUNT?String(DND_ITEM_CATALOG[id].name):"?";
  dndRenderFull(title,dndWindow(name,dndMenuMarquee,21),dndWindow(dndItemStatsLine(id),dndMenuMarquee,21),"A SHOP B BACK");
}

static void dndBuySelectedShopItem() {
  uint16_t id=dndShop[dndShopIndex];
  if (id>=DND_ITEM_COUNT) return;
  uint16_t price=dndItemPrice(id);
  if (dndGold<price) { dndQueue("NEED "+String(price)+" GOLD"); return; }
  if (!dndAddInventory(id)) { dndQueue("INVENTORY FULL"); return; }
  dndGold-=price;
  dndQueue("BOUGHT "+String(DND_ITEM_CATALOG[id].name));
  dndQueue("-"+String(price)+" GOLD");
  saveBloomSystemState();
}

static char dndCategoryType(uint8_t category) {
  if (category==0) return 'W';
  if (category==1) return 'A';
  if (category==2) return 'D';
  if (category==3 || category==4) return 'R';
  if (category==5) return 'C';
  return 'H';
}

static uint16_t dndEquippedForCategory(uint8_t category) {
  if (category==0) return dndEquipWeapon;
  if (category==1) return dndEquipArmor;
  if (category==2) return dndEquipShield;
  if (category==3) return dndEquipRing1;
  if (category==4) return dndEquipRing2;
  if (category==5) return dndEquipCharm;
  return DND_NO_ITEM;
}

static String dndCharacterCategoryLine(uint8_t idx) {
  String line=String(idx==dndEquipCategory?">":" ")+DND_EQUIP_CATEGORY_NAMES[idx];
  uint16_t eq=dndEquippedForCategory(idx);
  if (eq<DND_ITEM_COUNT) line += " "+String(DND_ITEM_CATALOG[eq].name);
  else if (idx<6) line += " -";
  return dndWindow(line,idx==dndEquipCategory?dndMenuMarquee:0,21);
}

static void dndDrawCharacterCategories() {
  uint8_t first=dndEquipCategory>1?dndEquipCategory-1:0;
  if (first>DND_EQUIP_CATEGORY_COUNT-3) first=DND_EQUIP_CATEGORY_COUNT-3;
  dndRenderFull(dndCharacterCategoryLine(first),dndCharacterCategoryLine(first+1),dndCharacterCategoryLine(first+2),"A SELECT B BACK");
}

static void dndDrawEquipList() {
  char type=dndCategoryType(dndEquipCategory);
  uint16_t count=dndOwnedCountType(type);
  if (!count) {
    dndRenderFull(DND_EQUIP_CATEGORY_NAMES[dndEquipCategory],"NO OWNED ITEMS","","B BACK");
    return;
  }
  if (dndEquipOwnedIndex>=count) dndEquipOwnedIndex=count-1U;
  uint16_t id=dndNthOwnedId(type,dndEquipOwnedIndex);
  String title=String(DND_EQUIP_CATEGORY_NAMES[dndEquipCategory])+" "+String(dndEquipOwnedIndex+1)+"/"+String(count);
  String marker=(dndEquippedForCategory(dndEquipCategory)==id && dndEquipCategory<6)?"* ":"> ";
  String footer=type=='H'?"A USE B BACK":"A EQUIP B BACK";
  dndRenderFull(dndWindow(title,0,21),dndWindow(marker+String(DND_ITEM_CATALOG[id].name),dndMenuMarquee,21),dndWindow(dndItemStatsLine(id),dndMenuMarquee,21),footer);
}

'''
s = s[:a] + helpers + s[b:]

# Floor weapon drops now become owned inventory rather than forced equipment.
s = replace_body(
    s,
    r'static\s+void\s+dndGenerateWeapon\s*\(\s*\)',
    r'''  uint16_t id=DND_NO_ITEM;
  for (uint16_t tries=0; tries<250; ++tries) {
    uint16_t pick=dndRollCatalogIndex();
    if (pick<DND_ITEM_COUNT && DND_ITEM_CATALOG[pick].type=='W') { id=pick; break; }
  }
  if (id==DND_NO_ITEM) id=dndFindItemByName("IRON SWORD",'W');
  if (id<DND_ITEM_COUNT && dndAddInventory(id)) {
    dndQueue("FOUND "+String(DND_ITEM_CATALOG[id].name));
    dndQueue(dndItemStatsLine(id));
    saveBloomSystemState();
  } else dndQueue("PACK FULL");'''
)

# Equipment bonuses participate in combat, traps/chests, HP caps, and HUD.
s = s.replace("roll + dndStrength + dndWeapon.hitBonus", "roll + dndEffectiveStrength() + dndWeapon.hitBonus")
s = s.replace("(dndStrength / 2)", "(dndEffectiveStrength() / 2)")
s = s.replace("total >= dndArmorClass", "total >= dndEffectiveArmorClass()")
s = s.replace("+ dndDexterity;", "+ dndEffectiveDexterity();")
s = s.replace("dndHp = dndMaxHp;", "dndHp = dndEffectiveMaxHp();")
s = s.replace("if (dndHp > dndMaxHp) dndHp = dndMaxHp;", "if (dndHp > dndEffectiveMaxHp()) dndHp = dndEffectiveMaxHp();")
s = s.replace('case 1: return "HEALTH " + String(dndHp) + "/" + String(dndMaxHp);', 'case 1: return "HEALTH " + String(dndHp) + "/" + String(dndEffectiveMaxHp());')
s = s.replace('case 2: return "ARMOR CLASS " + String(dndArmorClass);', 'case 2: return "ARMOR CLASS " + String(dndEffectiveArmorClass());')

# New game: one starter sword is owned/equipped; all other slots begin empty.
old_reset = "dndInventoryCount=0; dndInventoryIndex=0; dndShopRoom=0; dndShopIndex=0;\n  dndRollShop(true);"
new_reset = '''dndInventoryCount=0; dndInventoryIndex=0; dndShopRoom=0; dndShopIndex=0;
  dndEquipWeapon=dndFindItemByName("IRON SWORD",'W');
  dndEquipArmor=dndEquipShield=dndEquipRing1=dndEquipRing2=dndEquipCharm=DND_NO_ITEM;
  if (dndEquipWeapon<DND_ITEM_COUNT) dndAddInventory(dndEquipWeapon);
  dndSyncWeaponFromEquipped();
  dndRollShop(true);'''
if old_reset not in s:
    raise SystemExit("DND new-game inventory reset anchor not found")
s = s.replace(old_reset, new_reset, 1)

# -----------------------------------------------------------------------------
# Character menu becomes equipment hub. Replace its branch, then replace the
# inventory/shop handler region so indices are 16-bit and add equipment screens.
# -----------------------------------------------------------------------------
start, ob, end = find_function(s, r'static\s+void\s+dndHandleInput\s*\(\s*Input\s+in\s*\)')
body = s[ob+1:end-1]
body, n = re.subn(
    r'\s*if\s*\(dndMenuIndex==0\)\s*\{.*?\}\s*\n\s*if\s*\(dndMenuIndex==1\)',
    '''\n      if (dndMenuIndex==0) {
        dndScreen=DND_EQUIP_CATEGORIES; dndEquipCategory=0; dndEquipOwnedIndex=0;
        dndMenuMarquee=0; dndMenuMarqueeMs=millis(); dndDrawCharacterCategories(); return;
      }
      if (dndMenuIndex==1)''',
    body, count=1, flags=re.S,
)
if n != 1:
    raise SystemExit("Character menu branch not found")

a = body.find("  if (dndScreen==DND_INVENTORY) {")
b = body.find("  if (dndScreen==DND_SYMBOLS) {", a)
if a < 0 or b < 0:
    raise SystemExit("DND inventory/shop handler region not found")
new_handlers = r'''  if (dndScreen==DND_EQUIP_CATEGORIES) {
    if (in==BKEY) { dndScreen=DND_MENU; dndMenuMarquee=0; dndDrawMenu(); return; }
    if (in==UP) dndEquipCategory=(uint8_t)((dndEquipCategory+DND_EQUIP_CATEGORY_COUNT-1U)%DND_EQUIP_CATEGORY_COUNT);
    else if (in==DOWN) dndEquipCategory=(uint8_t)((dndEquipCategory+1U)%DND_EQUIP_CATEGORY_COUNT);
    else if (in==AKEY) { dndEquipOwnedIndex=0; dndScreen=DND_EQUIP_LIST; dndMenuMarquee=0; dndDrawEquipList(); return; }
    dndMenuMarquee=0; dndMenuMarqueeMs=millis(); dndDrawCharacterCategories(); return;
  }

  if (dndScreen==DND_EQUIP_LIST) {
    if (in==BKEY) { dndScreen=DND_EQUIP_CATEGORIES; dndMenuMarquee=0; dndDrawCharacterCategories(); return; }
    char type=dndCategoryType(dndEquipCategory);
    uint16_t count=dndOwnedCountType(type);
    if (count) {
      if (in==UP) dndEquipOwnedIndex=(dndEquipOwnedIndex+count-1U)%count;
      else if (in==DOWN) dndEquipOwnedIndex=(dndEquipOwnedIndex+1U)%count;
      else if (in==AKEY) {
        uint16_t slot=dndNthOwnedSlot(type,dndEquipOwnedIndex);
        uint16_t id=slot==DND_NO_ITEM?DND_NO_ITEM:dndInventory[slot];
        if (type=='H') { if (slot!=DND_NO_ITEM) dndUseConsumable(slot); }
        else dndEquipOwnedItem(id,dndEquipCategory);
        count=dndOwnedCountType(type);
        if (!count) dndEquipOwnedIndex=0;
        else if (dndEquipOwnedIndex>=count) dndEquipOwnedIndex=count-1U;
      }
    }
    dndMenuMarquee=0; dndMenuMarqueeMs=millis(); dndDrawEquipList(); return;
  }

  if (dndScreen==DND_INVENTORY) {
    if (in==BKEY) { dndScreen=DND_MENU; dndMenuMarquee=0; dndDrawMenu(); return; }
    if (in==AKEY) { dndScreen=DND_SHOP; dndShopIndex=0; dndMenuMarquee=0; dndRollShop(false); dndDrawShop(); return; }
    if (dndInventoryCount) {
      if (in==UP) dndInventoryIndex=(dndInventoryIndex+dndInventoryCount-1U)%dndInventoryCount;
      else if (in==DOWN) dndInventoryIndex=(dndInventoryIndex+1U)%dndInventoryCount;
    }
    dndMenuMarquee=0; dndMenuMarqueeMs=millis(); dndDrawInventory(); return;
  }

  if (dndScreen==DND_SHOP) {
    if (in==BKEY) { dndScreen=DND_INVENTORY; dndMenuMarquee=0; dndDrawInventory(); return; }
    if (in==UP) dndShopIndex=(uint8_t)((dndShopIndex+DND_SHOP_COUNT-1U)%DND_SHOP_COUNT);
    else if (in==DOWN) dndShopIndex=(uint8_t)((dndShopIndex+1U)%DND_SHOP_COUNT);
    else if (in==AKEY) dndBuySelectedShopItem();
    dndMenuMarquee=0; dndMenuMarqueeMs=millis(); dndDrawShop(); return;
  }

'''
body = body[:a] + new_handlers + body[b:]
s = s[:ob+1] + body + s[end-1:]

# Menu marquee redraw supports the new Character screens.
start, ob, end = find_function(s, r'static\s+void\s+dndServiceGame\s*\(\s*\)')
body = s[ob+1:end-1]
needle = "else if (dndScreen==DND_SHOP) dndDrawShop();"
if needle in body:
    body = body.replace(needle, needle + "\n    else if (dndScreen==DND_EQUIP_CATEGORIES) dndDrawCharacterCategories();\n    else if (dndScreen==DND_EQUIP_LIST) dndDrawEquipList();", 1)
else:
    raise SystemExit("DND service shop-redraw anchor not found")
s = s[:ob+1] + body + s[end-1:]

# -----------------------------------------------------------------------------
# Unified BLOOM save V2. One Preferences blob still owns all pets + DND.
# Includes migration from the just-finished V1 format by matching old names into
# the new 288-item catalog. Old shop stock is intentionally rerolled on migrate.
# -----------------------------------------------------------------------------
a = s.find("// BLOOM_SYSTEM_UNIFIED_SAVE_V1")
b = s.find("static void dndStartGame() {", a)
if a < 0 or b < 0:
    raise SystemExit("unified save V1 implementation block not found")

save_v2 = r'''// BLOOM_SYSTEM_UNIFIED_SAVE_V2
static const uint32_t BLOOM_SAVE_MAGIC_V2 = 0x424C4D32UL; // BLM2
static const uint16_t BLOOM_SAVE_VERSION_V2 = 2;
static const uint8_t BLOOM_SAVE_NAME_LEN_V1 = 24;
static const uint8_t BLOOM_SAVE_INV_CAP_V1 = 12;

// Exact legacy V1 layout, used only for migration.
struct BloomDndDurableV1Legacy {
  uint8_t valid;
  int16_t hp; int16_t maxHp; int16_t strength; int16_t dexterity; int16_t armorClass;
  uint32_t xp; uint32_t gold;
  uint16_t level; uint16_t keys; uint16_t roomNumber; uint16_t deepestRoom;
  char weaponName[BLOOM_SAVE_NAME_LEN_V1];
  int16_t weaponDamageMin; int16_t weaponDamageMax; int16_t weaponHitBonus; uint16_t weaponFoundRoom;
  uint8_t inventoryCount;
  char inventory[BLOOM_SAVE_INV_CAP_V1][BLOOM_SAVE_NAME_LEN_V1];
  uint8_t shop[4]; uint8_t shopIndex; uint16_t shopRoom; uint8_t roomThemeIndex;
};
struct BloomSystemSaveV1Legacy {
  uint32_t magic; uint16_t version; uint16_t size; uint8_t activePetSlot; uint8_t reserved[3];
  PetSave pet[3]; BloomDndDurableV1Legacy dnd; uint32_t checksum;
};

struct BloomDndDurableV2 {
  uint8_t valid;
  int16_t hp; int16_t maxHp; int16_t strength; int16_t dexterity; int16_t armorClass;
  uint32_t xp; uint32_t gold;
  uint16_t level; uint16_t keys; uint16_t roomNumber; uint16_t deepestRoom;
  uint16_t inventoryCount;
  uint16_t inventory[DND_INV_CAP];
  uint16_t shop[4];
  uint8_t shopIndex; uint16_t shopRoom; uint8_t roomThemeIndex;
  uint16_t equipWeapon; uint16_t equipArmor; uint16_t equipShield;
  uint16_t equipRing1; uint16_t equipRing2; uint16_t equipCharm;
};
struct BloomSystemSaveV2 {
  uint32_t magic; uint16_t version; uint16_t size; uint8_t activePetSlot; uint8_t reserved[3];
  PetSave pet[3]; BloomDndDurableV2 dnd; uint32_t checksum;
};

static bool bloomDndHasState=false;
static uint32_t bloomUnifiedLastAutosaveMs=0;

static uint32_t bloomUnifiedChecksumBytes(const uint8_t *data, size_t n) {
  uint32_t h=2166136261UL;
  for (size_t i=0; i<n; ++i) { h^=data[i]; h*=16777619UL; }
  return h;
}

static void saveBloomSystemState() {
  static BloomSystemSaveV2 st;
  memset(&st,0,sizeof(st));
  st.magic=BLOOM_SAVE_MAGIC_V2; st.version=BLOOM_SAVE_VERSION_V2; st.size=sizeof(st);
  st.activePetSlot=activeSlot<3?activeSlot:0;
  for (uint8_t i=0;i<3;++i) {
    if (pets[i].occupied) pets[i].checksum=petChecksum(pets[i]);
    memcpy(&st.pet[i],&pets[i],sizeof(PetSave));
  }
  st.dnd.valid=bloomDndHasState?1U:0U;
  if (bloomDndHasState) {
    st.dnd.hp=dndHp; st.dnd.maxHp=dndMaxHp; st.dnd.strength=dndStrength; st.dnd.dexterity=dndDexterity; st.dnd.armorClass=dndArmorClass;
    st.dnd.xp=dndXp; st.dnd.gold=dndGold; st.dnd.level=dndLevel; st.dnd.keys=dndKeys;
    st.dnd.roomNumber=dndRoomNumber; st.dnd.deepestRoom=dndDeepestRoom;
    st.dnd.inventoryCount=dndInventoryCount>DND_INV_CAP?DND_INV_CAP:dndInventoryCount;
    for (uint16_t i=0;i<st.dnd.inventoryCount;++i) st.dnd.inventory[i]=dndInventory[i];
    for (uint8_t i=0;i<4;++i) st.dnd.shop[i]=dndShop[i];
    st.dnd.shopIndex=dndShopIndex; st.dnd.shopRoom=dndShopRoom; st.dnd.roomThemeIndex=dndRoomThemeIndex;
    st.dnd.equipWeapon=dndEquipWeapon; st.dnd.equipArmor=dndEquipArmor; st.dnd.equipShield=dndEquipShield;
    st.dnd.equipRing1=dndEquipRing1; st.dnd.equipRing2=dndEquipRing2; st.dnd.equipCharm=dndEquipCharm;
  }
  st.checksum=bloomUnifiedChecksumBytes(reinterpret_cast<const uint8_t*>(&st),sizeof(st)-sizeof(st.checksum));
  Preferences prefs;
  if (!prefs.begin("bloomsys",false)) { Serial.println("BP|BLOOM_SAVE|ok=0|reason=prefs_begin"); return; }
  size_t wrote=prefs.putBytes("state",&st,sizeof(st)); prefs.end();
  Serial.printf("BP|BLOOM_SAVE|ok=%u|ver=2|bytes=%u|slot=%u|dnd=%u|items=%u\n",
                wrote==sizeof(st)?1U:0U,(unsigned)wrote,(unsigned)st.activePetSlot,(unsigned)st.dnd.valid,(unsigned)st.dnd.inventoryCount);
}

static bool loadBloomSystemState() {
  Preferences prefs;
  if (!prefs.begin("bloomsys",true)) return false;
  size_t len=prefs.getBytesLength("state");

  if (len==sizeof(BloomSystemSaveV2)) {
    static BloomSystemSaveV2 st;
    size_t got=prefs.getBytes("state",&st,sizeof(st)); prefs.end();
    uint32_t want=bloomUnifiedChecksumBytes(reinterpret_cast<const uint8_t*>(&st),sizeof(st)-sizeof(st.checksum));
    if (got!=sizeof(st)||st.magic!=BLOOM_SAVE_MAGIC_V2||st.version!=2||st.size!=sizeof(st)||want!=st.checksum) return false;
    for (uint8_t i=0;i<3;++i) memcpy(&pets[i],&st.pet[i],sizeof(PetSave));
    activeSlot=st.activePetSlot<3?st.activePetSlot:0;
    bloomDndHasState=st.dnd.valid!=0;
    if (bloomDndHasState) {
      dndHp=st.dnd.hp; dndMaxHp=st.dnd.maxHp<1?18:st.dnd.maxHp; dndStrength=st.dnd.strength; dndDexterity=st.dnd.dexterity; dndArmorClass=st.dnd.armorClass;
      dndXp=st.dnd.xp; dndGold=st.dnd.gold; dndLevel=st.dnd.level<1?1:st.dnd.level; dndKeys=st.dnd.keys;
      dndRoomNumber=st.dnd.roomNumber<1?1:st.dnd.roomNumber; dndDeepestRoom=st.dnd.deepestRoom<dndRoomNumber?dndRoomNumber:st.dnd.deepestRoom;
      dndInventoryCount=st.dnd.inventoryCount>DND_INV_CAP?DND_INV_CAP:st.dnd.inventoryCount; dndInventoryIndex=0;
      for (uint16_t i=0;i<dndInventoryCount;++i) dndInventory[i]=st.dnd.inventory[i]<DND_ITEM_COUNT?st.dnd.inventory[i]:DND_NO_ITEM;
      for (uint8_t i=0;i<4;++i) dndShop[i]=st.dnd.shop[i]<DND_ITEM_COUNT?st.dnd.shop[i]:0;
      dndShopIndex=st.dnd.shopIndex<4?st.dnd.shopIndex:0; dndShopRoom=st.dnd.shopRoom; dndRoomThemeIndex=st.dnd.roomThemeIndex%48U;
      dndEquipWeapon=st.dnd.equipWeapon<DND_ITEM_COUNT?st.dnd.equipWeapon:DND_NO_ITEM;
      dndEquipArmor=st.dnd.equipArmor<DND_ITEM_COUNT?st.dnd.equipArmor:DND_NO_ITEM;
      dndEquipShield=st.dnd.equipShield<DND_ITEM_COUNT?st.dnd.equipShield:DND_NO_ITEM;
      dndEquipRing1=st.dnd.equipRing1<DND_ITEM_COUNT?st.dnd.equipRing1:DND_NO_ITEM;
      dndEquipRing2=st.dnd.equipRing2<DND_ITEM_COUNT?st.dnd.equipRing2:DND_NO_ITEM;
      dndEquipCharm=st.dnd.equipCharm<DND_ITEM_COUNT?st.dnd.equipCharm:DND_NO_ITEM;
      dndSyncWeaponFromEquipped(); dndClampHpForGear();
    }
    Serial.printf("BP|BLOOM_LOAD|ok=1|ver=2|slot=%u|dnd=%u|items=%u\n",(unsigned)activeSlot,bloomDndHasState?1U:0U,(unsigned)dndInventoryCount);
    return true;
  }

  if (len==sizeof(BloomSystemSaveV1Legacy)) {
    static BloomSystemSaveV1Legacy old;
    size_t got=prefs.getBytes("state",&old,sizeof(old)); prefs.end();
    uint32_t want=bloomUnifiedChecksumBytes(reinterpret_cast<const uint8_t*>(&old),sizeof(old)-sizeof(old.checksum));
    if (got!=sizeof(old)||old.magic!=0x424C4D31UL||old.version!=1||old.size!=sizeof(old)||want!=old.checksum) return false;
    for (uint8_t i=0;i<3;++i) memcpy(&pets[i],&old.pet[i],sizeof(PetSave));
    activeSlot=old.activePetSlot<3?old.activePetSlot:0;
    bloomDndHasState=old.dnd.valid!=0;
    dndInventoryCount=0; dndInventoryIndex=0;
    dndEquipWeapon=dndEquipArmor=dndEquipShield=dndEquipRing1=dndEquipRing2=dndEquipCharm=DND_NO_ITEM;
    if (bloomDndHasState) {
      dndHp=old.dnd.hp; dndMaxHp=old.dnd.maxHp<1?18:old.dnd.maxHp; dndStrength=old.dnd.strength; dndDexterity=old.dnd.dexterity; dndArmorClass=old.dnd.armorClass;
      dndXp=old.dnd.xp; dndGold=old.dnd.gold; dndLevel=old.dnd.level<1?1:old.dnd.level; dndKeys=old.dnd.keys;
      dndRoomNumber=old.dnd.roomNumber<1?1:old.dnd.roomNumber; dndDeepestRoom=old.dnd.deepestRoom<dndRoomNumber?dndRoomNumber:old.dnd.deepestRoom;
      dndRoomThemeIndex=old.dnd.roomThemeIndex%48U;
      uint16_t wid=dndFindItemByName(String(old.dnd.weaponName),'W');
      if (wid==DND_NO_ITEM) wid=dndFindItemByName("IRON SWORD",'W');
      if (wid<DND_ITEM_COUNT) { dndEquipWeapon=wid; dndAddInventory(wid); }
      for (uint8_t i=0;i<old.dnd.inventoryCount && i<BLOOM_SAVE_INV_CAP_V1;++i) {
        uint16_t id=dndFindItemByName(String(old.dnd.inventory[i]));
        if (id<DND_ITEM_COUNT) dndAddInventory(id);
      }
      dndShopRoom=0; dndShopIndex=0; dndRollShop(true); dndSyncWeaponFromEquipped(); dndClampHpForGear();
    }
    Serial.println("BP|BLOOM_LOAD|ok=1|source=V1_MIGRATE_TO_V2");
    saveBloomSystemState();
    return true;
  }

  prefs.end();
  return false;
}

static void resumeBloomDndFromUnifiedSave() {
  dndScreen=DND_PLAY; dndEventHead=dndEventTail=0; dndCurrentEvent="RESUME";
  dndEventUntilMs=millis()+900UL; dndEventMarquee=0; dndStatusFirst=0; dndStatusRotateMs=millis(); dndAttackArmedUntilMs=0;
  for (uint8_t i=0;i<3;++i) { dndStatusMarquee[i]=0; dndStatusMarqueeMs[i]=millis(); }
  dndSyncWeaponFromEquipped(); dndClampHpForGear(); dndGenerateRoom(false); dndDrawPlay();
}

'''
s = s[:a] + save_v2 + s[b:]

p.write_text(s)
print("PATCHED DND EQUIPMENT + 288 ITEM CATALOG V2")
print("  48 weapons")
print("  48 armor")
print("  48 shields")
print("  48 rings")
print("  48 charms/relics")
print("  48 consumables")
print("  Character -> category -> owned-item equip/use UI")
print("  weapon drops go to inventory instead of silently replacing equipment")
print("  equipment bonuses feed combat, AC, DEX checks, STR damage, and HP cap")
print("  one unified bloomsys/state blob remains authoritative")
print("  unified save V1 migrates to V2 by matching old item names")
print("patched:", p)
