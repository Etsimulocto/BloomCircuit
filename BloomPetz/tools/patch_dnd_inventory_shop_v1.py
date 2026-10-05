#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_dnd_inventory_shop_v1.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()

marker = "BLOOM_DND_INVENTORY_SHOP_V1"
if marker in s:
    print("DND inventory/shop patch already present")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".pre_dnd_inventory_shop_v1")
if not backup.exists():
    backup.write_text(s)

old = "enum DndScreen : uint8_t { DND_PLAY=0, DND_MENU=1, DND_SYMBOLS=2, DND_INFO=3 };"
new = "enum DndScreen : uint8_t { DND_PLAY=0, DND_MENU=1, DND_SYMBOLS=2, DND_INFO=3, DND_INVENTORY=4, DND_SHOP=5 };"
if old not in s:
    raise SystemExit("DndScreen enum anchor not found")
s = s.replace(old, new, 1)

anchor = '''struct DndWeapon {
  String name;
  int16_t damageMin;
  int16_t damageMax;
  int16_t hitBonus;
  uint16_t foundRoom;
};
'''
insert = anchor + r'''
// BLOOM_DND_INVENTORY_SHOP_V1
struct DndItemDef {
  const char *name;
  char type;           // W weapon, A armor, H heal, S stat/charm
  uint16_t basePrice;
  int16_t a;
  int16_t b;
  int16_t c;
  uint8_t rarity;      // 0 common .. 4 legendary
};

static const DndItemDef DND_ITEM_CATALOG[] = {
  {"RUSTY KNIFE",'W',10,1,4,0,0}, {"DAGGER",'W',16,1,5,1,0},
  {"IRON SWORD",'W',28,2,6,0,0}, {"SHORT SWORD",'W',34,2,7,1,0},
  {"HAND AXE",'W',36,3,7,0,0}, {"MACE",'W',40,3,7,1,0},
  {"SPEAR",'W',42,2,8,2,0}, {"WAR AXE",'W',58,4,9,0,1},
  {"LONG SWORD",'W',64,3,9,2,1}, {"CROSSBOW",'W',72,4,10,2,1},
  {"BONE BLADE",'W',86,4,11,3,1}, {"SILVER SWORD",'W',110,5,12,3,2},
  {"FROST BLADE",'W',145,6,13,4,2}, {"FLAME SWORD",'W',165,7,14,4,2},
  {"VOID AXE",'W',230,8,16,5,3}, {"DRAGON BLADE",'W',340,10,20,6,4},

  {"LEATHER CAP",'A',14,1,0,0,0}, {"WOOD SHIELD",'A',20,1,0,0,0},
  {"LEATHER ARMOR",'A',28,1,0,0,0}, {"IRON HELM",'A',38,2,0,0,1},
  {"IRON SHIELD",'A',46,2,0,0,1}, {"CHAIN MAIL",'A',58,2,0,0,1},
  {"IRON ARMOR",'A',78,3,0,0,2}, {"TOWER SHIELD",'A',96,3,0,0,2},
  {"STEEL ARMOR",'A',125,4,0,0,2}, {"DRAGON SCALE",'A',260,6,0,0,4},

  {"BANDAGE",'H',8,5,0,0,0}, {"RED POTION",'H',14,9,0,0,0},
  {"BIG RED POTION",'H',28,18,0,0,1}, {"ELIXIR",'H',52,30,0,0,2},
  {"PHOENIX TONIC",'H',120,60,0,0,3}, {"FULL RESTORE",'H',220,999,0,0,4},

  {"COPPER RING",'S',24,1,0,0,0}, {"LUCKY RING",'S',44,0,1,0,1},
  {"GOBLIN TOOTH",'S',48,1,1,0,1}, {"BONE CHARM",'S',54,0,0,2,1},
  {"MOON CHARM",'S',72,0,2,2,2}, {"SUN CHARM",'S',76,2,0,2,2},
  {"RUBY RING",'S',95,3,0,0,2}, {"EMERALD RING",'S',98,0,3,0,2},
  {"SAPPHIRE RING",'S',110,0,0,4,2}, {"SKULL RING",'S',150,3,2,3,3},
  {"ROYAL SEAL",'S',185,2,3,4,3}, {"ANCIENT IDOL",'S',210,4,2,4,3},
  {"BLACK PEARL",'S',260,4,4,5,4}, {"STAR RELIC",'S',320,5,5,6,4},
  {"VOID HEART",'S',390,6,6,8,4}, {"CROWN OF BLOOM",'S',500,8,8,10,4}
};
static const uint8_t DND_ITEM_COUNT = sizeof(DND_ITEM_CATALOG)/sizeof(DND_ITEM_CATALOG[0]);
static const uint8_t DND_SHOP_COUNT = 4;
static const uint8_t DND_INV_CAP = 12;
static uint8_t dndShop[DND_SHOP_COUNT] = {0,1,2,3};
static uint8_t dndShopIndex = 0;
static uint16_t dndShopRoom = 0;
static String dndInventory[DND_INV_CAP];
static uint8_t dndInventoryCount = 0;
static uint8_t dndInventoryIndex = 0;
'''
if anchor not in s:
    raise SystemExit("DndWeapon struct anchor not found")
s = s.replace(anchor, insert, 1)

anchor = 'static void dndNextRoom() {\n'
helpers = r'''static uint16_t dndItemPrice(const DndItemDef &it) {
  uint32_t depth = dndRoomNumber;
  uint32_t price = (uint32_t)it.basePrice + depth * (uint32_t)(1U + it.rarity);
  if (price > 65000U) price = 65000U;
  return (uint16_t)price;
}

static uint8_t dndRollCatalogIndex() {
  uint8_t roll = (uint8_t)random(100);
  uint8_t wanted = roll < 55 ? 0 : (roll < 80 ? 1 : (roll < 93 ? 2 : (roll < 99 ? 3 : 4)));
  for (uint8_t tries=0; tries<50; ++tries) {
    uint8_t idx = (uint8_t)random(DND_ITEM_COUNT);
    if (DND_ITEM_CATALOG[idx].rarity == wanted) return idx;
  }
  return (uint8_t)random(DND_ITEM_COUNT);
}

static void dndRollShop(bool force=false) {
  if (!force && dndShopRoom == dndRoomNumber) return;
  dndShopRoom = dndRoomNumber;
  for (uint8_t i=0;i<DND_SHOP_COUNT;++i) {
    uint8_t idx;
    bool duplicate;
    do {
      idx = dndRollCatalogIndex();
      duplicate = false;
      for (uint8_t j=0;j<i;++j) if (dndShop[j] == idx) duplicate = true;
    } while (duplicate);
    dndShop[i] = idx;
  }
  dndShopIndex = 0;
}

static void dndRememberItem(const char *name) {
  if (dndInventoryCount < DND_INV_CAP) {
    dndInventory[dndInventoryCount++] = String(name);
  } else {
    for (uint8_t i=1;i<DND_INV_CAP;++i) dndInventory[i-1] = dndInventory[i];
    dndInventory[DND_INV_CAP-1] = String(name);
  }
}

static void dndApplyPurchase(const DndItemDef &it) {
  dndRememberItem(it.name);
  if (it.type == 'W') {
    dndWeapon.name = String(it.name);
    dndWeapon.damageMin = dndScaled(it.a, 1);
    dndWeapon.damageMax = dndScaled(it.b, dndWeapon.damageMin);
    dndWeapon.hitBonus = dndScaled(it.c, -20);
    dndWeapon.foundRoom = dndRoomNumber;
    dndQueue("EQUIP " + dndWeapon.name);
  } else if (it.type == 'A') {
    dndArmorClass += it.a;
    dndQueue("AC +" + String(it.a));
  } else if (it.type == 'H') {
    dndHp += it.a;
    if (dndHp > dndMaxHp || it.a >= 999) dndHp = dndMaxHp;
    dndQueue("HEAL " + String(it.a >= 999 ? dndMaxHp : it.a));
  } else if (it.type == 'S') {
    dndStrength += it.a;
    dndDexterity += it.b;
    dndMaxHp += it.c;
    dndHp += it.c;
    dndQueue("CHARM " + String(it.name));
  }
}

static String dndShopLine(uint8_t slot) {
  const DndItemDef &it = DND_ITEM_CATALOG[dndShop[slot]];
  String s = String(slot == dndShopIndex ? ">" : " ") + it.name + " " + String(dndItemPrice(it)) + "G";
  return dndWindow(s, slot == dndShopIndex ? dndMenuMarquee : 0, 21);
}

static void dndDrawShop() {
  dndRollShop(false);
  uint8_t first = dndShopIndex > 1 ? dndShopIndex - 1 : 0;
  if (first > DND_SHOP_COUNT - 3) first = DND_SHOP_COUNT - 3;
  dndRenderFull("SHOP GOLD " + String(dndGold), dndShopLine(first), dndShopLine(first+1), dndShopLine(first+2));
}

static void dndDrawInventory() {
  if (dndInventoryCount == 0) {
    dndRenderFull("INVENTORY", dndWeapon.name, "GOLD " + String(dndGold), "A SHOP B BACK");
    return;
  }
  uint8_t idx = dndInventoryIndex;
  String line = ">" + dndInventory[idx];
  dndRenderFull("ITEMS " + String(idx+1) + "/" + String(dndInventoryCount), dndWindow(line,dndMenuMarquee,21),
                "GOLD " + String(dndGold), "A SHOP B BACK");
}

static void dndBuySelectedShopItem() {
  const DndItemDef &it = DND_ITEM_CATALOG[dndShop[dndShopIndex]];
  uint16_t price = dndItemPrice(it);
  if (dndGold < price) {
    dndQueue("NEED " + String(price) + " GOLD");
    return;
  }
  dndGold -= price;
  dndApplyPurchase(it);
  dndQueue("BOUGHT " + String(it.name));
  dndQueue("-" + String(price) + " GOLD");
}

'''
if anchor not in s:
    raise SystemExit("dndNextRoom anchor not found")
s = s.replace(anchor, helpers + anchor, 1)

old = '''static void dndNextRoom() {
  if (dndRoomNumber < 65535) dndRoomNumber++;
  if (dndRoomNumber > dndDeepestRoom) dndDeepestRoom = dndRoomNumber;
  dndGenerateRoom(true);
}
'''
new = '''static void dndNextRoom() {
  if (dndRoomNumber < 65535) dndRoomNumber++;
  if (dndRoomNumber > dndDeepestRoom) dndDeepestRoom = dndRoomNumber;
  dndGenerateRoom(true);
  dndRollShop(true);
}
'''
if old not in s:
    raise SystemExit("dndNextRoom body anchor not found")
s = s.replace(old, new, 1)

old = '''      if (dndMenuIndex==1) {
        dndInfoTitle="INVENTORY";
        dndInfoBody=dndWeapon.name+" "+String(dndWeapon.damageMin)+"-"+String(dndWeapon.damageMax)+
                    " HIT "+String(dndWeapon.hitBonus)+" GOLD "+String(dndGold);
        dndScreen=DND_INFO; dndMenuMarquee=0; dndDrawInfo(); return;
      }
'''
new = '''      if (dndMenuIndex==1) {
        dndScreen=DND_INVENTORY; dndInventoryIndex=0; dndMenuMarquee=0; dndDrawInventory(); return;
      }
'''
if old not in s:
    raise SystemExit("inventory menu handler anchor not found")
s = s.replace(old, new, 1)

anchor = '''  if (dndScreen==DND_SYMBOLS) {
'''
handlers = r'''  if (dndScreen==DND_INVENTORY) {
    if (in==BKEY) { dndScreen=DND_MENU; dndMenuMarquee=0; dndDrawMenu(); return; }
    if (in==AKEY) { dndScreen=DND_SHOP; dndShopIndex=0; dndMenuMarquee=0; dndRollShop(false); dndDrawShop(); return; }
    if (dndInventoryCount > 0) {
      if (in==UP) dndInventoryIndex=(uint8_t)((dndInventoryIndex+dndInventoryCount-1U)%dndInventoryCount);
      else if (in==DOWN) dndInventoryIndex=(uint8_t)((dndInventoryIndex+1U)%dndInventoryCount);
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
if anchor not in s:
    raise SystemExit("DND_SYMBOLS handler anchor not found")
s = s.replace(anchor, handlers + anchor, 1)

old = '''    else if (dndScreen==DND_SYMBOLS) dndDrawSymbols();
    else if (dndScreen==DND_INFO) dndDrawInfo();
'''
new = '''    else if (dndScreen==DND_SYMBOLS) dndDrawSymbols();
    else if (dndScreen==DND_INFO) dndDrawInfo();
    else if (dndScreen==DND_INVENTORY) dndDrawInventory();
    else if (dndScreen==DND_SHOP) dndDrawShop();
'''
if old not in s:
    raise SystemExit("dndServiceGame redraw anchor not found")
s = s.replace(old, new, 1)

old = '''  dndXp=0; dndGold=0; dndLevel=1; dndKeys=0;
  dndRoomNumber=1; dndDeepestRoom=1;
  dndWeapon={"IRON SWORD",2,6,0,1};
'''
new = '''  dndXp=0; dndGold=0; dndLevel=1; dndKeys=0;
  dndRoomNumber=1; dndDeepestRoom=1;
  dndWeapon={"IRON SWORD",2,6,0,1};
  dndInventoryCount=0; dndInventoryIndex=0; dndShopRoom=0; dndShopIndex=0;
  dndRollShop(true);
'''
if old not in s:
    raise SystemExit("dndStartGame reset anchor not found")
s = s.replace(old, new, 1)

p.write_text(s)
print(f"Patched: {p}")
print("DND inventory/shop V1 installed")
print("  48-item authored catalog")
print("  4 random shop offers")
print("  gold spending + purchases")
print("  weapons equip / armor AC / healing / stat charms")
print("  12-slot recent-items inventory")
print("  shop rerolls on each new room")
print("Compile and flash required.")
