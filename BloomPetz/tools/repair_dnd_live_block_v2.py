#!/usr/bin/env python3
"""Repair the live evolved DND block using structural anchors that still exist.

Why this exists:
The earlier infinite-room patch assumed // BLOOMPETZ_USB_HOST_TIME_V1 appeared
AFTER the DND block. In the evolved local sketch that marker moved earlier, so the
patch correctly refused and the old hardcoded starter room remained active.

This repair:
- imports the known infinite-room ENGINE from patch_dnd_infinite_rooms_depth_scaling.py
- applies the guaranteed-exit replacement directly to that engine text
- applies the GEN30 ownership probe directly to that engine text
- replaces exactly one live DND block beginning at // BLOOM_DND_PLAYABLE_V0_1
  and ending immediately before static void handleInput(Input in)
- refuses if those structural anchors are missing/duplicated
- verifies old starter-room literals are gone after replacement

It intentionally does not depend on USB host-time marker placement.
"""
from pathlib import Path
import runpy
import sys

START = "// BLOOM_DND_PLAYABLE_V0_1"
END = "static void handleInput(Input in)"


def fail(msg: str):
    raise SystemExit(msg)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: repair_dnd_live_block_v2.py <bloompetz_v0_1.ino>")

    target = Path(sys.argv[1]).expanduser().resolve()
    if not target.exists():
        fail(f"firmware not found: {target}")

    tools = Path(__file__).resolve().parent
    inf = runpy.run_path(str(tools / "patch_dnd_infinite_rooms_depth_scaling.py"))
    guar = runpy.run_path(str(tools / "patch_dnd_guaranteed_exit_corridor.py"))

    engine = inf.get("ENGINE")
    if not engine:
        fail("could not load infinite-room ENGINE from patch tool")

    old_doors = guar.get("OLD")
    new_doors = guar.get("NEW")
    if not old_doors or not new_doors or old_doors not in engine:
        fail("guaranteed-exit door block does not match infinite ENGINE; refusing")
    engine = engine.replace(old_doors, new_doors, 1)

    startup_old = '''  dndGenerateRoom(false);\n  dndQueue("DND BEGINS");\n  dndQueue("ROOM 1 MOD +/-1");\n'''
    startup_new = '''  dndGenerateRoom(false);\n  // BLOOM_DND_ENGINE_OWNERSHIP_PROBE_V1\n  {\n    int8_t probeX = (dndPlayerX <= (DND_ROOM_W - 5)) ? (dndPlayerX + 3) : (dndPlayerX - 3);\n    int8_t step = (probeX > dndPlayerX) ? 1 : -1;\n    for (int8_t x = dndPlayerX; x != probeX; x += step) {\n      dndMap[(uint8_t)dndPlayerY][(uint8_t)x] = '.';\n    }\n    dndMap[(uint8_t)dndPlayerY][(uint8_t)probeX] = '+';\n  }\n  dndQueue("GEN30 LIVE");\n  dndQueue("ROOM 1 MOD +/-1");\n'''
    if startup_old not in engine:
        fail("startup anchor missing inside infinite ENGINE; refusing")
    engine = engine.replace(startup_old, startup_new, 1)

    s = target.read_text()

    if s.count(START) != 1:
        fail(f"expected exactly one DND start marker, found {s.count(START)}")
    if s.count(END) != 1:
        fail(f"expected exactly one global handleInput anchor, found {s.count(END)}")

    start = s.index(START)
    end = s.index(END, start)
    if end <= start:
        fail("handleInput anchor was not after DND block")

    # Sanity check: the section being replaced really is the old DND engine.
    old_block = s[start:end]
    if "static void dndStartGame()" not in old_block:
        fail("DND block does not contain dndStartGame(); refusing")
    if "#..c...^" not in old_block:
        fail("expected old starter-room fingerprint not found in live DND block; refusing")

    repaired = s[:start] + engine.rstrip() + "\n\n" + s[end:]

    required_after = [
        "// BLOOM_DND_INFINITE_ROOMS_DEPTH_V1",
        "// BLOOM_DND_GUARANTEED_EXIT_V1",
        "// BLOOM_DND_ENGINE_OWNERSHIP_PROBE_V1",
        "static constexpr uint8_t DND_ROOM_W = 30;",
        "static constexpr uint8_t DND_ROOM_H = 16;",
        'dndQueue("GEN30 LIVE");',
    ]
    missing = [x for x in required_after if x not in repaired]
    if missing:
        fail("post-repair verification failed: " + ", ".join(missing))
    if "#..c...^" in repaired or '"#....+......!#"' in repaired:
        fail("old starter-room literals survived replacement; refusing to write")
    if repaired.count("static void dndStartGame()") != 1:
        fail("post-repair duplicate dndStartGame detected; refusing to write")

    backup = target.with_suffix(target.suffix + ".pre_dnd_v2_repair")
    if not backup.exists():
        backup.write_text(s)
    target.write_text(repaired)

    print(f"Repaired live DND block: {target}")
    print(f"Backup: {backup}")
    print("Installed: 30x16 infinite rooms + guaranteed exit + GEN30 ownership probe")
    print("Removed old hardcoded starter room from the active DND block.")
    print("Next: verify markers, then compile and flash.")


if __name__ == "__main__":
    main()
