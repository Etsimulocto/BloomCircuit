#!/usr/bin/env python3
"""Replace BLOOM SYSTEM Wi-Fi/NTP clock with USB host-device time sync.

The ESP32 cannot query a USB host clock by itself. BloomPetz Mini already owns the
USB serial connection, so this patch makes the host app periodically send:

    SET HOSTTIME <unix_epoch> <utc_offset_minutes>

Firmware keeps a local clock from that base using millis(), displays host-local
HH:MM + MM/DD in the BLOOM SYSTEM launcher, and feeds YYYYMMDD into manualDay so
existing BloomPetz daily-reset logic works without Wi-Fi.

Also patches BloomPetz/desktop/bloompetz_mini.py to send host time on connect and
periodically while connected.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_USB_HOST_TIME_V1"
DESKTOP_MARKER = "# BLOOMPETZ_USB_HOST_TIME_V1"


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


def patch_firmware(p: Path):
    s = p.read_text()
    if MARKER in s:
        print("Firmware USB host-time patch already applied.")
        return
    if "// BLOOMPETZ_SYSTEM_LAUNCHER_CLOCK_V1" not in s:
        raise SystemExit("BLOOM SYSTEM launcher clock V1 is not present in firmware")

    # Wi-Fi is no longer needed by this clock layer.
    s = re.sub(r'^#include <WiFi\.h>\s*\n', '', s, flags=re.M)

    start = s.find("// BLOOMPETZ_SYSTEM_LAUNCHER_CLOCK_V1")
    end = s.find("static void serviceStartupUi() {", start)
    if start < 0 or end < 0:
        raise SystemExit("Could not locate launcher clock block")

    block = r'''// BLOOMPETZ_SYSTEM_LAUNCHER_CLOCK_V1
// BLOOMPETZ_USB_HOST_TIME_V1
static uint8_t bloomSystemGameIndex = 0;
static bool bloomSystemHostClockValid = false;
static int64_t bloomSystemHostEpochUtc = 0;
static int32_t bloomSystemHostOffsetMinutes = 0;
static uint32_t bloomSystemHostClockSetMs = 0;
static uint32_t bloomSystemLastDateKey = 0;
static uint32_t bloomSystemLastUiSecond = 0;

static int64_t bloomSystemUtcNow() {
  if (!bloomSystemHostClockValid) return 0;
  return bloomSystemHostEpochUtc + (int64_t)((millis() - bloomSystemHostClockSetMs) / 1000UL);
}

static bool bloomSystemLocalTm(struct tm &out) {
  if (!bloomSystemHostClockValid) return false;
  time_t localEpoch = (time_t)(bloomSystemUtcNow() + (int64_t)bloomSystemHostOffsetMinutes * 60LL);
  gmtime_r(&localEpoch, &out);
  return true;
}

static uint32_t bloomSystemTodayKey() {
  struct tm t;
  if (!bloomSystemLocalTm(t)) return 0;
  return (uint32_t)(t.tm_year + 1900) * 10000UL +
         (uint32_t)(t.tm_mon + 1) * 100UL +
         (uint32_t)t.tm_mday;
}

static String bloomSystemClockLine() {
  struct tm t;
  if (!bloomSystemLocalTm(t)) return "--:-- --/-- USB";
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

static void bloomSystemSetHostTime(int64_t epochUtc, int32_t offsetMinutes) {
  if (epochUtc < 1700000000LL) return;
  bloomSystemHostEpochUtc = epochUtc;
  bloomSystemHostOffsetMinutes = constrain(offsetMinutes, -840, 840);
  bloomSystemHostClockSetMs = millis();
  bloomSystemHostClockValid = true;

  uint32_t today = bloomSystemTodayKey();
  if (today) {
    bloomSystemLastDateKey = today;
    manualDay = today;
    if (pets[activeSlot].occupied) serviceDailyReset(pets[activeSlot]);
  }
  Serial.printf("BP|CLOCK|source=USB|date=%lu|offset_min=%ld\n",
                (unsigned long)today, (long)bloomSystemHostOffsetMinutes);
  if (uiMode == SYSTEM_MENU) drawBloomSystemMenu();
}

static void beginBloomSystemClock() {
  // Host app will supply time over the already-open USB serial connection.
  bloomSystemHostClockValid = false;
}

static void serviceBloomSystemClock() {
  if (bloomSystemHostClockValid) {
    uint32_t today = bloomSystemTodayKey();
    if (today && today != bloomSystemLastDateKey) {
      bloomSystemLastDateKey = today;
      manualDay = today;
      if (pets[activeSlot].occupied) serviceDailyReset(pets[activeSlot]);
      Serial.printf("BP|CLOCK|source=USB|date=%lu|daily_reset_check=1\n",
                    (unsigned long)today);
    }
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
    s = s[:start] + block + s[end:]

    # Add command parsing before the existing FEED command in serviceSerial().
    anchor = '  if (cmd == "FEED")'
    pos = s.find(anchor)
    if pos < 0:
        anchor = 'if (cmd == "FEED")'
        pos = s.find(anchor)
    if pos < 0:
        raise SystemExit("Could not locate serial command dispatch anchor")
    command = r'''  if (cmd.startsWith("SET HOSTTIME ")) {
    String rest = cmd.substring(13);
    int sp = rest.indexOf(' ');
    if (sp > 0) {
      int64_t epochUtc = strtoll(rest.substring(0, sp).c_str(), nullptr, 10);
      int32_t offsetMin = rest.substring(sp + 1).toInt();
      bloomSystemSetHostTime(epochUtc, offsetMin);
    }
    return;
  }
'''
    # Preserve current indentation even if anchor fallback had none.
    s = s[:pos] + command + s[pos:]
    p.write_text(s)
    print(f"Firmware now uses USB host time instead of Wi-Fi/NTP: {p}")


def patch_desktop(p: Path):
    s = p.read_text()
    if DESKTOP_MARKER in s:
        print("Desktop USB host-time patch already applied.")
        return

    # Add state for periodic clock refresh.
    needle = "        self.connected_port: str | None = None\n"
    if needle not in s:
        raise SystemExit("Desktop connected_port anchor missing")
    s = s.replace(needle, needle + "        self.last_host_time_send = 0.0  " + DESKTOP_MARKER + "\n", 1)

    # Add helper before _serial_worker.
    anchor = "    def _serial_worker(self):\n"
    pos = s.find(anchor)
    if pos < 0:
        raise SystemExit("Desktop _serial_worker anchor missing")
    helper = r'''    def _send_host_time(self):
        """Send this computer's current Unix time and local UTC offset to the ESP32."""
        now = time.time()
        lt = time.localtime(now)
        if lt.tm_isdst > 0 and time.daylight:
            offset_seconds = -time.altzone
        else:
            offset_seconds = -time.timezone
        offset_minutes = int(offset_seconds // 60)
        self.send(f"SET HOSTTIME {int(now)} {offset_minutes}")
        self.last_host_time_send = time.monotonic()

'''
    s = s[:pos] + helper + s[pos:]

    # Send immediately after serial connection setup commands.
    needle = '                self.send("HELLO")\n                self.send("GET SCREEN")\n                self.send("GET STATUS")\n'
    if needle not in s:
        raise SystemExit("Desktop connect command block missing")
    repl = needle + "                self._send_host_time()\n"
    s = s.replace(needle, repl, 1)

    # Refresh once per minute so DST/timezone/clock corrections follow the host.
    needle = "            port = self.connected_port\n"
    if needle not in s:
        raise SystemExit("Desktop connected loop anchor missing")
    repl = "            if time.monotonic() - self.last_host_time_send >= 60.0:\n                self._send_host_time()\n\n" + needle
    s = s.replace(needle, repl, 1)

    p.write_text(s)
    print(f"Desktop mirror now sends host clock on connect and every 60s: {p}")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_host_device_time.py <bloompetz_v0_1.ino>")
    firmware = Path(sys.argv[1]).expanduser().resolve()
    if not firmware.exists():
        raise SystemExit(f"Firmware not found: {firmware}")
    # firmware/.../bloompetz_v0_1.ino -> BloomPetz root
    try:
        bloompetz = firmware.parents[2]
    except IndexError:
        raise SystemExit("Unexpected BloomPetz firmware path")
    desktop = bloompetz / "desktop" / "bloompetz_mini.py"
    if not desktop.exists():
        raise SystemExit(f"Desktop mirror not found: {desktop}")
    patch_firmware(firmware)
    patch_desktop(desktop)
    print("USB host-time sync ready: no Wi-Fi credentials required.")
    print("Standalone fallback remains SET DATE YYYY-MM-DD.")


if __name__ == "__main__":
    main()
