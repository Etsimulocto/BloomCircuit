#!/usr/bin/env python3
"""Add HAPPY JARZ one-hour software sleep with touch/alarm wake.

This is deliberately NOT ESP32 deep sleep:
- clock, alarm, USB, Wi-Fi and capacitive touch continue running
- OLED enters controller power-save
- APA106 output goes black and pattern advancement freezes
- any physical touch edge wakes and is consumed as WAKE only
- alarm wake uses the same wake path before the alarm pattern fires
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_sleep_mode.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

def fail(msg):
    raise SystemExit("sleep-mode patch failed: " + msg)

if "HAPPYJARZ_SLEEP_MODE_V1" in s:
    print("Sleep mode already present; leaving staged sketch unchanged.")
    raise SystemExit(0)

# Early state/prototype: writeFrame(), servicePattern() and fireAlarmEvent()
# occur before the final OLED/input layer in the generated sketch.
marker = 'static String patternName = "SOLID";\n'
if marker not in s:
    fail("patternName marker not found")

early = r'''
// HAPPYJARZ_SLEEP_MODE_V1
static constexpr unsigned long HJ_SLEEP_IDLE_MS = 3600000UL; // 1 hour
static bool hjSleepActive = false;
static unsigned long hjSleepLastActivityMs = 0;
static void hjWakeFromSleep(const char *reason);
'''
s = s.replace(marker, marker + early, 1)

# Stop all APA106 traffic while sleeping. hjEnterSleep() sends the final black
# frame before setting hjSleepActive=true.
write_sig = 'static void writeFrame(const Rgb frame[LED_COUNT], uint8_t brightness) {\n'
if write_sig not in s:
    fail("writeFrame marker not found")
s = s.replace(write_sig,
              write_sig + '  if (hjSleepActive) return;\n',
              1)

# Freeze the pattern step/phase too, so wake resumes cleanly rather than jumping.
pattern_sig = 'static void servicePattern() {\n'
if pattern_sig not in s:
    fail("servicePattern marker not found")
s = s.replace(pattern_sig,
              pattern_sig + '  if (hjSleepActive) return;\n',
              1)

# Alarm must wake visible output before applying its normal alarm pattern.
alarm_sig = 'static void fireAlarmEvent() {\n'
if alarm_sig not in s:
    fail("fireAlarmEvent marker not found")
s = s.replace(alarm_sig,
              alarm_sig + '  hjWakeFromSleep("ALARM");\n',
              1)

# Define sleep/wake after OLED/host mirror symbols exist, immediately before
# serviceInputs(), which is stable across the final UI/arcade patch chain.
input_sig = '''static void serviceInputs() {
  bool q[INPUT_COUNT];
  for (uint8_t i=0;i<INPUT_COUNT;++i) q[i]=updateInputState(i);
'''
if input_sig not in s:
    fail("final serviceInputs marker not found")

sleep_block = r'''
static void hjEnterSleep() {
  if (hjSleepActive) return;

  // Blank all four lamps once, then freeze LED/pattern output.
  Rgb blank[LED_COUNT] = {};
  writeFrame(blank, 0);

  if (oledReady && oled) {
    oled->setPowerSave(1);
  }

  hjSleepActive = true;
  if (Serial) Serial.println("HJ|SLEEP|state=ASLEEP|reason=IDLE_1H");
}

static void hjWakeFromSleep(const char *reason) {
  hjSleepLastActivityMs = millis();
  if (!hjSleepActive) return;

  hjSleepActive = false;

  if (oledReady && oled) {
    oled->setPowerSave(0);
    oledDirty = true;
  }

  resetPatternEngine();
  if (patternName == "SOLID") showLeds();

  if (Serial) {
    Serial.print("HJ|SLEEP|state=AWAKE|reason=");
    Serial.println(reason ? reason : "UNKNOWN");
  }
}

static void hjServiceSleep() {
  if (hjSleepActive) return;
  unsigned long now = millis();
  if (now - hjSleepLastActivityMs >= HJ_SLEEP_IDLE_MS) {
    hjEnterSleep();
  }
}

'''
s=s.replace(input_sig, sleep_block + input_sig, 1)

# Physical touch activity is evaluated before all later UI/game/saver routers.
# When asleep, consume the first touch only as WAKE so it cannot also change a
# pattern, menu item or game state.
touch_insert = r'''
  bool hjAnyPhysicalPress = false;
  for (uint8_t i=0; i<INPUT_COUNT; ++i) {
    if (q[i] && !latched[i]) {
      hjAnyPhysicalPress = true;
      break;
    }
  }
  if (hjAnyPhysicalPress) {
    hjSleepLastActivityMs = millis();
    if (hjSleepActive) {
      hjWakeFromSleep("TOUCH");
      for (uint8_t i=0; i<INPUT_COUNT; ++i) latched[i] = q[i];
      return;
    }
  }
'''
s=s.replace(input_sig, input_sig + touch_insert, 1)

# Never present OLED frames while controller power-save is active. This also
# covers arcade frames because arcade ultimately uses hjOledPresent().
present_sig = 'static void hjOledPresent() {\n'
if present_sig not in s:
    fail("hjOledPresent marker not found")
s=s.replace(present_sig,
            present_sig + '  if (hjSleepActive) return;\n',
            1)

# Main OLED service can also stop doing render work during sleep.
oled_sig = 'static void serviceOled() {\n'
if oled_sig not in s:
    fail("serviceOled marker not found")
s=s.replace(oled_sig,
            oled_sig + '  if (hjSleepActive) return;\n',
            1)

# Freeze arcade simulation while sleeping, preserving the current game state.
arcade_call = '  if (hjArcadeActive()) hjArcadeService(millis());\n'
if arcade_call in s:
    s=s.replace(arcade_call,
                '  if (hjArcadeActive() && !hjSleepActive) hjArcadeService(millis());\n',
                1)

# Initialize idle epoch at setup and service sleep after input handling so a
# touch arriving exactly at the one-hour boundary wins over sleep entry.
setup_sig = 'void setup(){\n'
if setup_sig not in s:
    fail("setup marker not found")
s=s.replace(setup_sig, setup_sig + '  hjSleepLastActivityMs = millis();\n', 1)

loop_input = '  serviceInputs();\n'
if loop_input not in s:
    fail("loop serviceInputs call not found")
s=s.replace(loop_input,
            loop_input + '  hjServiceSleep();\n',
            1)

p.write_text(s, encoding="utf-8")
print("Applied HAPPY JARZ 1-hour sleep: OLED/lights off, any-touch wake, alarm wake.")
