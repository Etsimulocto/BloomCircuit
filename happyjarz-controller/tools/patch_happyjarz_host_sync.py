#!/usr/bin/env python3
"""Add unified host-control and OLED-mirror protocol to staged HAPPY JARZ firmware.

Runs late in the staging chain after OLED/games/screensavers and four-light
support are present.

Goals:
- app/keyboard/gamepad buttons enter the SAME serviceInputs() path as copper touch
- SIMPLE advertises only its six proven controls
- OLED mirror comes from the actual U8g2 framebuffer after sendBuffer()
- one existing USB serial connection owns control + telemetry
- mirror traffic is change-driven and capped at 4 Hz so it cannot become an
  accidental full-speed serial flood
"""

from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_host_sync.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

def fail(msg):
    raise SystemExit("host-sync patch failed: " + msg)

# ---------------------------------------------------------------------------
# Host virtual input queue: six proven SIMPLE controls.
# ---------------------------------------------------------------------------
marker = 'static bool bHomeSent = false;\n'
if marker not in s:
    fail("input-state marker not found")

input_block = r'''
// Host/app virtual keys join the SAME logical input path as copper touch.
static bool hjHostKeyPending[INPUT_COUNT] = {false,false,false,false,false,false};

static int8_t hjHostKeyIndex(String name) {
  name.trim();
  name.toUpperCase();
  if (name == "UP") return IN_UP;
  if (name == "DOWN") return IN_DOWN;
  if (name == "LEFT") return IN_LEFT;
  if (name == "RIGHT") return IN_RIGHT;
  if (name == "A") return IN_A;
  if (name == "B") return IN_B;
  return -1;
}

static void hjPrintCaps() {
  Serial.println("HJ|CAPS|profile=SIMPLE|controls=up,down,left,right,a,b|oled=128x64|oled_mirror=1|leds=4");
}
'''
s = s.replace(marker, marker + input_block, 1)

service_marker = '''static void serviceInputs() {
  bool q[INPUT_COUNT];
  for (uint8_t i=0;i<INPUT_COUNT;++i) q[i]=updateInputState(i);
'''
if service_marker not in s:
    fail("serviceInputs scan marker not found")

service_repl = service_marker + r'''  // Merge one-shot host events after reading physical touch. Existing menu,
  // game, saver and HOME code below this point sees one unified q[] array.
  for (uint8_t i=0; i<INPUT_COUNT; ++i) {
    if (hjHostKeyPending[i]) {
      q[i] = true;
      hjHostKeyPending[i] = false;
    }
  }
'''
s = s.replace(service_marker, service_repl, 1)

# ---------------------------------------------------------------------------
# OLED framebuffer mirror. Replace all existing U8g2 presents FIRST, then add
# the helper so its internal sendBuffer() is not recursively rewritten.
# ---------------------------------------------------------------------------
present_count = s.count('oled->sendBuffer();')
if present_count < 1:
    fail("no oled->sendBuffer() calls found")
s = s.replace('oled->sendBuffer();', 'hjOledPresent();')

oled_marker = '''static bool oledDirty = true;
static unsigned long oledLastDrawMs = 0;
'''
if oled_marker not in s:
    fail("OLED state marker not found")

oled_block = r'''
// Host OLED mirror: actual 128x64 U8g2 framebuffer, Base64 encoded.
// 1024 raw bytes -> 1368 Base64 chars. Frames are change-driven and <= 4 Hz.
static bool hjOledStream = false;
static bool hjOledHaveFrame = false;
static uint8_t hjOledLastFrame[1024];
static uint32_t hjOledSeq = 0;
static unsigned long hjOledLastMirrorMs = 0;

static void hjPrintBase64(const uint8_t *data, size_t len) {
  static const char table[] =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  size_t i = 0;
  while (i + 2 < len) {
    uint32_t v = ((uint32_t)data[i] << 16) |
                 ((uint32_t)data[i+1] << 8) |
                 (uint32_t)data[i+2];
    Serial.write(table[(v >> 18) & 63]);
    Serial.write(table[(v >> 12) & 63]);
    Serial.write(table[(v >> 6) & 63]);
    Serial.write(table[v & 63]);
    i += 3;
  }
  if (i < len) {
    uint32_t v = (uint32_t)data[i] << 16;
    bool two = (i + 1 < len);
    if (two) v |= (uint32_t)data[i+1] << 8;
    Serial.write(table[(v >> 18) & 63]);
    Serial.write(table[(v >> 12) & 63]);
    Serial.write(two ? table[(v >> 6) & 63] : '=');
    Serial.write('=');
  }
}

static void hjEmitOledFrame(bool force) {
  if (!oledReady || !oled || !Serial) return;
  if (!force && !hjOledStream) return;

  unsigned long now = millis();
  if (!force && now - hjOledLastMirrorMs < 250) return;

  uint8_t *buf = oled->getBufferPtr();
  if (!buf) return;

  bool changed = !hjOledHaveFrame ||
                 memcmp(hjOledLastFrame, buf, sizeof(hjOledLastFrame)) != 0;
  if (!force && !changed) return;

  hjOledLastMirrorMs = now;
  memcpy(hjOledLastFrame, buf, sizeof(hjOledLastFrame));
  hjOledHaveFrame = true;

  Serial.print("HJ|OLED|seq=");
  Serial.print(++hjOledSeq);
  Serial.print("|codec=b64v1|bytes=1024|data=");
  hjPrintBase64(buf, 1024);
  Serial.println();
}

static void hjOledPresent() {
  if (!oled) return;
  oled->sendBuffer();
  hjEmitOledFrame(false);
}
'''
s = s.replace(oled_marker, oled_marker + oled_block, 1)

# ---------------------------------------------------------------------------
# Serial protocol: capabilities, virtual keys and mirror control.
# ---------------------------------------------------------------------------
cmd_marker = '  if(line=="GET STATUS"){Serial.println(statusLine());return;}\n'
if cmd_marker not in s:
    fail("GET STATUS command marker not found")

commands = r'''  if(line=="GET CAPS"){hjPrintCaps();return;}
  if(line=="GET OLED"){hjEmitOledFrame(true);return;}
  if(line=="STREAM OLED ON"){
    hjOledStream=true;
    ack("STREAM OLED ON");
    hjEmitOledFrame(true);
    return;
  }
  if(line=="STREAM OLED OFF"){
    hjOledStream=false;
    ack("STREAM OLED OFF");
    return;
  }
  if(line.startsWith("KEY ")){
    String key=line.substring(4);
    key.trim();
    int8_t idx=hjHostKeyIndex(key);
    if(idx < 0){
      err("key unsupported by SIMPLE profile");
      return;
    }
    hjHostKeyPending[(uint8_t)idx]=true;
    Serial.print("HJ|EVENT|input=");
    key.toLowerCase();
    Serial.print(key);
    Serial.println("|source=host");
    ack("KEY");
    return;
  }
'''
s = s.replace(cmd_marker, cmd_marker + commands, 1)

p.write_text(s, encoding="utf-8")
print(
    "Applied HAPPY JARZ host sync: SIMPLE KEY input + CAPS + actual OLED framebuffer mirror."
)
