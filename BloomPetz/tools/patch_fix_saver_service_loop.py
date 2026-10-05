#!/usr/bin/env python3
"""Repair BloomPetz screensaver/light service integration after the first light patch.

Fixes:
- ensures serviceBloomSaverLights() is called from serviceBloomSaver(), not recursively
- keeps 30-second HOME idle -> SCREEN_SAVER transition explicit
- preserves RMT APA106 transport and 25% screensaver brightness
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_SAVER_SERVICE_LOOP_FIX_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_fix_saver_service_loop.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Saver service-loop fix already applied.")
        return

    required = [
        "static void serviceBloomSaverLights()",
        "static void serviceBloomSaver()",
        "BLOOMPETZ_SAVER_IDLE_MS",
        "SCREEN_SAVER",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Missing anchors: " + ", ".join(missing))

    # Remove any accidental self-recursion inside serviceBloomSaverLights().
    m = re.search(r"static void serviceBloomSaverLights\(\)\s*\{", s)
    if not m:
        raise SystemExit("serviceBloomSaverLights() not found")
    start = m.start()
    brace = s.find('{', m.start())
    depth = 0
    end = None
    for i in range(brace, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise SystemExit("Unbalanced serviceBloomSaverLights()")
    block = s[start:end]
    block = block.replace("\n  serviceBloomSaverLights();\n", "\n")
    s = s[:start] + block + s[end:]

    # Replace the whole serviceBloomSaver() body with the intended stable version.
    m = re.search(r"static void serviceBloomSaver\(\)\s*\{", s)
    if not m:
        raise SystemExit("serviceBloomSaver() not found")
    start = m.start()
    brace = s.find('{', m.start())
    depth = 0
    end = None
    for i in range(brace, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise SystemExit("Unbalanced serviceBloomSaver()")

    new_service = r'''// BLOOMPETZ_SAVER_SERVICE_LOOP_FIX_V1
static void serviceBloomSaver() {
  unsigned long now = millis();

  if (bloomSaverLastInputMs == 0) bloomSaverLastInputMs = now;

  if (uiMode == HOME) {
    if (now - bloomSaverLastInputMs >= BLOOMPETZ_SAVER_IDLE_MS) {
      uiMode = SCREEN_SAVER;
      bloomSaverPhase = 0;
      bloomSaverLastFrameMs = 0;
      bloomSaverBlinkUntilMs = 0;
      bloomSaverNextBlinkMs = now + random(1200, 3600);
      bloomSaverNextLightMs = 0;
      drawBloomSaver();
      serviceBloomSaverLights();
    }
    return;
  }

  if (uiMode != SCREEN_SAVER) return;

  serviceBloomSaverLights();

  if (bloomSaverNextBlinkMs == 0 || now >= bloomSaverNextBlinkMs) {
    bloomSaverBlinkUntilMs = now + random(140, 360);
    bloomSaverNextBlinkMs = now + random(1200, 4200);
  }

  if (now - bloomSaverLastFrameMs >= 220) {
    bloomSaverLastFrameMs = now;
    ++bloomSaverPhase;
    drawBloomSaver();
  }
}
'''

    s = s[:start] + new_service + s[end:]

    # Sanity: serviceBloomSaverLights() should appear exactly twice as a call in the
    # intended service function (entry + active loop), and never call itself.
    lm = re.search(r"static void serviceBloomSaverLights\(\)\s*\{([\s\S]*?)\n\}", s)
    if lm and "serviceBloomSaverLights();" in lm.group(1):
        raise SystemExit("Self-recursion still present in serviceBloomSaverLights()")

    p.write_text(s)
    print(f"Repaired screensaver service loop in {p}")
    print("30s HOME idle -> SCREEN_SAVER is explicit again.")
    print("RMT light service now runs continuously only while SCREEN_SAVER is active.")
    print("Existing 25% saver brightness and APA106 transport are unchanged.")


if __name__ == "__main__":
    main()
