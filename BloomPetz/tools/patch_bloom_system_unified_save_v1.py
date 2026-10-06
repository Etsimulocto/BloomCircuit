#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_bloom_system_unified_save_v1.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_SYSTEM_UNIFIED_SAVE_V1"
if marker in s:
    print("Unified BLOOM SYSTEM save patch already present")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".pre_bloom_system_unified_save_v1")
if not backup.exists():
    backup.write_text(s)


def find_function(src: str, signature_regex: str):
    m = re.search(signature_regex, src)
    if not m:
        raise SystemExit(f"function not found: {signature_regex}")
    open_brace = src.find('{', m.start())
    if open_brace < 0:
        raise SystemExit(f"opening brace not found: {signature_regex}")
    depth = 0
    i = open_brace
    while i < len(src):
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return m.start(), open_brace, i + 1
        i += 1
    raise SystemExit(f"closing brace not found: {signature_regex}")


def replace_body(src: str, signature_regex: str, body: str):
    start, ob, end = find_function(src, signature_regex)
    return src[:ob+1] + "\n" + body.rstrip() + "\n" + src[end-1:]

# -----------------------------------------------------------------------------
# Remove the earlier separate DND persistence experiment. It never compiled,
# so no on-device save format depends on it.
# -----------------------------------------------------------------------------
old_marker = "// BLOOM_PET_DND_PERSISTENCE_V1"
if old_marker in s:
    a = s.index(old_marker)
    b = s.find("static void dndStartGame() {", a)
    if b < 0:
        raise SystemExit("could not locate end of old persistence block")
    s = s[:a] + s[b:]

# Remove any failed forward-declaration repair if it somehow landed locally.
s = s.replace("// BLOOM_DND_PERSIST_TYPE_VISIBILITY_V1\nstruct DndPersistV1;\n\n", "")
s = s.replace("// BLOOM_DND_PERSIST_TYPE_VISIBILITY_V2\nstruct DndPersistV1;\n\n", "")
s = s.replace("// BLOOM_DND_PERSIST_TYPE_VISIBILITY_V3\nstruct DndPersistV1;\n\n", "")

# One harmless forward declaration lets early PetSave saveSlot() calls route to
# the unified writer whose implementation lives later, after DND globals exist.
forward = "// BLOOM_SYSTEM_UNIFIED_SAVE_FORWARD_V1\nstatic void saveBloomSystemState();\nstatic bool loadBloomSystemState();\n\n"
lines = s.splitlines(True)
idx = 0
while idx < len(lines) and (lines[idx].lstrip().startswith('#include') or lines[idx].strip() == ''):
    idx += 1
lines.insert(idx, forward)
s = ''.join(lines)

# Existing Petz code already calls saveSlot() at the right mutation points.
# Turn it into a compatibility wrapper so those calls now write ONE BLOOM blob.
s = replace_body(
    s,
    r'static\s+void\s+saveSlot\s*\(\s*uint8_t\s+slot\s*\)',
    r'''  if (slot < 3) pets[slot].checksum = petChecksum(pets[slot]);
  saveBloomSystemState();'''
)

# -----------------------------------------------------------------------------
# Unified durable record. No function signature mentions this custom type, so
# Arduino's generated prototypes cannot trip over it.
# -----------------------------------------------------------------------------
anchor = "static void dndStartGame() {"
if anchor not in s:
    raise SystemExit("dndStartGame anchor not found")

block = r'''// BLOOM_SYSTEM_UNIFIED_SAVE_V1
// One authoritative durable record for all three BloomPetz slots + DND.
static const uint32_t BLOOM_SAVE_MAGIC_V1 = 0x424C4D31UL; // BLM1
static const uint16_t BLOOM_SAVE_VERSION_V1 = 1;
static const uint8_t BLOOM_SAVE_INV_CAP_V1 = 12;
static const uint8_t BLOOM_SAVE_NAME_LEN_V1 = 24;

struct BloomDndDurableV1 {
  uint8_t valid;
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
  char weaponName[BLOOM_SAVE_NAME_LEN_V1];
  int16_t weaponDamageMin;
  int16_t weaponDamageMax;
  int16_t weaponHitBonus;
  uint16_t weaponFoundRoom;
  uint8_t inventoryCount;
  char inventory[BLOOM_SAVE_INV_CAP_V1][BLOOM_SAVE_NAME_LEN_V1];
  uint8_t shop[4];
  uint8_t shopIndex;
  uint16_t shopRoom;
  uint8_t roomThemeIndex;
};

struct BloomSystemSaveV1 {
  uint32_t magic;
  uint16_t version;
  uint16_t size;
  uint8_t activePetSlot;
  uint8_t reserved[3];
  PetSave pet[3];
  BloomDndDurableV1 dnd;
  uint32_t checksum;
};

static bool bloomDndHasState = false;
static uint32_t bloomUnifiedLastAutosaveMs = 0;
static bool bloomUnifiedLoadedOnce = false;

static uint32_t bloomUnifiedChecksumBytes(const uint8_t *data, size_t n) {
  uint32_t h = 2166136261UL;
  for (size_t i=0; i<n; ++i) { h ^= data[i]; h *= 16777619UL; }
  return h;
}

static void bloomUnifiedCopyText(char *dst, size_t n, const String &src) {
  if (!dst || n == 0) return;
  memset(dst, 0, n);
  src.substring(0, (int)n - 1).toCharArray(dst, n);
}

static void saveBloomSystemState() {
  static BloomSystemSaveV1 st;
  memset(&st, 0, sizeof(st));
  st.magic = BLOOM_SAVE_MAGIC_V1;
  st.version = BLOOM_SAVE_VERSION_V1;
  st.size = sizeof(BloomSystemSaveV1);
  st.activePetSlot = activeSlot < 3 ? activeSlot : 0;

  for (uint8_t i=0; i<3; ++i) {
    if (pets[i].occupied) pets[i].checksum = petChecksum(pets[i]);
    memcpy(&st.pet[i], &pets[i], sizeof(PetSave));
  }

  st.dnd.valid = bloomDndHasState ? 1U : 0U;
  if (bloomDndHasState) {
    st.dnd.hp = dndHp;
    st.dnd.maxHp = dndMaxHp;
    st.dnd.strength = dndStrength;
    st.dnd.dexterity = dndDexterity;
    st.dnd.armorClass = dndArmorClass;
    st.dnd.xp = dndXp;
    st.dnd.gold = dndGold;
    st.dnd.level = dndLevel;
    st.dnd.keys = dndKeys;
    st.dnd.roomNumber = dndRoomNumber;
    st.dnd.deepestRoom = dndDeepestRoom;
    bloomUnifiedCopyText(st.dnd.weaponName, sizeof(st.dnd.weaponName), dndWeapon.name);
    st.dnd.weaponDamageMin = dndWeapon.damageMin;
    st.dnd.weaponDamageMax = dndWeapon.damageMax;
    st.dnd.weaponHitBonus = dndWeapon.hitBonus;
    st.dnd.weaponFoundRoom = dndWeapon.foundRoom;
    st.dnd.inventoryCount = dndInventoryCount > BLOOM_SAVE_INV_CAP_V1 ? BLOOM_SAVE_INV_CAP_V1 : dndInventoryCount;
    for (uint8_t i=0; i<st.dnd.inventoryCount; ++i)
      bloomUnifiedCopyText(st.dnd.inventory[i], sizeof(st.dnd.inventory[i]), dndInventory[i]);
    for (uint8_t i=0; i<4; ++i) st.dnd.shop[i] = dndShop[i];
    st.dnd.shopIndex = dndShopIndex;
    st.dnd.shopRoom = dndShopRoom;
    st.dnd.roomThemeIndex = dndRoomThemeIndex;
  }

  st.checksum = bloomUnifiedChecksumBytes(reinterpret_cast<const uint8_t *>(&st), sizeof(st) - sizeof(st.checksum));

  Preferences prefs;
  if (!prefs.begin("bloomsys", false)) {
    Serial.println("BP|BLOOM_SAVE|ok=0|reason=prefs_begin");
    return;
  }
  size_t wrote = prefs.putBytes("state", &st, sizeof(st));
  prefs.end();
  Serial.printf("BP|BLOOM_SAVE|ok=%u|bytes=%u|slot=%u|dnd=%u|room=%u\n",
                wrote == sizeof(st) ? 1U : 0U, (unsigned)wrote,
                (unsigned)st.activePetSlot, (unsigned)st.dnd.valid,
                (unsigned)(st.dnd.valid ? st.dnd.roomNumber : 0));
}

static bool loadBloomSystemState() {
  static BloomSystemSaveV1 st;
  Preferences prefs;
  if (!prefs.begin("bloomsys", true)) return false;
  size_t len = prefs.getBytesLength("state");
  if (len != sizeof(st)) { prefs.end(); return false; }
  size_t got = prefs.getBytes("state", &st, sizeof(st));
  prefs.end();
  if (got != sizeof(st) || st.magic != BLOOM_SAVE_MAGIC_V1 ||
      st.version != BLOOM_SAVE_VERSION_V1 || st.size != sizeof(st)) return false;
  uint32_t want = bloomUnifiedChecksumBytes(reinterpret_cast<const uint8_t *>(&st), sizeof(st) - sizeof(st.checksum));
  if (want != st.checksum) {
    Serial.println("BP|BLOOM_LOAD|ok=0|reason=checksum");
    return false;
  }

  for (uint8_t i=0; i<3; ++i) memcpy(&pets[i], &st.pet[i], sizeof(PetSave));
  activeSlot = st.activePetSlot < 3 ? st.activePetSlot : 0;

  bloomDndHasState = st.dnd.valid != 0;
  if (bloomDndHasState) {
    dndHp = st.dnd.hp;
    dndMaxHp = st.dnd.maxHp < 1 ? 18 : st.dnd.maxHp;
    if (dndHp < 0) dndHp = 0;
    if (dndHp > dndMaxHp) dndHp = dndMaxHp;
    dndStrength = st.dnd.strength;
    dndDexterity = st.dnd.dexterity;
    dndArmorClass = st.dnd.armorClass;
    dndXp = st.dnd.xp;
    dndGold = st.dnd.gold;
    dndLevel = st.dnd.level < 1 ? 1 : st.dnd.level;
    dndKeys = st.dnd.keys;
    dndRoomNumber = st.dnd.roomNumber < 1 ? 1 : st.dnd.roomNumber;
    dndDeepestRoom = st.dnd.deepestRoom < dndRoomNumber ? dndRoomNumber : st.dnd.deepestRoom;
    dndWeapon.name = String(st.dnd.weaponName);
    if (!dndWeapon.name.length()) dndWeapon.name = "IRON SWORD";
    dndWeapon.damageMin = st.dnd.weaponDamageMin;
    dndWeapon.damageMax = st.dnd.weaponDamageMax;
    dndWeapon.hitBonus = st.dnd.weaponHitBonus;
    dndWeapon.foundRoom = st.dnd.weaponFoundRoom;
    dndInventoryCount = st.dnd.inventoryCount > BLOOM_SAVE_INV_CAP_V1 ? BLOOM_SAVE_INV_CAP_V1 : st.dnd.inventoryCount;
    dndInventoryIndex = 0;
    for (uint8_t i=0; i<DND_INV_CAP; ++i) dndInventory[i] = "";
    for (uint8_t i=0; i<dndInventoryCount; ++i) dndInventory[i] = String(st.dnd.inventory[i]);
    for (uint8_t i=0; i<4; ++i) dndShop[i] = st.dnd.shop[i] < DND_ITEM_COUNT ? st.dnd.shop[i] : i;
    dndShopIndex = st.dnd.shopIndex < 4 ? st.dnd.shopIndex : 0;
    dndShopRoom = st.dnd.shopRoom;
    dndRoomThemeIndex = st.dnd.roomThemeIndex % 48U;
  }

  Serial.printf("BP|BLOOM_LOAD|ok=1|slot=%u|dnd=%u|room=%u\n",
                (unsigned)activeSlot, bloomDndHasState ? 1U : 0U,
                (unsigned)(bloomDndHasState ? dndRoomNumber : 0));
  return true;
}

static void resumeBloomDndFromUnifiedSave() {
  dndScreen = DND_PLAY;
  dndEventHead = dndEventTail = 0;
  dndCurrentEvent = "RESUME";
  dndEventUntilMs = millis() + 900UL;
  dndEventMarquee = 0;
  dndStatusFirst = 0;
  dndStatusRotateMs = millis();
  dndAttackArmedUntilMs = 0;
  for (uint8_t i=0; i<3; ++i) { dndStatusMarquee[i]=0; dndStatusMarqueeMs[i]=millis(); }
  dndGenerateRoom(false);
  dndDrawPlay();
}

'''
s = s.replace(anchor, block + anchor, 1)

# New-game initialization becomes the moment DND gains a durable save.
start, ob, end = find_function(s, r'static\s+void\s+dndStartGame\s*\(\s*\)')
body = s[ob+1:end-1]
body = body.replace("dndSaveState();", "")
last_draw = body.rfind("dndDrawPlay();")
if last_draw < 0:
    raise SystemExit("dndStartGame draw anchor not found")
body = body[:last_draw] + "bloomDndHasState = true;\n  saveBloomSystemState();\n  " + body[last_draw:]
s = s[:ob+1] + "\n" + body.strip("\n") + "\n" + s[end-1:]

# DND app entry: resume durable progression if available; otherwise new game.
s = replace_body(
    s,
    r'static\s+void\s+drawDndPlaceholder\s*\(\s*\)',
    r'''  if (bloomDndHasState) resumeBloomDndFromUnifiedSave();
  else dndStartGame();'''
)

# Shared app boundary: one save for whichever app was active.
s = replace_body(
    s,
    r'static\s+void\s+enterBloomSystemMenu\s*\(\s*\)',
    r'''  saveBloomSystemState();
  uiMode = SYSTEM_MENU;
  bloomSystemGameIndex = 0;
  drawBloomSystemMenu();'''
)

# Boot: existing legacy pet loader gets first chance. Then unified state wins if
# present; otherwise current recovered RAM state is migrated into the new blob.
start, ob, end = find_function(s, r'static\s+void\s+beginBootSplash\s*\(\s*\)')
body = s[ob+1:end-1]
boot_prefix = r'''  if (!bloomUnifiedLoadedOnce) {
    bloomUnifiedLoadedOnce = true;
    if (!loadBloomSystemState()) {
      Serial.println("BP|BLOOM_LOAD|ok=0|source=legacy_migrate");
      saveBloomSystemState();
    }
  }
'''
# Avoid doubling if a retry script is ever partially applied.
if "bloomUnifiedLoadedOnce" not in body:
    body = "\n" + boot_prefix + body
s = s[:ob+1] + body + s[end-1:]

# DND autosave: replace the old separate-persistence prefix if present, then
# prepend a unified 30-second checkpoint.
start, ob, end = find_function(s, r'static\s+void\s+dndServiceGame\s*\(\s*\)')
body = s[ob+1:end-1]
body = re.sub(
    r'\s*if\s*\(uiMode\s*==\s*DND_PLACEHOLDER\)\s*\{\s*uint32_t\s+persistNow\s*=\s*millis\(\);.*?dndSaveState\(\);\s*\}\s*\}',
    '', body, count=1, flags=re.S)
auto = r'''  if (uiMode == DND_PLACEHOLDER && bloomDndHasState) {
    uint32_t nowSave = millis();
    if (bloomUnifiedLastAutosaveMs == 0 || nowSave - bloomUnifiedLastAutosaveMs >= 30000UL) {
      bloomUnifiedLastAutosaveMs = nowSave;
      saveBloomSystemState();
    }
  }
'''
body = "\n" + auto + body.lstrip("\n")
s = s[:ob+1] + body + s[end-1:]

# Any old explicit separate-DND save/load calls left by the abandoned patch are
# invalid in the unified architecture and must not survive compilation.
s = s.replace("dndSaveState();", "saveBloomSystemState();")
s = s.replace("if (dndLoadState()) { dndDrawPlay(); } else { dndStartGame(); saveBloomSystemState(); }",
              "if (bloomDndHasState) resumeBloomDndFromUnifiedSave(); else dndStartGame();")

p.write_text(s)
print("PATCHED BLOOM SYSTEM UNIFIED SAVE V1")
print("  one Preferences blob: bloomsys/state")
print("  contains all 3 complete PetSave records + active slot + DND progression")
print("  existing saveSlot() calls now route into the unified blob")
print("  first boot migrates whatever the legacy pet loader recovered")
print("  DND resumes progression instead of resetting on app re-entry")
print("  DND transient map/enemies regenerate safely on resume")
print("  save on app boundary + existing Petz mutation points + 30s DND checkpoint")
print("patched:", p)
