#!/usr/bin/env python3
"""Remove visible parameter jumps from SPIRAL/TRIPPY entropy drift.

Runs after patch_happyjarz_saver_controls.py. The procedural engine still chooses
new entropy-driven destinations periodically, but the live values ease toward
those targets every rendered frame instead of stepping instantly.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_saver_smooth_drift.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

state_marker = '''static float hjTrippyPhaseDrift = 0.0f;\n'''
if state_marker not in s:
    raise SystemExit("smooth drift patch failed: drift state marker not found")

target_state = r'''static float hjSpiralCxTarget = 0.0f, hjSpiralCyTarget = 0.0f;
static float hjSpiralAngleTarget = 0.0f, hjSpiralSquashTarget = 0.0f;
static float hjSpiralWobbleTarget = 0.0f;
static float hjTrippyFreqTarget1 = 0.0f, hjTrippyFreqTarget2 = 0.0f;
static float hjTrippyAmpTarget1 = 0.0f, hjTrippyAmpTarget2 = 0.0f;
static float hjTrippyPhaseTarget = 0.0f;
'''
s = s.replace(state_marker, state_marker + target_state, 1)

start = s.find('static void hjWanderSpiral() {')
end = s.find('\nstatic void hjReseedSpiral() {', start)
if start < 0 or end < 0:
    raise SystemExit("smooth drift patch failed: wander functions not found")

smooth_functions = r'''static float hjEaseF(float current, float target, float amount) {
  return current + (target - current) * amount;
}

static float hjWrappedPhaseDelta(float current, float target) {
  float d = target - current;
  while (d > 3.14159f) d -= 6.28318f;
  while (d < -3.14159f) d += 6.28318f;
  return d;
}

static void hjWanderSpiral() {
  // A new destination is chosen occasionally, but the visible values move
  // toward it every frame. This removes the old ~3 second visual snap.
  if ((hjArtStep % 53U) == 0U) {
    hjSpiralWanderState ^= hjBoardEntropy();
    hjSpiralCxTarget     = hjClampF(hjSpiralCxTarget     + hjSeedFloat(hjSpiralWanderState,-3.5f, 3.5f), -12.0f, 12.0f);
    hjSpiralCyTarget     = hjClampF(hjSpiralCyTarget     + hjSeedFloat(hjSpiralWanderState,-2.5f, 2.5f),  -8.0f,  8.0f);
    hjSpiralAngleTarget  = hjClampF(hjSpiralAngleTarget  + hjSeedFloat(hjSpiralWanderState,-0.045f,0.045f),-0.16f, 0.16f);
    hjSpiralSquashTarget = hjClampF(hjSpiralSquashTarget + hjSeedFloat(hjSpiralWanderState,-0.070f,0.070f),-0.24f, 0.24f);
    hjSpiralWobbleTarget = hjClampF(hjSpiralWobbleTarget + hjSeedFloat(hjSpiralWanderState,-0.035f,0.035f),-0.11f, 0.11f);
  }

  hjSpiralCxDrift     = hjEaseF(hjSpiralCxDrift,     hjSpiralCxTarget,     0.018f);
  hjSpiralCyDrift     = hjEaseF(hjSpiralCyDrift,     hjSpiralCyTarget,     0.018f);
  hjSpiralAngleDrift  = hjEaseF(hjSpiralAngleDrift,  hjSpiralAngleTarget,  0.010f);
  hjSpiralSquashDrift = hjEaseF(hjSpiralSquashDrift, hjSpiralSquashTarget, 0.012f);
  hjSpiralWobbleDrift = hjEaseF(hjSpiralWobbleDrift, hjSpiralWobbleTarget, 0.012f);
}

static void hjWanderTrippy() {
  if ((hjArtStep % 59U) == 0U) {
    hjTrippyWanderState ^= hjBoardEntropy();
    hjTrippyFreqTarget1 = hjClampF(hjTrippyFreqTarget1 + hjSeedFloat(hjTrippyWanderState,-0.010f,0.010f),-0.030f,0.030f);
    hjTrippyFreqTarget2 = hjClampF(hjTrippyFreqTarget2 + hjSeedFloat(hjTrippyWanderState,-0.009f,0.009f),-0.025f,0.025f);
    hjTrippyAmpTarget1  = hjClampF(hjTrippyAmpTarget1  + hjSeedFloat(hjTrippyWanderState,-3.0f,3.0f),-9.0f,9.0f);
    hjTrippyAmpTarget2  = hjClampF(hjTrippyAmpTarget2  + hjSeedFloat(hjTrippyWanderState,-2.4f,2.4f),-7.0f,7.0f);
    hjTrippyPhaseTarget += hjSeedFloat(hjTrippyWanderState,-0.60f,0.60f);
    while (hjTrippyPhaseTarget > 6.28318f) hjTrippyPhaseTarget -= 6.28318f;
    while (hjTrippyPhaseTarget < -6.28318f) hjTrippyPhaseTarget += 6.28318f;
  }

  hjTrippyFreqDrift1 = hjEaseF(hjTrippyFreqDrift1, hjTrippyFreqTarget1, 0.010f);
  hjTrippyFreqDrift2 = hjEaseF(hjTrippyFreqDrift2, hjTrippyFreqTarget2, 0.010f);
  hjTrippyAmpDrift1  = hjEaseF(hjTrippyAmpDrift1,  hjTrippyAmpTarget1,  0.015f);
  hjTrippyAmpDrift2  = hjEaseF(hjTrippyAmpDrift2,  hjTrippyAmpTarget2,  0.015f);
  hjTrippyPhaseDrift += hjWrappedPhaseDelta(hjTrippyPhaseDrift, hjTrippyPhaseTarget) * 0.012f;
}
'''

s = s[:start] + smooth_functions + s[end:]

spiral_reset = '''  hjSpiralCxDrift=hjSpiralCyDrift=0.0f;\n  hjSpiralAngleDrift=hjSpiralSquashDrift=hjSpiralWobbleDrift=0.0f;\n'''
spiral_reset_new = spiral_reset + '''  hjSpiralCxTarget=hjSpiralCyTarget=0.0f;\n  hjSpiralAngleTarget=hjSpiralSquashTarget=hjSpiralWobbleTarget=0.0f;\n'''
if spiral_reset not in s:
    raise SystemExit("smooth drift patch failed: spiral reset marker not found")
s = s.replace(spiral_reset, spiral_reset_new, 1)

trippy_reset = '''  hjTrippyFreqDrift1=hjTrippyFreqDrift2=0.0f;\n  hjTrippyAmpDrift1=hjTrippyAmpDrift2=0.0f;\n  hjTrippyPhaseDrift=0.0f;\n'''
trippy_reset_new = trippy_reset + '''  hjTrippyFreqTarget1=hjTrippyFreqTarget2=0.0f;\n  hjTrippyAmpTarget1=hjTrippyAmpTarget2=0.0f;\n  hjTrippyPhaseTarget=0.0f;\n'''
if trippy_reset not in s:
    raise SystemExit("smooth drift patch failed: trippy reset marker not found")
s = s.replace(trippy_reset, trippy_reset_new, 1)

p.write_text(s, encoding="utf-8")
