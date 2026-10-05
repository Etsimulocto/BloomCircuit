#!/usr/bin/env python3
"""Repair BloomPetz pet ticker after marquee patch collided with earlier sayings patch.

This patch is intentionally surgical against the user's working local sketch:
- removes the erroneous early marquee block that references PET_SAYINGS/uiMode/HOME
  before those symbols exist
- keeps the existing later PET_SAYINGS bank
- replaces the later petTickerLine implementation with alternating art/saying logic
- adds marquee state/service logic after UI symbols exist
- hooks servicePetTicker() into loop() if needed

Result:
- 10s pet art
- 10s saying
- sayings >16 chars marquee at 350ms/char
- art and saying are never combined on one line
"""
from pathlib import Path
import re, sys

MARKER = "// BLOOMPETZ_TICKER_COLLISION_FIX_V1"


def die(msg):
    raise SystemExit(msg)


def main():
    if len(sys.argv) != 2:
        die("usage: patch_fix_pet_ticker_collisions.py <bloompetz_v0_1.ino>")
    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()
    if MARKER in s:
        print("Pet ticker collision fix already applied.")
        return

    # Remove the bad early block from the previous marquee patch. It begins at
    # the duplicate state near the earlier screen/render helpers and ends right
    # before the next unrelated declaration. Match by the distinctive helper
    # set rather than line numbers.
    bad = re.compile(
        r"\nstatic uint16_t petSayingIndex = 0;\n"
        r"static unsigned long petTickerPhaseMs = 0;\n"
        r"static unsigned long petMarqueeMs = 0;\n"
        r"static uint16_t petMarqueeOffset = 0;\n"
        r"static bool petTickerShowSaying = false;\n"
        r".*?"
        r"static void servicePetTicker\(\) \{.*?\n\}\n",
        re.S,
    )
    matches = list(bad.finditer(s))
    if matches:
        # Remove only the first occurrence: the erroneous early insertion.
        m = matches[0]
        s = s[:m.start()] + "\n" + s[m.end():]

    # Locate the later, valid sayings area. We require PET_SAYINGS and the
    # existing petTickerLine from the earlier sayings patch.
    if "PET_SAYINGS" not in s:
        die("PET_SAYINGS bank not found; refusing to guess")

    # Remove duplicate ticker state declarations around the later sayings block
    # so we can install one authoritative state set.
    s = re.sub(r"\nstatic uint16_t petSayingIndex = 0;\n", "\n", s)
    s = re.sub(r"\nstatic unsigned long petSayingLastMs = 0;\n", "\n", s)
    s = re.sub(r"\nstatic bool petSayingShowArt = [^;]+;\n", "\n", s)

    # Replace all prior petTickerLine definitions with one later implementation.
    s = re.sub(
        r"\nstatic String petTickerLine\(const PetSave &p\) \{.*?\n\}\n",
        "\n",
        s,
        flags=re.S,
    )

    # Add declarations/logic immediately AFTER the PET_SAYINGS array closing.
    # Find the array by declaration and its terminating `};`.
    arr = re.search(r"(static\s+const\s+char\s*\*\s*(?:const\s+)?PET_SAYINGS\s*\[\s*\]\s*=\s*\{.*?\n\};)", s, re.S)
    if not arr:
        # Accept PROGMEM or alternate spacing/type spellings.
        arr = re.search(r"(PET_SAYINGS[^=]*=\s*\{.*?\n\};)", s, re.S)
    if not arr:
        die("Could not locate PET_SAYINGS array body")

    block = r'''

// BLOOMPETZ_TICKER_COLLISION_FIX_V1
static uint16_t petSayingIndex = 0;
static unsigned long petTickerPhaseMs = 0;
static unsigned long petMarqueeMs = 0;
static uint16_t petMarqueeOffset = 0;
static bool petTickerShowSaying = false;
static constexpr unsigned long PET_TICKER_PHASE_MS = 10000UL;
static constexpr unsigned long PET_MARQUEE_STEP_MS = 350UL;

static uint16_t petSayingCount() {
  return (uint16_t)(sizeof(PET_SAYINGS) / sizeof(PET_SAYINGS[0]));
}

static String petTickerLine(const PetSave &p) {
  if (!petTickerShowSaying) return String(p.art);
  uint16_t count = petSayingCount();
  if (!count) return String(p.art);
  String msg = String(PET_SAYINGS[petSayingIndex % count]);
  if (msg.length() <= 16) return msg;
  String belt = msg + "   ";
  uint16_t span = belt.length();
  if (!span) return msg.substring(0, 16);
  String out;
  for (uint8_t i = 0; i < 16; ++i) out += belt[(petMarqueeOffset + i) % span];
  return out;
}

static void servicePetTicker() {
  if (uiMode != HOME) return;
  PetSave &p = pets[activeSlot];
  if (!p.occupied) return;
  unsigned long now = millis();
  if (petTickerPhaseMs == 0) petTickerPhaseMs = now;
  if (now - petTickerPhaseMs >= PET_TICKER_PHASE_MS) {
    petTickerPhaseMs = now;
    petTickerShowSaying = !petTickerShowSaying;
    petMarqueeOffset = 0;
    petMarqueeMs = now;
    if (petTickerShowSaying) {
      uint16_t count = petSayingCount();
      if (count) petSayingIndex = (uint16_t)random(count);
    }
    drawHome();
    return;
  }
  if (!petTickerShowSaying) return;
  uint16_t count = petSayingCount();
  if (!count) return;
  String msg = String(PET_SAYINGS[petSayingIndex % count]);
  if (msg.length() <= 16) return;
  if (now - petMarqueeMs >= PET_MARQUEE_STEP_MS) {
    petMarqueeMs = now;
    ++petMarqueeOffset;
    drawHome();
  }
}
'''
    s = s[:arr.end()] + block + s[arr.end():]

    # Ensure drawHome uses ticker line as row 1, not p.art or combined art+saying.
    # Replace the occupied-home render call conservatively.
    home_pat = re.compile(
        r"renderDisplay\((?:petTickerLine\(p\)|p\.art|[^,\n]+),\s*String\(p\.name\),\s*line3,\s*line4\);"
    )
    if home_pat.search(s):
        s = home_pat.sub("renderDisplay(petTickerLine(p), String(p.name), line3, line4);", s, count=1)
    elif "renderDisplay(petTickerLine(p), String(p.name), line3, line4);" not in s:
        die("Could not locate occupied drawHome renderDisplay call")

    # Hook service into loop after serial service. Avoid duplicate hook.
    if "servicePetTicker();" not in s:
        loop_anchor = "void loop() {\n  serviceSerial();"
        if loop_anchor not in s:
            die("loop/serviceSerial anchor not found")
        s = s.replace(loop_anchor, loop_anchor + "\n  servicePetTicker();", 1)

    p.write_text(s)
    print(f"Pet ticker collision fix applied to {p}")
    print("Line 1 alternates 10s ART / 10s SAYING; long sayings marquee at 350ms/char.")


if __name__ == "__main__":
    main()
