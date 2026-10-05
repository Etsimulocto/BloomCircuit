#!/usr/bin/env python3
"""Add a shared BLOOM SYSTEM startup launcher with Wi-Fi/NTP clock.

Flow:
  existing BloomPetz splash -> BLOOM SYSTEM launcher
  launcher shows local time/date and game choices
  UP/DOWN selects game
  A on BLOOMPETZ -> existing slot picker
  A on DND -> placeholder screen for future game
  B on placeholder -> launcher

Clock:
- reuses HAPPY JARZ saved NVS keys from namespace "happyjarz"
- timezone defaults to America/Chicago
- uses configTzTime() with the proven HAPPY JARZ POSIX timezone mapping
- when clock is synced, writes YYYYMMDD into existing manualDay so BloomPetz's
  existing daily-reset path gets a real local calendar date
- when offline/unsynced, existing manual SET DATE fallback remains available

This patch intentionally does not alter pet saves, stats, LEDs, touch timing, or OLED renderer.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_SYSTEM_LAUNCHER_CLOCK_V1"


def brace_block(text: str, start: int):
    op = text.find('{', start)
    if op < 0:
        raise SystemExit("opening brace not found")
    depth = 0
    in_string = False
    esc = False
    for i in range(op, len(text)):
        ch = text[i]
        if in_string:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit("unbalanced brace block")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_system_launcher_clock.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()
    if MARKER in s:
        print("BLOOM SYSTEM launcher clock already applied.")
        return

    required = [
        "BLOOMPETZ_STARTUP_SPLASH_SLOT_PICKER_V1",
        "enum UiMode",
        "static void serviceStartupUi()",
        "static void drawStartupSlotPicker()",
        "static void handleInput(Input in)",
        "static uint32_t manualDay",
        "Preferences",
        "void setup()",
        "void loop()",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required live anchors missing: " + ", ".join(missing))

    # Preserve the line-1 LED header workaround. Add network/time includes immediately
    # after the initial include region without moving the existing first line.
    additions = []
    if "#include <WiFi.h>" not in s:
        additions.append("#include <WiFi.h>")
    if "#include <time.h>" not in s:
        additions.append("#include <time.h>")
    if additions:
        lines = s.splitlines(True)
        insert_idx = 0
        while insert_idx < len(lines) and (lines[insert_idx].lstrip().startswith("#include") or lines[insert_idx].strip() == ""):
            insert_idx += 1
        lines[insert_idx:insert_idx] = [x + "\n" for x in additions]
        s = "".join(lines)

    # Add launcher modes to existing enum, preserving all current modes.
    em = re.search(r"enum\s+UiMode\s*:\s*uint8_t\s*\{([^}]*)\};", s, re.S)
    if not em:
        raise SystemExit("UiMode enum not found")
    body = em.group(1).strip()
    extras = []
    if "SYSTEM_MENU" not in body:
        extras.append("SYSTEM_MENU")
    if "DND_PLACEHOLDER" not in body:
        extras.append("DND_PLACEHOLDER")
    if extras:
        body = body.rstrip()
        if not body.endswith(','):
            body += ','
        body += " " + ", ".join(extras)
        s = s[:em.start(1)] + " " + body + " " + s[em.end(1):]

    # Insert shared clock + launcher helpers immediately before serviceStartupUi().
    anchor = "static void serviceStartupUi() {"
    pos = s.find(anchor)
    if pos < 0:
        raise SystemExit("serviceStartupUi() anchor not found")

    block = r'''// BLOOMPETZ_SYSTEM_LAUNCHER_CLOCK_V1
static uint8_t bloomSystemGameIndex = 0;
static String bloomSystemWifiSsid;
static String bloomSystemWifiPassword;
static String bloomSystemTimezone = "America/Chicago";
static bool bloomSystemTimeConfigured = false;
static bool bloomSystemClockWasSynced = false;
static uint32_t bloomSystemLastDateKey = 0;
static uint32_t bloomSystemLastUiSecond = 0;

static const char *bloomSystemTzPosixFor(const String &name) {
  if (name == "America/New_York") return "EST5EDT,M3.2.0/2,M11.1.0/2";
  if (name == "America/Chicago") return "CST6CDT,M3.2.0/2,M11.1.0/2";
  if (name == "America/Denver") return "MST7MDT,M3.2.0/2,M11.1.0/2";
  if (name == "America/Los_Angeles") return "PST8PDT,M3.2.0/2,M11.1.0/2";
  if (name == "UTC" || name == "Etc/UTC") return "UTC0";
  return "CST6CDT,M3.2.0/2,M11.1.0/2";
}

static bool bloomSystemClockSynced() {
  time_t now = time(nullptr);
  return now > 1700000000;
}

static uint32_t bloomSystemTodayKey() {
  if (!bloomSystemClockSynced()) return 0;
  time_t now = time(nullptr);
  struct tm t;
  localtime_r(&now, &t);
  return (uint32_t)(t.tm_year + 1900) * 10000UL +
         (uint32_t)(t.tm_mon + 1) * 100UL +
         (uint32_t)t.tm_mday;
}

static String bloomSystemClockLine() {
  if (!bloomSystemClockSynced()) {
    if (!bloomSystemWifiSsid.length()) return "--:-- --/-- NOWIFI";
    if (WiFi.status() != WL_CONNECTED) return "--:-- --/-- WIFI";
    return "--:-- --/-- SYNC";
  }
  time_t now = time(nullptr);
  struct tm t;
  localtime_r(&now, &t);
  char out[17];
  int hour = t.tm_hour % 12;
  if (hour == 0) hour = 12;
  snprintf(out, sizeof(out), "%2d:%02d %02d/%02d %c", hour, t.tm_min,
           t.tm_mon + 1, t.tm_mday, t.tm_hour >= 12 ? 'P' : 'A');
  return String(out);
}

static void drawBloomSystemMenu() {
  String pet = String(bloomSystemGameIndex == 0 ? ">" : " ") + "BLOOMPETZ";
  String dnd = String(bloomSystemGameIndex == 1 ? ">" : " ") + "DND [SOON]";
  renderDisplay("BLOOM SYSTEM", bloomSystemClockLine(), pet, dnd);
}

static void drawDndPlaceholder() {
  renderDisplay("DND", "COMING NEXT...", "ASCII DUNGEONS", "B BACK");
}

static void beginBloomSystemClock() {
  Preferences sysPrefs;
  sysPrefs.begin("happyjarz", true);
  bloomSystemWifiSsid = sysPrefs.getString("wifi_ssid", "");
  bloomSystemWifiPassword = sysPrefs.getString("wifi_pass", "");
  bloomSystemTimezone = sysPrefs.getString("timezone", "America/Chicago");
  sysPrefs.end();

  if (bloomSystemWifiSsid.length()) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(bloomSystemWifiSsid.c_str(), bloomSystemWifiPassword.c_str());
  }
}

static void serviceBloomSystemClock() {
  if (!bloomSystemTimeConfigured && WiFi.status() == WL_CONNECTED) {
    configTzTime(bloomSystemTzPosixFor(bloomSystemTimezone),
                 "pool.ntp.org", "time.nist.gov", "time.google.com");
    bloomSystemTimeConfigured = true;
  }

  bool synced = bloomSystemClockSynced();
  if (synced) {
    uint32_t today = bloomSystemTodayKey();
    if (today && today != bloomSystemLastDateKey) {
      bloomSystemLastDateKey = today;
      manualDay = today;  // reuse the existing BloomPetz daily-reset date path
      if (pets[activeSlot].occupied) serviceDailyReset(pets[activeSlot]);
      Serial.printf("BP|CLOCK|synced=1|date=%lu|timezone=%s\n",
                    (unsigned long)today, bloomSystemTimezone.c_str());
    }
  }

  if (synced != bloomSystemClockWasSynced) {
    bloomSystemClockWasSynced = synced;
    if (uiMode == SYSTEM_MENU) drawBloomSystemMenu();
  }

  if (uiMode == SYSTEM_MENU) {
    uint32_t sec = millis() / 1000UL;
    if (sec != bloomSystemLastUiSecond) {
      bloomSystemLastUiSecond = sec;
      drawBloomSystemMenu();
    }
  }
}

static void enterBloomSystemMenu() {
  uiMode = SYSTEM_MENU;
  bloomSystemGameIndex = 0;
  drawBloomSystemMenu();
}

'''
    s = s[:pos] + block + s[pos:]

    # Existing splash currently falls directly into slot picker. Route both the
    # timed completion and "skip splash" input path through the shared launcher.
    old_transition = re.compile(
        r"uiMode\s*=\s*SLOT_PICKER\s*;\s*\n\s*startupSlotIndex\s*=\s*\(activeSlot\s*<\s*3\)\s*\?\s*activeSlot\s*:\s*0\s*;\s*\n\s*drawStartupSlotPicker\(\)\s*;"
    )
    s, ntrans = old_transition.subn("enterBloomSystemMenu();", s)
    if ntrans < 1:
        raise SystemExit("Could not reroute startup SLOT_PICKER transition")

    # Add launcher input handling immediately before existing SLOT_PICKER handler.
    slot_handler = "  if (uiMode == SLOT_PICKER) {"
    hp = s.find(slot_handler, s.find("static void handleInput(Input in)"))
    if hp < 0:
        raise SystemExit("SLOT_PICKER input handler not found")
    handlers = r'''  if (uiMode == SYSTEM_MENU) {
    if (in == UP || in == DOWN) {
      bloomSystemGameIndex ^= 1U;
      drawBloomSystemMenu();
    } else if (in == AKEY) {
      if (bloomSystemGameIndex == 0) {
        uiMode = SLOT_PICKER;
        startupSlotIndex = (activeSlot < 3) ? activeSlot : 0;
        drawStartupSlotPicker();
      } else {
        uiMode = DND_PLACEHOLDER;
        drawDndPlaceholder();
      }
    }
    return;
  }
  if (uiMode == DND_PLACEHOLDER) {
    if (in == BKEY || in == AKEY) enterBloomSystemMenu();
    return;
  }
'''
    s = s[:hp] + handlers + s[hp:]

    # Start shared clock before the existing splash begins.
    setup_start = s.find("void setup() {")
    ss, se = brace_block(s, setup_start)
    setup = s[ss:se]
    if "beginBloomSystemClock();" not in setup:
        if "beginBootSplash();" in setup:
            setup = setup.replace("beginBootSplash();", "beginBloomSystemClock();\n  beginBootSplash();", 1)
        else:
            close = setup.rfind('}')
            setup = setup[:close] + "  beginBloomSystemClock();\n" + setup[close:]
    s = s[:ss] + setup + s[se:]

    # Service clock at the top of loop, before startup UI and daily-dependent game work.
    loop_start = s.find("void loop() {")
    if loop_start < 0:
        raise SystemExit("loop() not found")
    nl = s.find("\n", loop_start)
    if "serviceBloomSystemClock();" not in s[loop_start:loop_start+300]:
        s = s[:nl+1] + "  serviceBloomSystemClock();\n" + s[nl+1:]

    p.write_text(s)
    print(f"BLOOM SYSTEM launcher + shared NTP clock applied to {p}")
    print("Boot flow: splash -> BLOOM SYSTEM -> BLOOMPETZ slot picker or DND placeholder.")
    print("Launcher reads HAPPY JARZ Wi-Fi/timezone settings and displays local time/date.")
    print("When NTP syncs, YYYYMMDD is fed into BloomPetz manualDay for real daily resets.")
    print("Offline SET DATE fallback remains intact.")


if __name__ == "__main__":
    main()
