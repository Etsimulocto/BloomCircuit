#!/usr/bin/env python3
"""Add desktop serial controls/status for the current HAPPY JARZ screensaver engine.

Runs after patch_happyjarz_saver_controls.py. Before adding protocol commands it
also applies the particle-universe layer so the standard flasher needs no new
manual step.

The SPIRAL/TRIPPY generators intentionally evolve over time, so this wrapper
must not depend on an exact historical hjReseedTrippy() function body. The older
particle patch still uses that legacy marker; we temporarily normalize only that
function while the particle patch runs, then restore the current entropy-aware
implementation before compile.

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
import re
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_saver_protocol.py <staged .ino>")

p = Path(sys.argv[1])
particle_patch = Path(__file__).with_name("patch_happyjarz_particle_universe.py")
if not particle_patch.exists():
    raise SystemExit(f"saver protocol patch failed: missing {particle_patch.name}")

# Capture the CURRENT reseed function structurally. Do not make the patch chain
# depend on whatever state initialization happens to live inside it this week.
s = p.read_text(encoding="utf-8")
trippy_re = re.compile(r'static void hjReseedTrippy\(\) \{.*?\n\}', re.S)
m = trippy_re.search(s)
if not m:
    raise SystemExit("saver protocol patch failed: hjReseedTrippy function not found")
current_trippy = m.group(0)

legacy_trippy = '''static void hjReseedTrippy() {
  hjTrippySeed = hjBoardEntropy() ^ 0x54524950UL;
  hjArtStep = 0;
}'''

# The particle layer predates the evolving-art state and still expects the old
# literal block. Normalize just long enough for that patch to insert its code.
s = s[:m.start()] + legacy_trippy + s[m.end():]
p.write_text(s, encoding="utf-8")

try:
    subprocess.run([sys.executable, str(particle_patch), str(p)], check=True)
except Exception:
    # Restore the staged source before surfacing the failure, which makes failed
    # flash attempts easier to inspect and avoids leaving a fake legacy function.
    failed = p.read_text(encoding="utf-8")
    if legacy_trippy in failed:
        failed = failed.replace(legacy_trippy, current_trippy, 1)
        p.write_text(failed, encoding="utf-8")
    raise

# Restore the real current reseed function after the particle patch has used its
# compatibility marker. The entropy/random-walk state from saver-controls stays.
s = p.read_text(encoding="utf-8")
if legacy_trippy not in s:
    raise SystemExit("saver protocol patch failed: compatibility reseed marker disappeared")
s = s.replace(legacy_trippy, current_trippy, 1)

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

if current_trippy not in s:
    raise SystemExit("saver protocol patch failed: restored reseed function not found")
s = s.replace(current_trippy, current_trippy + helpers, 1)

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
