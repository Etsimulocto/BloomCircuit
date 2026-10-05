#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_bloom_clock_battery_fallback_v1.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_CLOCK_BATTERY_FALLBACK_V1"

if marker in s:
    print("Bloom clock battery fallback already present")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".pre_clock_battery_fallback_v1")
if not backup.exists():
    backup.write_text(s)

anchor = '''static void bloomSystemSetHostTime(int64_t epochUtc, int32_t offsetMinutes) {
'''
if anchor not in s:
    raise SystemExit("bloomSystemSetHostTime anchor not found")

helpers = r'''// BLOOM_CLOCK_BATTERY_FALLBACK_V1
// USB host time remains authoritative.  These Preferences values are only a
// battery/offline fallback so BLOOM SYSTEM does not return to a blank clock
// whenever the ESP32 reboots away from the Pi.
static Preferences bloomClockPrefs;
static uint32_t bloomClockLastCheckpointMs = 0;
static const uint32_t BLOOM_CLOCK_CHECKPOINT_MS = 3600000UL; // once per hour

static void bloomClockSaveFallback() {
  if (!bloomSystemHostClockValid) return;
  int64_t nowUtc = bloomSystemHostEpochUtc +
                   (int64_t)((millis() - bloomSystemHostClockSetMs) / 1000UL);
  if (nowUtc < 1700000000LL) return;

  if (!bloomClockPrefs.begin("bloomclock", false)) return;
  bloomClockPrefs.putULong64("epoch", (uint64_t)nowUtc);
  bloomClockPrefs.putInt("offset", bloomSystemHostOffsetMinutes);
  bloomClockPrefs.end();
  bloomClockLastCheckpointMs = millis();
}

static bool bloomClockLoadFallback() {
  if (!bloomClockPrefs.begin("bloomclock", true)) return false;
  uint64_t savedEpoch = bloomClockPrefs.getULong64("epoch", 0ULL);
  int32_t savedOffset = bloomClockPrefs.getInt("offset", 0);
  bloomClockPrefs.end();

  if (savedEpoch < 1700000000ULL) return false;
  bloomSystemHostEpochUtc = (int64_t)savedEpoch;
  bloomSystemHostOffsetMinutes = constrain(savedOffset, -840, 840);
  bloomSystemHostClockSetMs = millis();
  bloomSystemHostClockValid = true;
  bloomClockLastCheckpointMs = millis();
  Serial.printf("BP|CLOCK|source=FLASH|epoch=%llu|offset_min=%ld\n",
                (unsigned long long)savedEpoch,
                (long)bloomSystemHostOffsetMinutes);
  return true;
}

'''
s = s.replace(anchor, helpers + anchor, 1)

old_set_tail = '''  bloomSystemHostClockSetMs = millis();
  bloomSystemHostClockValid = true;

  uint32_t today = bloomSystemTodayKey();
'''
new_set_tail = '''  bloomSystemHostClockSetMs = millis();
  bloomSystemHostClockValid = true;
  bloomClockSaveFallback();

  uint32_t today = bloomSystemTodayKey();
'''
if old_set_tail not in s:
    raise SystemExit("host-time assignment anchor not found")
s = s.replace(old_set_tail, new_set_tail, 1)

old_begin = '''static void beginBloomSystemClock() {
  // Host app will supply time over the already-open USB serial connection.
  bloomSystemHostClockValid = false;
}
'''
new_begin = '''static void beginBloomSystemClock() {
  // Restore the last known clock immediately for battery/offline boot.
  // A connected Pi will replace this with exact USB host time shortly after.
  bloomSystemHostClockValid = false;
  if (!bloomClockLoadFallback()) {
    Serial.println("BP|CLOCK|source=NONE|waiting_for_usb=1");
  }
}
'''
if old_begin not in s:
    raise SystemExit("beginBloomSystemClock body anchor not found")
s = s.replace(old_begin, new_begin, 1)

service_anchor = '''static void serviceBloomSystemClock() {
  if (bloomSystemHostClockValid) {
'''
service_new = '''static void serviceBloomSystemClock() {
  if (bloomSystemHostClockValid) {
    // Periodically checkpoint the advancing clock so a later battery boot
    // restores a recent value instead of only the original USB sync instant.
    if (millis() - bloomClockLastCheckpointMs >= BLOOM_CLOCK_CHECKPOINT_MS) {
      bloomClockSaveFallback();
    }
'''
if service_anchor not in s:
    raise SystemExit("serviceBloomSystemClock anchor not found")
s = s.replace(service_anchor, service_new, 1)

p.write_text(s)
print("PATCHED BLOOM CLOCK BATTERY FALLBACK V1")
print("  USB host time saved to ESP32 Preferences")
print("  last saved clock restored on battery/offline boot")
print("  running clock checkpointed once per hour")
print("  USB host time remains authoritative when connected")
print(f"patched: {p}")
