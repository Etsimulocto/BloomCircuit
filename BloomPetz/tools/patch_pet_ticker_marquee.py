#!/usr/bin/env python3
"""Repair BloomPetz line-1 ticker behavior.

Behavior:
- Never combine pet art and saying on the same frame.
- Alternate every 10 seconds between PET ART mode and SAYING mode.
- Short sayings (<=16 chars) show centered/static through renderDisplay fit16.
- Long sayings scroll as a marquee across line 1 while the saying mode is active.
- Preserve the existing 260-saying bank added by patch_pet_sayings_ticker.py.

This patch targets the user's working local firmware after the sayings and home-status
patches have already been applied.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_PET_TICKER_MARQUEE_V1"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_pet_ticker_marquee.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Pet ticker marquee already applied.")
        return

    # Find the saying-bank symbol name without depending on one exact patch layout.
    m = re.search(r"static\s+const\s+char\s*\*\s*(?:const\s+)?(PET_[A-Z0-9_]*SAY[A-Z0-9_]*)\s*\[", s)
    if not m:
        m = re.search(r"static\s+const\s+char\s*\*\s*(?:const\s+)?([A-Za-z0-9_]*say[A-Za-z0-9_]*)\s*\[", s)
    if not m:
        raise SystemExit("Could not locate existing pet saying bank. Apply the sayings patch first.")
    bank = m.group(1)

    # Resolve a count expression from sizeof(bank)/sizeof(bank[0]) so we don't need
    # to know whether the prior patch declared an explicit count constant.
    anchor = "static bool actionDone(const PetSave &p, uint8_t action)"
    if anchor not in s:
        raise SystemExit("Pet engine anchor not found")

    block = f'''\n\n{MARKER}\nstatic constexpr unsigned long PET_TICKER_MODE_MS = 10000UL;\nstatic constexpr unsigned long PET_MARQUEE_STEP_MS = 350UL;\nstatic unsigned long petTickerModeStartedMs = 0;\nstatic unsigned long petMarqueeLastStepMs = 0;\nstatic uint16_t petSayingIndex = 0;\nstatic uint16_t petMarqueeOffset = 0;\nstatic bool petTickerShowingSaying = false;\n\nstatic uint16_t petSayingCount() {{\n  return (uint16_t)(sizeof({bank}) / sizeof({bank}[0]));\n}}\n\nstatic void chooseNextPetSaying() {{\n  uint16_t count = petSayingCount();\n  if (!count) {{ petSayingIndex = 0; return; }}\n  uint16_t next = (uint16_t)random(count);\n  if (count > 1 && next == petSayingIndex) next = (uint16_t)((next + 1) % count);\n  petSayingIndex = next;\n  petMarqueeOffset = 0;\n}}\n\nstatic String petTickerLine(const PetSave &p) {{\n  if (!petTickerShowingSaying) return String(p.art);\n\n  uint16_t count = petSayingCount();\n  if (!count) return String(p.art);\n  String msg = String({bank}[petSayingIndex % count]);\n  if (msg.length() <= 16) return msg;\n\n  // Circular marquee with a 4-space breathing gap between repeats.\n  String looped = msg + "    " + msg;\n  uint16_t cycle = (uint16_t)(msg.length() + 4);\n  uint16_t off = cycle ? (petMarqueeOffset % cycle) : 0;\n  if (off + 16 > looped.length()) looped += msg + "    ";\n  return looped.substring(off, off + 16);\n}}\n\nstatic void servicePetTicker() {{\n  if (uiMode != HOME) return;\n  PetSave &p = pets[activeSlot];\n  if (!p.occupied) return;\n\n  unsigned long now = millis();\n  if (petTickerModeStartedMs == 0) petTickerModeStartedMs = now;\n\n  if (now - petTickerModeStartedMs >= PET_TICKER_MODE_MS) {{\n    petTickerModeStartedMs = now;\n    petTickerShowingSaying = !petTickerShowingSaying;\n    petMarqueeOffset = 0;\n    petMarqueeLastStepMs = now;\n    if (petTickerShowingSaying) chooseNextPetSaying();\n    drawHome();\n    return;\n  }}\n\n  if (petTickerShowingSaying) {{\n    uint16_t count = petSayingCount();\n    if (count) {{\n      String msg = String({bank}[petSayingIndex % count]);\n      if (msg.length() > 16 && now - petMarqueeLastStepMs >= PET_MARQUEE_STEP_MS) {{\n        petMarqueeLastStepMs = now;\n        petMarqueeOffset++;\n        drawHome();\n      }}\n    }}\n  }}\n}}\n'''
    s = s.replace(anchor, block + "\n" + anchor, 1)

    # Ensure drawHome uses the ticker line only; don't combine art+saying.
    # Replace the first renderDisplay call inside drawHome's occupied-pet path.
    dm = re.search(r"static void drawHome\(\) \{(?P<body>.*?)\n\}", s, re.S)
    if not dm:
        raise SystemExit("drawHome() not found")
    body = dm.group("body")
    # Find final renderDisplay in drawHome. Prior patches may already use a ticker helper.
    renders = list(re.finditer(r"renderDisplay\(([^;]+)\);", body))
    if not renders:
        raise SystemExit("drawHome renderDisplay not found")
    r = renders[-1]
    old_call = r.group(0)
    # Preserve args 2..4 by parsing simple comma separation from known drawHome shape.
    inner = r.group(1)
    parts = [x.strip() for x in inner.split(",", 3)]
    if len(parts) != 4:
        raise SystemExit("Unexpected drawHome renderDisplay shape")
    new_call = f"renderDisplay(petTickerLine(p), {parts[1]}, {parts[2]}, {parts[3]});"
    new_body = body[:r.start()] + new_call + body[r.end():]
    s = s[:dm.start("body")] + new_body + s[dm.end("body"):]

    # Service the ticker continuously from loop, after serial service if possible.
    if "servicePetTicker();" not in s:
        loop_anchor = "void loop() {\n  serviceSerial();"
        if loop_anchor in s:
            s = s.replace(loop_anchor, "void loop() {\n  serviceSerial();\n  servicePetTicker();", 1)
        else:
            lm = re.search(r"void loop\(\) \{", s)
            if not lm:
                raise SystemExit("loop() not found")
            s = s[:lm.end()] + "\n  servicePetTicker();" + s[lm.end():]

    p.write_text(s)
    print(f"Pet ticker marquee applied to {p}")
    print("Line 1 now alternates: 10s pet art / 10s saying; long sayings marquee at 350ms/char.")


if __name__ == "__main__":
    main()
