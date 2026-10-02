#!/usr/bin/env python3
"""Add desktop serial controls/status for the current HAPPY JARZ screensaver engine.

Runs after patch_happyjarz_saver_controls.py. Before adding protocol commands it
applies smooth SPIRAL/TRIPPY drift, then the particle-universe layer. After the
saver protocol is staged it applies the Fuel Gauge layer, so the standard
flasher needs no new manual step.

Protocol:
  GET SAVER STATUS
  SAVER ENTER
  SAVER EXIT
  SAVER NEXT
  SAVER PREV
  SAVER RESEED
  SAVER SPEED UP
  SAVER SPEED DOWN
  SET SAVER MODE SAYINGS|SPIRAL|TRIPPY|PARTICLES
"""
from pathlib import Path
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_saver_protocol.py <staged .ino>")

p = Path(sys.argv[1])

smooth_patch = Path(__file__).with_name("patch_happyjarz_saver_smooth_drift.py")
if not smooth_patch.exists():
    raise SystemExit(f"saver protocol patch failed: missing {smooth_patch.name}")
subprocess.run([sys.executable, str(smooth_patch), str(p)], check=True)

# The particle patch predates the evolving TRIPPY reseed body and still matches
# the original small function literally. Normalize only that function while the
# particle patch runs, then restore the current smooth-drift version afterward.
s = p.read_text(encoding="utf-8")
fn_start = s.find("static void hjReseedTrippy() {")
if fn_start < 0:
    raise SystemExit("saver protocol patch failed: hjReseedTrippy not found")
fn_end = s.find("\n}", fn_start)
if fn_end < 0:
    raise SystemExit("saver protocol patch failed: hjReseedTrippy end not found")
fn_end += 2
current_reseed = s[fn_start:fn_end]
legacy_reseed = '''static void hjReseedTrippy() {
  hjTrippySeed = hjBoardEntropy() ^ 0x54524950UL;
  hjArtStep = 0;
}'''
s = s[:fn_start] + legacy_reseed + s[fn_end:]
p.write_text(s, encoding="utf-8")

particle_patch = Path(__file__).with_name("patch_happyjarz_particle_universe.py")
if not particle_patch.exists():
    raise SystemExit(f"saver protocol patch failed: missing {particle_patch.name}")
subprocess.run([sys.executable, str(particle_patch), str(p)], check=True)

s = p.read_text(encoding="utf-8")
legacy_pos = s.find(legacy_reseed)
if legacy_pos < 0:
    raise SystemExit("saver protocol patch failed: normalized reseed marker disappeared")
s = s[:legacy_pos] + current_reseed + s[legacy_pos + len(legacy_reseed):]

# Insert protocol helpers after the restored reseed function without depending
# on its exact internal implementation.
marker = current_reseed
if marker not in s:
    raise SystemExit("saver protocol patch failed: restored reseed marker not found")

helpers = r'''

static void hjReseedParticles();

static const char *hjSaverModeName() {
  if (hjScreensaverMode == 0) return "SAYINGS";
  if (hjScreensaverMode == 1) return "SPIRAL";
  if (hjScreensaverMode == 2) return "TRIPPY";
  return "PARTICLES";
}

static void hjSaverReseedCurrent() {
  if (hjScreensaverMode == 1) hjReseedSpiral();
  else if (hjScreensaverMode == 2) hjReseedTrippy();
  else if (hjScreensaverMode == 3) hjReseedParticles();
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
  Serial.print("|trippy_speed="); Serial.print(hjTrippySpeed);
  Serial.print("|particle_speed="); Serial.print(hjParticleSpeed);
  Serial.print("|particles="); Serial.print(hjParticleCount);
  Serial.print("|attractors="); Serial.print(hjAttractorCount);
  Serial.print("|links="); Serial.print(hjParticleLinks ? 1 : 0);
  Serial.print("|wrap="); Serial.print(hjParticleWrap ? 1 : 0);
  Serial.print("|repel="); Serial.println(hjParticleRepel ? 1 : 0);
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
    else if(hjScreensaverMode==3 && hjParticleSpeed<8) hjParticleSpeed++;
    ack("SAVER SPEED UP"); hjPrintSaverStatus(); return;
  }
  if(line=="SAVER SPEED DOWN"){
    if(hjScreensaverMode==1 && hjSpiralSpeed>1) hjSpiralSpeed--;
    else if(hjScreensaverMode==2 && hjTrippySpeed>1) hjTrippySpeed--;
    else if(hjScreensaverMode==3 && hjParticleSpeed>1) hjParticleSpeed--;
    ack("SAVER SPEED DOWN"); hjPrintSaverStatus(); return;
  }
  if(line.startsWith("SET SAVER MODE ")){
    String v=line.substring(15); v.trim(); v.toUpperCase();
    if(v=="SAYINGS") hjSaverSetMode(0,true);
    else if(v=="SPIRAL") hjSaverSetMode(1,true);
    else if(v=="TRIPPY") hjSaverSetMode(2,true);
    else if(v=="PARTICLES") hjSaverSetMode(3,true);
    else {err("saver mode must be SAYINGS SPIRAL TRIPPY or PARTICLES");return;}
    ack("SET SAVER MODE"); hjPrintSaverStatus(); return;
  }
'''
s = s.replace(cmd_needle, cmds + cmd_needle, 1)

p.write_text(s, encoding="utf-8")

# Fuel Gauge is deliberately chained last. It extends the already-staged OLED
# menu/protocol and therefore cannot overwrite the proven LED/touch/saver layers.
fuel_patch = Path(__file__).with_name("patch_happyjarz_fuel_gauge.py")
if not fuel_patch.exists():
    raise SystemExit(f"saver protocol patch failed: missing {fuel_patch.name}")
subprocess.run([sys.executable, str(fuel_patch), str(p)], check=True)
