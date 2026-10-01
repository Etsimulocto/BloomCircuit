#!/usr/bin/env python3
"""Add desktop serial controls/status for the current HAPPY JARZ screensaver engine.

Runs after patch_happyjarz_saver_controls.py.
Protocol:
  GET SAVER STATUS
  SAVER ENTER
  SAVER EXIT
  SAVER NEXT
  SAVER PREV
  SAVER RESEED
  SAVER SPEED UP
  SAVER SPEED DOWN
  SET SAVER MODE SAYINGS|SPIRAL|TRIPPY
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_saver_protocol.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

marker = '''static void hjReseedTrippy() {
  hjTrippySeed = hjBoardEntropy() ^ 0x54524950UL;
  hjArtStep = 0;
}
'''
if marker not in s:
    raise SystemExit("saver protocol patch failed: reseed marker not found")

helpers = r'''

static const char *hjSaverModeName() {
  if (hjScreensaverMode == 0) return "SAYINGS";
  if (hjScreensaverMode == 1) return "SPIRAL";
  return "TRIPPY";
}

static void hjSaverReseedCurrent() {
  if (hjScreensaverMode == 1) hjReseedSpiral();
  else if (hjScreensaverMode == 2) hjReseedTrippy();
}

static void hjSaverPrepareCurrent() {
  hjArtStep = 0;
  if (hjScreensaverMode == 0) {
    hjPickNextSaying();
    hjMarqueeX = 128;
  } else {
    hjSaverReseedCurrent();
  }
  oledDirty = true;
}

static void hjSaverSetMode(uint8_t mode, bool activate) {
  hjScreensaverMode = mode % HJ_SCREENSAVER_COUNT;
  if (activate) hjScreensaverActive = true;
  hjSaverPrepareCurrent();
}

static void hjPrintSaverStatus() {
  Serial.print("HJ|SAVER|active="); Serial.print(hjScreensaverActive ? 1 : 0);
  Serial.print("|mode="); Serial.print(hjSaverModeName());
  Serial.print("|idle_ms="); Serial.print(HJ_SCREENSAVER_IDLE_MS);
  Serial.print("|spiral_speed="); Serial.print(hjSpiralSpeed);
  Serial.print("|trippy_speed="); Serial.println(hjTrippySpeed);
}
'''
s = s.replace(marker, marker + helpers, 1)

cmd_needle = '  if(line=="SAVE"){persistSettings();ack("SAVE");return;}\n'
if cmd_needle not in s:
    raise SystemExit("saver protocol patch failed: SAVE command marker not found")

cmds = r'''  if(line=="GET SAVER STATUS"){hjPrintSaverStatus();return;}
  if(line=="SAVER ENTER"){
    hjScreensaverEnter(); hjSaverPrepareCurrent(); ack("SAVER ENTER"); hjPrintSaverStatus(); return;
  }
  if(line=="SAVER EXIT"){
    hjScreensaverExit(); ack("SAVER EXIT"); hjPrintSaverStatus(); return;
  }
  if(line=="SAVER NEXT"){
    hjScreensaverNext(); hjSaverPrepareCurrent(); ack("SAVER NEXT"); hjPrintSaverStatus(); return;
  }
  if(line=="SAVER PREV"){
    hjScreensaverPrev(); hjSaverPrepareCurrent(); ack("SAVER PREV"); hjPrintSaverStatus(); return;
  }
  if(line=="SAVER RESEED"){
    hjSaverPrepareCurrent(); ack("SAVER RESEED"); hjPrintSaverStatus(); return;
  }
  if(line=="SAVER SPEED UP"){
    if(hjScreensaverMode==1 && hjSpiralSpeed<8) hjSpiralSpeed++;
    else if(hjScreensaverMode==2 && hjTrippySpeed<8) hjTrippySpeed++;
    ack("SAVER SPEED UP"); hjPrintSaverStatus(); return;
  }
  if(line=="SAVER SPEED DOWN"){
    if(hjScreensaverMode==1 && hjSpiralSpeed>1) hjSpiralSpeed--;
    else if(hjScreensaverMode==2 && hjTrippySpeed>1) hjTrippySpeed--;
    ack("SAVER SPEED DOWN"); hjPrintSaverStatus(); return;
  }
  if(line.startsWith("SET SAVER MODE ")){
    String v=line.substring(15); v.trim(); v.toUpperCase();
    if(v=="SAYINGS") hjSaverSetMode(0,true);
    else if(v=="SPIRAL") hjSaverSetMode(1,true);
    else if(v=="TRIPPY") hjSaverSetMode(2,true);
    else {err("saver mode must be SAYINGS SPIRAL or TRIPPY");return;}
    ack("SET SAVER MODE"); hjPrintSaverStatus(); return;
  }
'''
s = s.replace(cmd_needle, cmds + cmd_needle, 1)

p.write_text(s, encoding="utf-8")
