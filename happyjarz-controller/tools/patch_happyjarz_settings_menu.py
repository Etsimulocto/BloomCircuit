#!/usr/bin/env python3
"""Add standalone ALARM and TIMER controls to OLED SETTINGS.

SETTINGS page:
  UP/DOWN = choose ALARM / TIMER
  A = open selected editor
  B/LEFT = back to main menu

Editors:
  LEFT/RIGHT = select field
  UP/DOWN = adjust selected value
  A = save and return to SETTINGS
  B = cancel and return to SETTINGS

Existing firmware state remains authoritative:
- alarmEnabled / alarmHour / alarmMinute
- timerEnabled / timerMinutes / timerStartedMs
- persistSettings()
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_settings_menu.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

state_marker = '''static uint8_t uiScroll = 0;\n'''
if state_marker not in s:
    raise SystemExit("settings patch failed: UI state marker not found")

state_block = r'''

// -----------------------------
// Standalone SETTINGS editors
// -----------------------------
static uint8_t settingsCursor = 0;      // 0 alarm, 1 timer
static uint8_t settingsEditor = 0;      // 0 menu, 1 alarm, 2 timer
static uint8_t settingsField = 0;

static bool editAlarmEnabled = false;
static uint8_t editAlarmHour = 7;
static uint8_t editAlarmMinute = 0;
static bool editTimerEnabled = false;
static uint16_t editTimerMinutes = 10;

static void settingsOpenEditor(uint8_t which) {
  settingsEditor = which;
  settingsField = 0;
  if (which == 1) {
    editAlarmEnabled = alarmEnabled;
    editAlarmHour = alarmHour;
    editAlarmMinute = alarmMinute;
  } else if (which == 2) {
    editTimerEnabled = timerEnabled;
    editTimerMinutes = timerMinutes;
    if (editTimerMinutes < 1) editTimerMinutes = 1;
  }
  oledDirty = true;
}

static void settingsCancelEditor() {
  settingsEditor = 0;
  settingsField = 0;
  oledDirty = true;
}

static void settingsAdjust(int delta) {
  if (settingsEditor == 1) {
    if (settingsField == 0) {
      editAlarmEnabled = !editAlarmEnabled;
    } else if (settingsField == 1) {
      int v = (int)editAlarmHour + delta;
      if (v < 0) v = 23;
      if (v > 23) v = 0;
      editAlarmHour = (uint8_t)v;
    } else {
      int v = (int)editAlarmMinute + delta;
      if (v < 0) v = 59;
      if (v > 59) v = 0;
      editAlarmMinute = (uint8_t)v;
    }
  } else if (settingsEditor == 2) {
    if (settingsField == 0) {
      editTimerEnabled = !editTimerEnabled;
    } else {
      int v = (int)editTimerMinutes + delta;
      if (v < 1) v = 240;
      if (v > 240) v = 1;
      editTimerMinutes = (uint16_t)v;
    }
  }
  oledDirty = true;
}

static void settingsSaveEditor() {
  if (settingsEditor == 1) {
    alarmEnabled = editAlarmEnabled;
    alarmHour = editAlarmHour;
    alarmMinute = editAlarmMinute;
  } else if (settingsEditor == 2) {
    timerEnabled = editTimerEnabled;
    timerMinutes = editTimerMinutes;
    if (timerEnabled) timerStartedMs = millis();
  }
  persistSettings();
  settingsEditor = 0;
  settingsField = 0;
  oledDirty = true;
}
'''
s = s.replace(state_marker, state_marker + state_block, 1)

old_settings = '''static void oledRenderSettings() {
  oledCentered(13, "SETTINGS");
  oledCentered(29, "DISPLAY " + String(displayBrightness) + "%");
  oledCentered(45, alarmEnabled ? "ALARM ON" : "ALARM OFF");
  oledCentered(61, timerText());
}
'''
new_settings = r'''static void oledRenderSettings() {
  if (settingsEditor == 0) {
    static const char *items[] = {"ALARM", "TIMER"};
    oledCentered(13, "SETTINGS");
    for (uint8_t row=0; row<2; ++row) {
      String text = String(row == settingsCursor ? "> " : "  ") + items[row];
      oledCentered(33 + row*20, text);
    }
    oledCentered(61, "B BACK");
    return;
  }

  if (settingsEditor == 1) {
    char timeBuf[16];
    int h12 = editAlarmHour % 12; if (h12 == 0) h12 = 12;
    snprintf(timeBuf, sizeof(timeBuf), "%02d:%02d %s", h12, editAlarmMinute, editAlarmHour >= 12 ? "PM" : "AM");
    oledCentered(13, "ALARM");
    oledCentered(29, editAlarmEnabled ? "ON" : "OFF");
    oledCentered(45, String(timeBuf));
    oledCentered(61, settingsField==0 ? "< ON/OFF >" : (settingsField==1 ? "< HOUR >" : "< MINUTE >"));
    return;
  }

  oledCentered(13, "TIMER");
  oledCentered(29, editTimerEnabled ? "RUN ON SAVE" : "OFF");
  oledCentered(45, String(editTimerMinutes) + " MINUTES");
  oledCentered(61, settingsField==0 ? "< ON/OFF >" : "< MINUTES >");
}
'''
if old_settings not in s:
    raise SystemExit("settings patch failed: SETTINGS renderer not found")
s = s.replace(old_settings, new_settings, 1)

generic_branch = '''    } else {\n      // DETAIL/STATUS MODE: still no light commands. B/LEFT return to menu.\n'''
if generic_branch not in s:
    raise SystemExit("settings patch failed: generic detail branch not found")

settings_controls = r'''    } else if (uiScreen == UI_SETTINGS) {
      if (settingsEditor == 0) {
        if (q[IN_UP] && !latched[IN_UP]) { settingsCursor=(settingsCursor+1)%2; oledDirty=true; }
        if (q[IN_DOWN] && !latched[IN_DOWN]) { settingsCursor=(settingsCursor+1)%2; oledDirty=true; }
        if (q[IN_A] && !latched[IN_A]) settingsOpenEditor(settingsCursor+1);
        if ((q[IN_B] && !latched[IN_B]) || (q[IN_LEFT] && !latched[IN_LEFT])) uiOpenMainMenu();
      } else {
        uint8_t fieldCount = settingsEditor==1 ? 3 : 2;
        if (q[IN_LEFT] && !latched[IN_LEFT]) { settingsField=(settingsField+fieldCount-1)%fieldCount; oledDirty=true; }
        if (q[IN_RIGHT] && !latched[IN_RIGHT]) { settingsField=(settingsField+1)%fieldCount; oledDirty=true; }
        if (q[IN_UP] && !latched[IN_UP]) settingsAdjust(+1);
        if (q[IN_DOWN] && !latched[IN_DOWN]) settingsAdjust(-1);
        if (q[IN_A] && !latched[IN_A]) settingsSaveEditor();
        if (q[IN_B] && !latched[IN_B]) settingsCancelEditor();
      }
'''
s = s.replace(generic_branch, settings_controls + generic_branch, 1)

p.write_text(s, encoding="utf-8")
print("Applied standalone SETTINGS: alarm + timer.")
