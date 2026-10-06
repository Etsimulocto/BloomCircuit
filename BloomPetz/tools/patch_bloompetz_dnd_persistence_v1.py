#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_bloompetz_dnd_persistence_v1.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_PET_DND_PERSISTENCE_V1"
if marker in s:
    print("BloomPetz/DND persistence patch already present")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".pre_bloom_pet_dnd_persistence_v1")
if not backup.exists():
    backup.write_text(s)

# -----------------------------------------------------------------------------
# Pet persistence already exists as whole-struct saveSlot(slot).  The missing
# safety boundary is flushing the active pet before BLOOM SYSTEM takes over.
# DND gets a separate fixed-layout Preferences record (never raw String data).
# -----------------------------------------------------------------------------

start_anchor = "static void dndStartGame() {\n"
if start_anchor not in s:
    raise SystemExit("dndStartGame definition not found")

persist_block = r'''// BLOOM_PET_DND_PERSISTENCE_V1
// Durable DND progression. Transient room enemies/event timers are rebuilt.
static const uint32_t DND_SAVE_MAGIC_V1 = 0x444E4431UL; // DND1
static const uint16_t DND_SAVE_VERSION_V1 = 1;
static const uint8_t DND_SAVE_INV_CAP_V1 = 12;
static const uint8_t DND_SAVE_NAME_LEN_V1 = 24;

struct DndPersistV1 {
  uint32_t magic;
  uint16_t version;
  uint16_t size;

  int16_t hp;
  int16_t maxHp;
  int16_t strength;
  int16_t dexterity;
  int16_t armorClass;
  uint32_t xp;
  uint32_t gold;
  uint16_t level;
  uint16_t keys;
  uint16_t roomNumber;
  uint16_t deepestRoom;

  char weaponName[DND_SAVE_NAME_LEN_V1];
  int16_t weaponDamageMin;
  int16_t weaponDamageMax;
  int16_t weaponHitBonus;
  uint16_t weaponFoundRoom;

  uint8_t inventoryCount;
  char inventory[DND_SAVE_INV_CAP_V1][DND_SAVE_NAME_LEN_V1];
  uint8_t shop[4];
  uint8_t shopIndex;
  uint16_t shopRoom;
  uint8_t roomThemeIndex;

  uint32_t checksum;
};

static uint32_t dndPersistChecksumV1(const DndPersistV1 &st) {
  const uint8_t *b = reinterpret_cast<const uint8_t *>(&st);
  const size_t n = sizeof(DndPersistV1) - sizeof(st.checksum);
  uint32_t h = 2166136261UL;
  for (size_t i=0; i<n; ++i) { h ^= b[i]; h *= 16777619UL; }
  return h;
}

static void dndPersistCopyStringV1(char *dst, size_t n, const String &src) {
  if (!dst || n == 0) return;
  memset(dst, 0, n);
  src.substring(0, (int)n - 1).toCharArray(dst, n);
}

static void dndSaveState() {
  DndPersistV1 st{};
  st.magic = DND_SAVE_MAGIC_V1;
  st.version = DND_SAVE_VERSION_V1;
  st.size = sizeof(DndPersistV1);
  st.hp = dndHp;
  st.maxHp = dndMaxHp;
  st.strength = dndStrength;
  st.dexterity = dndDexterity;
  st.armorClass = dndArmorClass;
  st.xp = dndXp;
  st.gold = dndGold;
  st.level = dndLevel;
  st.keys = dndKeys;
  st.roomNumber = dndRoomNumber;
  st.deepestRoom = dndDeepestRoom;
  dndPersistCopyStringV1(st.weaponName, sizeof(st.weaponName), dndWeapon.name);
  st.weaponDamageMin = dndWeapon.damageMin;
  st.weaponDamageMax = dndWeapon.damageMax;
  st.weaponHitBonus = dndWeapon.hitBonus;
  st.weaponFoundRoom = dndWeapon.foundRoom;

  st.inventoryCount = dndInventoryCount > DND_SAVE_INV_CAP_V1 ? DND_SAVE_INV_CAP_V1 : dndInventoryCount;
  for (uint8_t i=0; i<st.inventoryCount; ++i) {
    dndPersistCopyStringV1(st.inventory[i], sizeof(st.inventory[i]), dndInventory[i]);
  }
  for (uint8_t i=0; i<4; ++i) st.shop[i] = dndShop[i];
  st.shopIndex = dndShopIndex;
  st.shopRoom = dndShopRoom;
  st.roomThemeIndex = dndRoomThemeIndex;
  st.checksum = dndPersistChecksumV1(st);

  Preferences prefs;
  if (!prefs.begin("bloomdnd", false)) {
    Serial.println("BP|DND_SAVE|ok=0|reason=prefs_begin");
    return;
  }
  size_t wrote = prefs.putBytes("state", &st, sizeof(st));
  prefs.end();
  Serial.printf("BP|DND_SAVE|ok=%u|bytes=%u|room=%u|gold=%lu|xp=%lu\n",
                wrote == sizeof(st) ? 1U : 0U, (unsigned)wrote,
                (unsigned)dndRoomNumber, (unsigned long)dndGold, (unsigned long)dndXp);
}

static bool dndLoadState() {
  Preferences prefs;
  if (!prefs.begin("bloomdnd", true)) return false;
  size_t len = prefs.getBytesLength("state");
  if (len != sizeof(DndPersistV1)) { prefs.end(); return false; }
  DndPersistV1 st{};
  size_t got = prefs.getBytes("state", &st, sizeof(st));
  prefs.end();
  if (got != sizeof(st) || st.magic != DND_SAVE_MAGIC_V1 ||
      st.version != DND_SAVE_VERSION_V1 || st.size != sizeof(DndPersistV1) ||
      st.checksum != dndPersistChecksumV1(st)) {
    Serial.println("BP|DND_LOAD|ok=0|reason=invalid");
    return false;
  }

  dndHp = st.hp;
  dndMaxHp = st.maxHp < 1 ? 18 : st.maxHp;
  if (dndHp < 0) dndHp = 0;
  if (dndHp > dndMaxHp) dndHp = dndMaxHp;
  dndStrength = st.strength;
  dndDexterity = st.dexterity;
  dndArmorClass = st.armorClass;
  dndXp = st.xp;
  dndGold = st.gold;
  dndLevel = st.level < 1 ? 1 : st.level;
  dndKeys = st.keys;
  dndRoomNumber = st.roomNumber < 1 ? 1 : st.roomNumber;
  dndDeepestRoom = st.deepestRoom < dndRoomNumber ? dndRoomNumber : st.deepestRoom;
  dndWeapon.name = String(st.weaponName);
  if (!dndWeapon.name.length()) dndWeapon.name = "IRON SWORD";
  dndWeapon.damageMin = st.weaponDamageMin;
  dndWeapon.damageMax = st.weaponDamageMax;
  dndWeapon.hitBonus = st.weaponHitBonus;
  dndWeapon.foundRoom = st.weaponFoundRoom;

  dndInventoryCount = st.inventoryCount > DND_SAVE_INV_CAP_V1 ? DND_SAVE_INV_CAP_V1 : st.inventoryCount;
  dndInventoryIndex = 0;
  for (uint8_t i=0; i<DND_INV_CAP; ++i) dndInventory[i] = "";
  for (uint8_t i=0; i<dndInventoryCount; ++i) dndInventory[i] = String(st.inventory[i]);
  for (uint8_t i=0; i<4; ++i) dndShop[i] = st.shop[i] < DND_ITEM_COUNT ? st.shop[i] : i;
  dndShopIndex = st.shopIndex < 4 ? st.shopIndex : 0;
  dndShopRoom = st.shopRoom;

  dndScreen = DND_PLAY;
  dndEventHead = dndEventTail = 0;
  dndCurrentEvent = "RESUME";
  dndEventUntilMs = millis() + 900UL;
  dndEventMarquee = 0;
  dndStatusFirst = 0;
  dndStatusRotateMs = millis();
  dndAttackArmedUntilMs = 0;
  for (uint8_t i=0; i<3; ++i) { dndStatusMarquee[i]=0; dndStatusMarqueeMs[i]=millis(); }

  // Regenerate the current room safely. Durable progression is preserved;
  // transient enemy positions/HP and event timers intentionally are not.
  dndGenerateRoom(false);
  dndRoomThemeIndex = st.roomThemeIndex % 48U;
  Serial.printf("BP|DND_LOAD|ok=1|room=%u|gold=%lu|xp=%lu|level=%u\n",
                (unsigned)dndRoomNumber, (unsigned long)dndGold,
                (unsigned long)dndXp, (unsigned)dndLevel);
  return true;
}

static uint32_t dndLastAutosaveMs = 0;

'''
s = s.replace(start_anchor, persist_block + start_anchor, 1)

# DND app entry: resume valid durable state; only reset when no save exists.
pat = re.compile(
    r'static\s+void\s+drawDndPlaceholder\s*\(\s*\)\s*\{(?P<body>.*?)\n\}',
    re.S,
)
m = pat.search(s)
if not m:
    raise SystemExit("drawDndPlaceholder definition not found")
body = m.group("body")
if "dndStartGame();" not in body:
    raise SystemExit("drawDndPlaceholder no longer starts DND via dndStartGame")
new_body = body.replace(
    "dndStartGame();",
    'if (dndLoadState()) { dndDrawPlay(); } else { dndStartGame(); dndSaveState(); }',
    1,
)
s = s[:m.start("body")] + new_body + s[m.end("body"):]

# Flush both app states at the shared launcher boundary. This is the key pet
# repair: saveSlot already serializes the whole PetSave, so save RAM before the
# slot picker can reload it from Preferences.
pat = re.compile(r'static\s+void\s+enterBloomSystemMenu\s*\(\s*\)\s*\{')
m = pat.search(s)
if not m:
    raise SystemExit("enterBloomSystemMenu definition not found")
insert_at = m.end()
flush = r'''
  // Persistence boundary: commit active app state before BLOOM SYSTEM.
  if (activeSlot < 3 && pets[activeSlot].occupied) saveSlot(activeSlot);
  if (uiMode == DND_PLACEHOLDER) dndSaveState();
'''
s = s[:insert_at] + flush + s[insert_at:]

# Feed/treat mutate PetSave directly. Make their menu actions immediately
# durable rather than relying only on a later app-exit flush.
s, feed_n = re.subn(
    r'(feedPet\(pets\[activeSlot\]\);)(\s*uiMode\s*=\s*HOME;)',
    r'\1 saveSlot(activeSlot);\2', s, count=1)
s, treat_n = re.subn(
    r'(giveTreat\(pets\[activeSlot\]\);)(\s*uiMode\s*=\s*HOME;)',
    r'\1 saveSlot(activeSlot);\2', s, count=1)

# DND periodic checkpoint: protects progression during battery use even if the
# player does not return to BLOOM SYSTEM before power is cut. 30 s limits NVS
# write frequency while keeping losses small.
pat = re.compile(r'static\s+void\s+dndServiceGame\s*\(\s*\)\s*\{')
m = pat.search(s)
if not m:
    raise SystemExit("dndServiceGame definition not found")
insert_at = m.end()
autosave = r'''
  if (uiMode == DND_PLACEHOLDER) {
    uint32_t persistNow = millis();
    if (dndLastAutosaveMs == 0 || persistNow - dndLastAutosaveMs >= 30000UL) {
      dndLastAutosaveMs = persistNow;
      dndSaveState();
    }
  }
'''
s = s[:insert_at] + autosave + s[insert_at:]

# Save a fresh DND state whenever a new game/reset path is explicitly executed.
# Insert before the final draw in dndStartGame, but only inside that function.
pat = re.compile(r'(static\s+void\s+dndStartGame\s*\(\s*\)\s*\{)(?P<body>.*?)(\n\})', re.S)
m = pat.search(s)
if not m:
    raise SystemExit("dndStartGame body not found after persistence insertion")
body = m.group("body")
last_draw = body.rfind("dndDrawPlay();")
if last_draw < 0:
    raise SystemExit("dndStartGame dndDrawPlay anchor not found")
body = body[:last_draw] + "dndSaveState();\n  " + body[last_draw:]
s = s[:m.start("body")] + body + s[m.end("body"):]

p.write_text(s)
print("PATCHED BLOOMPETZ + DND PERSISTENCE V1")
print("  pet: whole PetSave flushed before returning to BLOOM SYSTEM")
print("  pet: feed/treat saved immediately")
print("  DND: HP/maxHP/stats/XP/gold/level/keys/room/deepest room saved")
print("  DND: weapon, 12-item inventory, shop stock, and room theme saved")
print("  DND: resumes saved progression instead of resetting on every entry")
print("  DND: transient room enemies/map are regenerated safely on resume")
print("  DND: 30-second autosave plus save-on-system-exit")
print("patched:", p)
