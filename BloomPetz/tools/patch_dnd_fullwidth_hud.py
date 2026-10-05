#!/usr/bin/env python3
"""Give DND the full OLED width and expand its HUD.

Targets local firmware after patch_dnd_playable_v0_1.py.

Changes:
- DND bypasses BloomPetz side-art/gutter rendering.
- Uses the raw 128px OLED width with the existing 6x12 font.
- Keeps the dungeon viewport at 12x4.
- Expands HUD from 4x4 to 9x4 and places the 12x4 map hard-right.
- DND menus/info/glossary also use the full-width renderer.

21 text columns total = 9 HUD + 12 map.
"""
from pathlib import Path
import sys

MARKER = "// BLOOM_DND_FULLWIDTH_HUD_V1"
START_MARKER = "// BLOOM_DND_PLAYABLE_V0_1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_dnd_fullwidth_hud.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("DND full-width HUD patch already applied.")
        return
    if START_MARKER not in s:
        raise SystemExit("DND playable v0.1 marker not found; apply patch_dnd_playable_v0_1.py first")

    old = "static constexpr uint8_t DND_HUD_W = 4;"
    if old not in s:
        raise SystemExit("Expected DND_HUD_W = 4 not found; refusing to guess")
    s = s.replace(old, "static constexpr uint8_t DND_HUD_W = 9;", 1)

    # Insert a DND-only renderer immediately before dndDrawPlay().
    anchor = "static void dndDrawPlay() {"
    pos = s.find(anchor)
    if pos < 0:
        raise SystemExit("dndDrawPlay() not found")

    renderer = r'''// BLOOM_DND_FULLWIDTH_HUD_V1
static void dndRenderFull(const String &r0, const String &r1,
                          const String &r2, const String &r3) {
  // DND owns the entire OLED. No BloomPetz side art/gutters.
  // Existing font is ~6 px wide, so 21 chars fit across 128 px.
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tr);
  oled.drawStr(0, 13, r0.substring(0, 21).c_str());
  oled.drawStr(0, 29, r1.substring(0, 21).c_str());
  oled.drawStr(0, 45, r2.substring(0, 21).c_str());
  oled.drawStr(0, 61, r3.substring(0, 21).c_str());
  oled.sendBuffer();
}

'''
    s = s[:pos] + renderer + s[pos:]

    # Replace renderer calls only inside the DND code block. The block lives between
    # the playable marker and the normal startup UI handler in the current firmware.
    start = s.find(START_MARKER)
    end = s.find("static void serviceStartupUi()", start)
    if end < 0:
        # Fallback: patch through handleInput if startup handler moved.
        end = s.find("static void handleInput(Input in)", start)
    if end < 0:
        raise SystemExit("Could not bound DND block safely; refusing to guess")

    chunk = s[start:end]
    if "renderDisplay(" not in chunk:
        raise SystemExit("No DND renderDisplay() calls found in bounded DND block")
    chunk = chunk.replace("renderDisplay(", "dndRenderFull(")
    s = s[:start] + chunk + s[end:]

    p.write_text(s)
    print(f"DND full-width renderer applied: {p}")
    print("Geometry: 21x4 total = 9x4 HUD + 12x4 map")
    print("BloomPetz rendering is unchanged outside DND.")


if __name__ == "__main__":
    main()
