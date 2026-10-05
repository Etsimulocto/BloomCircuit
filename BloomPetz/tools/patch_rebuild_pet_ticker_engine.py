#!/usr/bin/env python3
"""Rebuild the BloomPetz pet ticker engine after marquee patch collisions.

Safe local repair for a sketch that already has:
- BLOOMPETZ_PET_SAYINGS_V1 with PET_SAYINGS[]
- drawHome() already using petTickerLine(p)
- advancePetSayingIfDue() already called from loop()

This script:
1) removes the broken early BLOOMPETZ_PET_TICKER_MARQUEE_V1 block,
2) removes stray servicePetTicker() calls,
3) preserves the existing PET_SAYINGS[] bank,
4) replaces the old sayings/ticker state + functions with one engine that:
   - shows pet art alone for 10 seconds,
   - then a saying alone for 10 seconds,
   - marquees sayings longer than 16 chars at 350 ms/char,
   - then advances to the next saying and returns to art.
"""
from pathlib import Path
import re
import sys

FIX_MARKER = "// BLOOMPETZ_PET_TICKER_ENGINE_REBUILT_V1"
BAD_MARKER = "// BLOOMPETZ_PET_TICKER_MARQUEE_V1"
SAY_MARKER = "// BLOOMPETZ_PET_SAYINGS_V1"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_rebuild_pet_ticker_engine.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if FIX_MARKER in s:
        print("Pet ticker engine already rebuilt.")
        return

    # 1) Remove the broken early marquee block. It was inserted immediately
    # before actionDone(), so use that stable engine function as the end anchor.
    if BAD_MARKER in s:
        start = s.find(BAD_MARKER)
        end = s.find("static bool actionDone(const PetSave &p, uint8_t action)", start)
        if end < 0:
            raise SystemExit("Found broken marquee marker but could not find actionDone() end anchor")
        s = s[:start] + s[end:]

    # 2) Remove the stray service call left by the broken block.
    s = re.sub(r"^[ \t]*servicePetTicker\(\);[ \t]*\n", "", s, flags=re.M)

    # 3) Locate the existing sayings bank and the later drawHome(). We preserve
    # the whole PET_SAYINGS[] declaration exactly as-is.
    marker_pos = s.find(SAY_MARKER)
    if marker_pos < 0:
        raise SystemExit("Existing BLOOMPETZ_PET_SAYINGS_V1 block not found")

    bank_start = s.find("static const char* const PET_SAYINGS[] = {", marker_pos)
    if bank_start < 0:
        raise SystemExit("PET_SAYINGS[] bank not found")

    bank_close = s.find("};", bank_start)
    if bank_close < 0:
        raise SystemExit("PET_SAYINGS[] closing brace not found")
    bank_end = bank_close + 2

    draw_pos = s.find("static void drawHome() {", bank_end)
    if draw_pos < 0:
        raise SystemExit("drawHome() not found after sayings bank")

    # Ensure HOME already consumes the ticker helper. If not, do a narrow,
    # drawHome-only replacement without depending on exact footer contents.
    draw_end = s.find("\nstatic void ", draw_pos + 1)
    if draw_end < 0:
        draw_end = len(s)
    draw_region = s[draw_pos:draw_end]
    if "petTickerLine(p)" not in draw_region:
        if "renderDisplay(p.art," not in draw_region:
            raise SystemExit("drawHome() is not using petTickerLine(p), and no p.art render anchor was found")
        draw_region = draw_region.replace("renderDisplay(p.art,", "renderDisplay(petTickerLine(p),", 1)
        s = s[:draw_pos] + draw_region + s[draw_end:]
        # Positions after drawHome may have shifted; recompute marker/bank/draw.
        marker_pos = s.find(SAY_MARKER)
        bank_start = s.find("static const char* const PET_SAYINGS[] = {", marker_pos)
        bank_close = s.find("};", bank_start)
        bank_end = bank_close + 2
        draw_pos = s.find("static void drawHome() {", bank_end)

    # 4) Replace everything between the bank and drawHome with one clean engine.
    engine = r'''

// BLOOMPETZ_PET_TICKER_ENGINE_REBUILT_V1
static constexpr uint16_t PET_SAYING_COUNT = sizeof(PET_SAYINGS) / sizeof(PET_SAYINGS[0]);
static constexpr uint32_t PET_TICKER_MODE_MS = 10000UL;
static constexpr uint32_t PET_MARQUEE_STEP_MS = 350UL;
static uint16_t petSayingIndex = 0;
static uint16_t petMarqueeOffset = 0;
static uint32_t petTickerModeStartedMs = 0;
static uint32_t petMarqueeLastStepMs = 0;
static bool petTickerShowingSaying = false;

static String petTickerLine(const PetSave &p) {
  if (!petTickerShowingSaying || PET_SAYING_COUNT == 0) return String(p.art);

  String msg = String(PET_SAYINGS[petSayingIndex % PET_SAYING_COUNT]);
  if (msg.length() <= 16) return msg;

  String looped = msg + "    " + msg + "    ";
  uint16_t cycle = (uint16_t)(msg.length() + 4U);
  uint16_t off = cycle ? (uint16_t)(petMarqueeOffset % cycle) : 0;
  while (off + 16 > looped.length()) looped += msg + "    ";
  return looped.substring(off, off + 16);
}

static void advancePetSayingIfDue() {
  if (uiMode != HOME || !pets[activeSlot].occupied) return;

  uint32_t now = millis();
  if (petTickerModeStartedMs == 0) {
    petTickerModeStartedMs = now;
    petMarqueeLastStepMs = now;
  }

  // Switch between ART and SAYING every 10 seconds.
  if (now - petTickerModeStartedMs >= PET_TICKER_MODE_MS) {
    petTickerModeStartedMs = now;
    petTickerShowingSaying = !petTickerShowingSaying;
    petMarqueeOffset = 0;
    petMarqueeLastStepMs = now;

    // When leaving a saying, move to the next one for the next saying phase.
    if (!petTickerShowingSaying && PET_SAYING_COUNT > 0) {
      petSayingIndex = (uint16_t)((petSayingIndex + 1U) % PET_SAYING_COUNT);
    }
    drawHome();
    return;
  }

  // Only long sayings need intermediate redraws for marquee motion.
  if (petTickerShowingSaying && PET_SAYING_COUNT > 0) {
    String msg = String(PET_SAYINGS[petSayingIndex % PET_SAYING_COUNT]);
    if (msg.length() > 16 && now - petMarqueeLastStepMs >= PET_MARQUEE_STEP_MS) {
      petMarqueeLastStepMs = now;
      petMarqueeOffset++;
      drawHome();
    }
  }
}
'''

    s = s[:bank_end] + engine + "\n" + s[draw_pos:]

    # The original sayings patch should already have this call. Ensure exactly one.
    calls = list(re.finditer(r"^[ \t]*advancePetSayingIfDue\(\);[ \t]*$", s, flags=re.M))
    if not calls:
        loop_pos = s.find("void loop() {")
        if loop_pos < 0:
            raise SystemExit("loop() not found")
        line_end = s.find("\n", loop_pos)
        s = s[:line_end + 1] + "  advancePetSayingIfDue();\n" + s[line_end + 1:]
    elif len(calls) > 1:
        first = calls[0]
        # Remove duplicates from bottom-up, preserving first.
        for m in reversed(calls[1:]):
            line_start = s.rfind("\n", 0, m.start()) + 1
            line_end = s.find("\n", m.end())
            if line_end < 0:
                line_end = len(s)
            else:
                line_end += 1
            s = s[:line_start] + s[line_end:]

    p.write_text(s)
    print(f"Pet ticker engine rebuilt in {p}")
    print("Behavior: 10s art / 10s saying; long sayings marquee at 350ms/char; no combined art+saying frames.")


if __name__ == "__main__":
    main()
