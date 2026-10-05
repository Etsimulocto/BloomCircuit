#!/usr/bin/env python3
"""Stop BloomPetz side-art refresh from repainting over full-width DND.

Root cause proven from the live architecture:
- DND draws directly to the OLED with dndRenderFull() about every 120 ms.
- Legacy BloomPetz side-art service also redraws the OLED about every 120 ms via
  physicalOledRender(screenLines[0..3]).
- screenLines still contains the last normal UI frame (typically BLOOM SYSTEM),
  so the two renderers visibly alternate.

This patch does NOT remove side art. It simply prevents the legacy side-art
refresh from touching the OLED while uiMode == DND_PLACEHOLDER.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOM_DND_PAUSE_SIDE_ART_REFRESH_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_pause_side_art_during_dnd.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("DND side-art refresh guard already applied.")
        return

    required = [
        "DND_PLACEHOLDER",
        "lastSideArtMs",
        "physicalOledRender(screenLines[0], screenLines[1], screenLines[2], screenLines[3]);",
        "void loop() {",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required live anchors missing: " + ", ".join(missing))

    # Preferred exact form from the proven side-art service.
    old = '''  if (millis() - lastSideArtMs >= 120) {
    lastSideArtMs = millis();
    stepSideArt();
    physicalOledRender(screenLines[0], screenLines[1], screenLines[2], screenLines[3]);
  }'''
    new = '''  // BLOOM_DND_PAUSE_SIDE_ART_REFRESH_V1
  // DND owns the full OLED. Legacy side-art refresh must not repaint screenLines
  // over the dungeon while DND is active.
  if (uiMode != DND_PLACEHOLDER && millis() - lastSideArtMs >= 120) {
    lastSideArtMs = millis();
    stepSideArt();
    physicalOledRender(screenLines[0], screenLines[1], screenLines[2], screenLines[3]);
  }'''

    if old in s:
        s = s.replace(old, new, 1)
    else:
        # Conservative fallback: locate the one physicalOledRender(screenLines...)
        # call in loop and gate only that existing side-art timer block.
        loop_pos = s.find("void loop() {")
        if loop_pos < 0:
            raise SystemExit("loop() not found")
        call = "physicalOledRender(screenLines[0], screenLines[1], screenLines[2], screenLines[3]);"
        call_pos = s.find(call, loop_pos)
        if call_pos < 0:
            raise SystemExit("side-art physicalOledRender(screenLines...) call not found in loop")

        # Find nearest preceding if line containing lastSideArtMs.
        line_start = s.rfind("\n", 0, call_pos) + 1
        search_start = max(loop_pos, line_start - 600)
        region = s[search_start:call_pos]
        matches = list(re.finditer(r"^[ \t]*if \([^\n]*lastSideArtMs[^\n]*\) \{[ \t]*$", region, re.M))
        if not matches:
            raise SystemExit("Could not safely identify side-art timer if-block; refusing to guess")
        m = matches[-1]
        abs_start = search_start + m.start()
        abs_end = search_start + m.end()
        original_if = s[abs_start:abs_end]
        if "uiMode != DND_PLACEHOLDER" in original_if:
            print("Side-art timer already gated for DND.")
            return
        gated_if = original_if.replace("if (", "if (uiMode != DND_PLACEHOLDER && ", 1)
        s = s[:abs_start] + "  " + MARKER + "\n" + gated_if + s[abs_end:]

    p.write_text(s)
    print(f"Paused legacy side-art OLED refresh during DND: {p}")
    print("BloomPetz/System keep side art; DND gets exclusive full-width OLED ownership.")


if __name__ == "__main__":
    main()
