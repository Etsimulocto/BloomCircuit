#!/usr/bin/env python3
"""Add standalone on-device date/time setting to the HAPPY JARZ CLOCK page.

No PC or Wi-Fi is required.

CLOCK page:
  A = enter editor
  B/LEFT = back to main menu

Editor:
  LEFT/RIGHT = select MONTH/DAY/YEAR/HOUR/MINUTE
  UP/DOWN = change selected value
  A = save with settimeofday()
  B = cancel

The ESP32 system clock continues running while powered. Without a battery-backed
RTC, elapsed time while the board is fully powered off cannot be recovered.

Control routing is intercepted at the stable top of serviceInputs(), so this
patch does not depend on the shape/order of downstream menu/detail branches.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_manual_clock.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

state_marker = '''static uint8_t uiScroll = 0;\n'''
if state_marker not in s:
    raise SystemExit("manual clock patch failed: UI state marker not found")

state_block = r'''

// -----------------------------
// Standalone manual clock editor
// -----------------------------
static bool manualClockEditing = false;
static uint8_t manualClockField = 0; // 0 month, 1 day, 2 year, 3 hour, 4 minute
static int manualClockMonth = 1;
static int manualClockDay = 1;
static int manualClockYear = 2026;
static int manualClockHour = 12;
static int manualClockMinute = 0;

static int manualClockDaysInMonth(int year, int month) {
  static const uint8_t days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  if (month == 2) {
    bool leap = (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
    return leap ? 29 : 28;
  }
  if (month < 1 || month > 12) return 31;
  return days[month-1];
}

static void manualClockClampDay() {
  int maxDay = manualClockDaysInMonth(manualClockYear, manualClockMonth);
  if (manualClockDay < 1) manualClockDay = maxDay;
  if (manualClockDay > maxDay) manualClockDay = 1;
}

static void manualClockBeginEdit() {
  struct tm t;
  if (getLocalTime(&t, 10) && t.tm_year + 1900 >= 2020) {
    manualClockMonth = t.tm_mon + 1;
    manualClockDay = t.tm_mday;
    manualClockYear = t.tm_year + 1900;
    manualClockHour = t.tm_hour;
    manualClockMinute = t.tm_min;
  } else {
    manualClockMonth = 1;
    manualClockDay = 1;
    manualClockYear = 2026;
    manualClockHour = 12;
    manualClockMinute = 0;
  }
  manualClockField = 0;
  manualClockEditing = true;
  oledDirty = true;
}

static const char *manualClockFieldName() {
  static const char *names[] = {"MONTH", "DAY", "YEAR", "HOUR", "MINUTE"};
  return names[manualClockField % 5];
}

static void manualClockAdjust(int delta) {
  switch (manualClockField) {
    case 0:
      manualClockMonth += delta;
      if (manualClockMonth < 1) manualClockMonth = 12;
      if (manualClockMonth > 12) manualClockMonth = 1;
      manualClockClampDay();
      break;
    case 1: {
      int maxDay = manualClockDaysInMonth(manualClockYear, manualClockMonth);
      manualClockDay += delta;
      if (manualClockDay < 1) manualClockDay = maxDay;
      if (manualClockDay > maxDay) manualClockDay = 1;
      break;
    }
    case 2:
      manualClockYear += delta;
      if (manualClockYear < 2020) manualClockYear = 2099;
      if (manualClockYear > 2099) manualClockYear = 2020;
      manualClockClampDay();
      break;
    case 3:
      manualClockHour += delta;
      if (manualClockHour < 0) manualClockHour = 23;
      if (manualClockHour > 23) manualClockHour = 0;
      break;
    default:
      manualClockMinute += delta;
      if (manualClockMinute < 0) manualClockMinute = 59;
      if (manualClockMinute > 59) manualClockMinute = 0;
      break;
  }
  oledDirty = true;
}

static bool manualClockSave() {
  struct tm t = {};
  t.tm_year = manualClockYear - 1900;
  t.tm_mon = manualClockMonth - 1;
  t.tm_mday = manualClockDay;
  t.tm_hour = manualClockHour;
  t.tm_min = manualClockMinute;
  t.tm_sec = 0;
  t.tm_isdst = -1;
  time_t epoch = mktime(&t);
  if (epoch < 1700000000) return false;
  struct timeval tv;
  tv.tv_sec = epoch;
  tv.tv_usec = 0;
  if (settimeofday(&tv, nullptr) != 0) return false;
  manualClockEditing = false;
  oledDirty = true;
  Serial.println("HJ|EVENT|clock=MANUAL_SET");
  return true;
}
'''
s = s.replace(state_marker, state_marker + state_block, 1)

old_clock = '''static void oledRenderClock() {
  struct tm t;
  oledCentered(13, "CLOCK");
  if (!clockSynced() || !getLocalTime(&t, 10)) {
    oledCentered(29, "NOT SET");
    oledCentered(45, timezoneName);
    oledCentered(61, "B BACK");
    return;
  }
  char timeBuf[22], dateBuf[22];
  strftime(timeBuf, sizeof(timeBuf), "%I:%M:%S %p", &t);
  strftime(dateBuf, sizeof(dateBuf), "%a %b %d %Y", &t);
  oledCentered(29, String(timeBuf));
  oledCentered(45, String(dateBuf));
  oledCentered(61, WiFi.status()==WL_CONNECTED ? "SOURCE WIFI" : "SOURCE USB");
}
'''
new_clock = r'''static void oledRenderClock() {
  if (manualClockEditing) {
    char dateBuf[18], timeBuf[18];
    snprintf(dateBuf, sizeof(dateBuf), "%02d/%02d/%04d", manualClockMonth, manualClockDay, manualClockYear);
    int h12 = manualClockHour % 12; if (h12 == 0) h12 = 12;
    snprintf(timeBuf, sizeof(timeBuf), "%02d:%02d %s", h12, manualClockMinute, manualClockHour >= 12 ? "PM" : "AM");
    oledCentered(13, "SET CLOCK");
    oledCentered(29, String(dateBuf));
    oledCentered(45, String(timeBuf));
    oledCentered(61, String("< ") + manualClockFieldName() + " >");
    return;
  }

  struct tm t;
  oledCentered(13, "CLOCK");
  if (!getLocalTime(&t, 10) || t.tm_year + 1900 < 2020) {
    oledCentered(29, "TIME NOT SET");
    oledCentered(45, "A SET TIME/DATE");
    oledCentered(61, "B BACK");
    return;
  }
  char timeBuf[22], dateBuf[22];
  strftime(timeBuf, sizeof(timeBuf), "%I:%M:%S %p", &t);
  strftime(dateBuf, sizeof(dateBuf), "%a %b %d %Y", &t);
  oledCentered(29, String(timeBuf));
  oledCentered(45, String(dateBuf));
  oledCentered(61, "A SET   B BACK");
}
'''
if old_clock not in s:
    raise SystemExit("manual clock patch failed: CLOCK renderer not found")
s = s.replace(old_clock, new_clock, 1)

service_marker = '''static void serviceInputs() {
  bool q[INPUT_COUNT];
  for (uint8_t i=0;i<INPUT_COUNT;++i) q[i]=updateInputState(i);
'''
if service_marker not in s:
    raise SystemExit("manual clock patch failed: serviceInputs scan marker not found")

clock_controls = r'''

  // CLOCK owns touch input before downstream menu/detail routing.
  if (inputMode == "JAR" && !hjScreensaverActive && uiScreen == UI_CLOCK) {
    if (manualClockEditing) {
      if (q[IN_LEFT] && !latched[IN_LEFT]) { manualClockField=(manualClockField+4)%5; oledDirty=true; }
      if (q[IN_RIGHT] && !latched[IN_RIGHT]) { manualClockField=(manualClockField+1)%5; oledDirty=true; }
      if (q[IN_UP] && !latched[IN_UP]) manualClockAdjust(+1);
      if (q[IN_DOWN] && !latched[IN_DOWN]) manualClockAdjust(-1);
      if (q[IN_A] && !latched[IN_A]) {
        if (!manualClockSave()) Serial.println("HJ|ERR|message=manual clock save failed");
      }
      if (q[IN_B] && !latched[IN_B]) { manualClockEditing=false; oledDirty=true; }
    } else {
      if (q[IN_A] && !latched[IN_A]) manualClockBeginEdit();
      if ((q[IN_B] && !latched[IN_B]) || (q[IN_LEFT] && !latched[IN_LEFT])) uiOpenMainMenu();
    }
    for (uint8_t i=0;i<INPUT_COUNT;++i) latched[i]=q[i];
    return;
  }
'''
s = s.replace(service_marker, service_marker + clock_controls, 1)

p.write_text(s, encoding="utf-8")
print("Applied standalone OLED time/date editor.")
