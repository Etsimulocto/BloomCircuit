#!/usr/bin/env python3
"""Add persistent editable custom marquee sayings to staged HAPPY JARZ firmware.

Provides 8 business/user-editable slots stored in ESP32 Preferences.
Serial protocol:
  GET CUSTOM SAYINGS
  SET CUSTOM SAYING <1-8> <text>
  CLEAR CUSTOM SAYINGS
  SET SAYING SOURCE BUILTIN|CUSTOM|MIXED

Runs after the normal screensaver + expanded sayings patches.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_custom_sayings.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

needle = 'static constexpr uint8_t HJ_SAYING_COUNT = sizeof(HJ_SAYINGS)/sizeof(HJ_SAYINGS[0]);\n'
if needle not in s:
    raise SystemExit("custom sayings patch failed: saying count marker not found")

block = r'''
static constexpr uint8_t HJ_CUSTOM_SAYING_SLOTS = 8;
static String hjCustomSayings[HJ_CUSTOM_SAYING_SLOTS];
static String hjSayingSource = "BUILTIN";
static int8_t hjCustomActiveSlot = -1;

static void hjLoadCustomSayings() {
  prefs.begin("happyjarz", true);
  hjSayingSource = prefs.getString("say_src", "BUILTIN");
  for (uint8_t i=0; i<HJ_CUSTOM_SAYING_SLOTS; ++i) {
    String key = "say" + String(i);
    hjCustomSayings[i] = prefs.getString(key.c_str(), "");
  }
  prefs.end();
}

static void hjSaveCustomSaying(uint8_t slot, const String &text) {
  if (slot >= HJ_CUSTOM_SAYING_SLOTS) return;
  hjCustomSayings[slot] = text;
  prefs.begin("happyjarz", false);
  String key = "say" + String(slot);
  prefs.putString(key.c_str(), text);
  prefs.end();
}

static void hjSetSayingSource(const String &source) {
  hjSayingSource = source;
  prefs.begin("happyjarz", false);
  prefs.putString("say_src", source);
  prefs.end();
}

static uint8_t hjCustomCount() {
  uint8_t count=0;
  for (uint8_t i=0; i<HJ_CUSTOM_SAYING_SLOTS; ++i) if (hjCustomSayings[i].length()) count++;
  return count;
}

static int8_t hjPickCustomSlot() {
  uint8_t count = hjCustomCount();
  if (!count) return -1;
  uint8_t target = (uint8_t)random(count);
  for (uint8_t i=0; i<HJ_CUSTOM_SAYING_SLOTS; ++i) {
    if (!hjCustomSayings[i].length()) continue;
    if (target == 0) return (int8_t)i;
    target--;
  }
  return -1;
}

static void hjPickNextSaying() {
  bool useCustom = false;
  uint8_t customCount = hjCustomCount();
  if (hjSayingSource == "CUSTOM") useCustom = customCount > 0;
  else if (hjSayingSource == "MIXED") useCustom = customCount > 0 && random(2) == 0;

  if (useCustom) {
    hjCustomActiveSlot = hjPickCustomSlot();
  } else {
    hjCustomActiveSlot = -1;
    hjSayingIndex = (uint8_t)random(HJ_SAYING_COUNT);
  }
}

static const char *hjCurrentSaying() {
  if (hjCustomActiveSlot >= 0 && hjCustomActiveSlot < HJ_CUSTOM_SAYING_SLOTS)
    return hjCustomSayings[hjCustomActiveSlot].c_str();
  return HJ_SAYINGS[hjSayingIndex];
}

static void hjPrintCustomSayings() {
  Serial.print("HJ|CUSTOM_SAYINGS|BEGIN|source="); Serial.println(hjSayingSource);
  for (uint8_t i=0; i<HJ_CUSTOM_SAYING_SLOTS; ++i) {
    Serial.print("HJ|CUSTOM_SAYING|slot="); Serial.print(i+1);
    Serial.print("|text="); Serial.println(hjCustomSayings[i]);
  }
  Serial.print("HJ|CUSTOM_SAYINGS|END|source="); Serial.println(hjSayingSource);
}
'''
s = s.replace(needle, needle + block, 1)

# Pick source-aware saying when saver starts / changes mode.
s = s.replace('  hjSayingIndex = (uint8_t)random(HJ_SAYING_COUNT);\n  hjArtStep = 0;\n  oledDirty = true;\n}',
              '  hjPickNextSaying();\n  hjArtStep = 0;\n  oledDirty = true;\n}', 3)

old_render = '''static void oledRenderSaverSayings() {
  oled->setFont(u8g2_font_7x14B_tr);
  const char *msg = HJ_SAYINGS[hjSayingIndex];
  int width = oled->getUTF8Width(msg);
  oled->drawUTF8(hjMarqueeX, hjMarqueeY, msg);
  if (hjMarqueeX < -width - 18) {
    hjSayingIndex = (uint8_t)random(HJ_SAYING_COUNT);
    hjMarqueeX = 128;
    hjMarqueeY = hjPickMarqueeY();
  }
}
'''
new_render = '''static void oledRenderSaverSayings() {
  oled->setFont(u8g2_font_7x14B_tr);
  const char *msg = hjCurrentSaying();
  int width = oled->getUTF8Width(msg);
  oled->drawUTF8(hjMarqueeX, hjMarqueeY, msg);
  if (hjMarqueeX < -width - 18) {
    hjPickNextSaying();
    hjMarqueeX = 128;
    hjMarqueeY = hjPickMarqueeY();
  }
}
'''
if old_render not in s:
    raise SystemExit("custom sayings patch failed: expanded marquee renderer not found")
s = s.replace(old_render, new_render, 1)

# Load custom sayings after preferences infrastructure exists and before OLED saver can run.
setup_needle = '  oledInit();\n  hjScreensaverTouch();\n'
if setup_needle not in s:
    raise SystemExit("custom sayings patch failed: setup load point not found")
s = s.replace(setup_needle, '  hjLoadCustomSayings();\n' + setup_needle, 1)

# Add serial protocol before SAVE.
cmd_needle = '  if(line=="SAVE"){persistSettings();ack("SAVE");return;}\n'
if cmd_needle not in s:
    raise SystemExit("custom sayings patch failed: SAVE command marker not found")
cmd_block = r'''  if(line=="GET CUSTOM SAYINGS"){hjPrintCustomSayings();return;}
  if(line=="CLEAR CUSTOM SAYINGS"){
    for(uint8_t i=0;i<HJ_CUSTOM_SAYING_SLOTS;++i) hjSaveCustomSaying(i,"");
    hjCustomActiveSlot=-1; ack("CLEAR CUSTOM SAYINGS"); return;
  }
  if(line.startsWith("SET SAYING SOURCE ")){
    String v=line.substring(18); v.trim(); v.toUpperCase();
    if(v=="BUILTIN"||v=="CUSTOM"||v=="MIXED"){
      hjSetSayingSource(v); hjPickNextSaying(); hjMarqueeX=128; oledDirty=true; ack("SET SAYING SOURCE");
    } else err("saying source must be BUILTIN CUSTOM or MIXED");
    return;
  }
  if(line.startsWith("SET CUSTOM SAYING ")){
    String rest=line.substring(18); rest.trim();
    int split=rest.indexOf(' ');
    if(split<1){err("custom saying requires slot and text");return;}
    int slot=rest.substring(0,split).toInt();
    String text=rest.substring(split+1); text.trim();
    text.replace("|","/"); text.replace("\r"," "); text.replace("\n"," ");
    if(slot<1||slot>HJ_CUSTOM_SAYING_SLOTS){err("custom saying slot must be 1-8");return;}
    if(text.length()>96) text=text.substring(0,96);
    hjSaveCustomSaying((uint8_t)(slot-1),text); ack("SET CUSTOM SAYING"); return;
  }
'''
s = s.replace(cmd_needle, cmd_block + cmd_needle, 1)

p.write_text(s, encoding="utf-8")
