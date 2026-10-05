#!/usr/bin/env python3
"""Prove the active local DND engine owns startup and expose a visible room-1 portal.

This is a diagnostic/repair patch for the local Arduino sketch. It refuses to
modify the sketch unless the infinite-room engine and guaranteed-exit markers are
present exactly once. It also checks for duplicate DND startup/generator functions.

Changes:
- startup event says GEN30 LIVE so the flashed binary is unmistakable
- ROOM 1 gets one extra + portal exactly 3 cells horizontally from the player,
  guaranteed inside the initial camera and connected by floor
- stepping on that + uses the existing dndNextRoom() path

If GEN30 LIVE / the nearby + do not appear after a clean compile+flash, the board
is not running the file this script patched.
"""
from pathlib import Path
import sys

MARKER = "// BLOOM_DND_ENGINE_OWNERSHIP_PROBE_V1"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_dnd_engine_ownership_probe.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"firmware not found: {p}")

    s = p.read_text()

    if MARKER in s:
        print("DND engine ownership probe already applied.")
        return

    required = [
        "// BLOOM_DND_INFINITE_ROOMS_DEPTH_V1",
        "// BLOOM_DND_GUARANTEED_EXIT_V1",
        "static constexpr uint8_t DND_ROOM_W = 30;",
        "static constexpr uint8_t DND_ROOM_H = 16;",
        "static void dndGenerateRoom(bool announce)",
        "static void dndStartGame()",
        "dndGenerateRoom(false);",
        'dndQueue(\"DND BEGINS\");',
        'dndQueue(\"ROOM 1 MOD +/-1\");',
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("active infinite-engine anchors missing: " + ", ".join(missing))

    counts = {
        "dndStartGame": s.count("static void dndStartGame()"),
        "dndGenerateRoom": s.count("static void dndGenerateRoom(bool announce)"),
        "infinite marker": s.count("// BLOOM_DND_INFINITE_ROOMS_DEPTH_V1"),
    }
    bad = [f"{k}={v}" for k, v in counts.items() if v != 1]
    if bad:
        raise SystemExit("duplicate/ambiguous DND engine detected; refusing to guess: " + ", ".join(bad))

    old_room_literals = ["#..c...^", "#....+....!#"]
    found_old = [x for x in old_room_literals if x in s]
    if found_old:
        raise SystemExit("old hardcoded starter-room literal still exists in active sketch: " + ", ".join(found_old))

    anchor = '''  dndGenerateRoom(false);\n  dndQueue("DND BEGINS");\n  dndQueue("ROOM 1 MOD +/-1");\n'''
    if anchor not in s:
        raise SystemExit("startup generator anchor missing; refusing to guess")

    replacement = '''  dndGenerateRoom(false);\n  // BLOOM_DND_ENGINE_OWNERSHIP_PROBE_V1\n  // Put an unmistakable, reachable portal inside ROOM 1's initial camera.\n  // This proves the flashed binary is executing the 30x16 generator path.\n  {\n    int8_t probeX = (dndPlayerX <= (DND_ROOM_W - 5)) ? (dndPlayerX + 3) : (dndPlayerX - 3);\n    int8_t step = (probeX > dndPlayerX) ? 1 : -1;\n    for (int8_t x = dndPlayerX; x != probeX; x += step) {\n      dndMap[(uint8_t)dndPlayerY][(uint8_t)x] = '.';\n    }\n    dndMap[(uint8_t)dndPlayerY][(uint8_t)probeX] = '+';\n  }\n  dndQueue("GEN30 LIVE");\n  dndQueue("ROOM 1 MOD +/-1");\n'''

    s = s.replace(anchor, replacement, 1)
    p.write_text(s)

    print(f"DND ownership probe applied: {p}")
    print("Verified exactly one dndStartGame(), one dndGenerateRoom(), one infinite-engine marker.")
    print("Verified old hardcoded starter-room literals are absent.")
    print("ROOM 1 will show GEN30 LIVE and a + portal 3 cells horizontally from @.")
    print("If those do not appear after compile+flash, the wrong binary/sketch is being uploaded.")


if __name__ == "__main__":
    main()
