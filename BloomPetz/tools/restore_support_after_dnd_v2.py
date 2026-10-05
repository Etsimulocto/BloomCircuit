#!/usr/bin/env python3
"""Restore non-DND support code accidentally removed by repair_dnd_live_block_v2.py.

The v2 DND structural repair replaced from the DND marker through handleInput(),
which also removed unrelated Bloom System / startup / screensaver helpers that
lived between those points in the evolved local sketch.

This script restores ONLY the missing support slice from the automatic backup
created by repair_dnd_live_block_v2.py, while leaving the new infinite DND engine
untouched.
"""
from pathlib import Path
import sys

HANDLE = "static void handleInput(Input in)"
MARKER = "// BLOOM_SUPPORT_RESTORED_AFTER_DND_V2"

# These are the compile-log symbols that prove the support slice was lost.
NEEDED = [
    "bloomSystemSetHostTime",
    "enterBloomSystemMenu",
    "bloomSaverLastInputMs",
    "bloomSaverLightsOff",
    "chooseStartupSlot",
    "bloomSaverRmtReady",
    "bloomSaverInitApa106Rmt",
    "beginBloomSystemClock",
    "serviceBloomSystemClock",
    "serviceStartupUi",
    "serviceBloomSaver",
]


def fail(msg: str):
    raise SystemExit(msg)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: restore_support_after_dnd_v2.py <bloompetz_v0_1.ino>")

    target = Path(sys.argv[1]).expanduser().resolve()
    if not target.exists():
        fail(f"firmware not found: {target}")

    backup = target.with_suffix(target.suffix + ".pre_dnd_v2_repair")
    if not backup.exists():
        fail(f"expected repair backup not found: {backup}")

    current = target.read_text()
    old = backup.read_text()

    if MARKER in current:
        print("Support code already restored after DND v2 repair.")
        return

    if "// BLOOM_DND_INFINITE_ROOMS_DEPTH_V1" not in current:
        fail("new infinite DND engine is not present; refusing to modify")
    if current.count(HANDLE) != 1 or old.count(HANDLE) != 1:
        fail("handleInput anchor is missing/ambiguous")

    handle_old = old.index(HANDLE)
    handle_cur = current.index(HANDLE)

    # Find the earliest *definition/declaration* of any missing support symbol in
    # the pre-repair slice immediately before handleInput. Start on its line.
    positions = []
    for name in NEEDED:
        pos = old.rfind(name, 0, handle_old)
        if pos >= 0:
            positions.append((pos, name))

    if not positions:
        fail("none of the expected missing support symbols were found in backup")

    first_pos, first_name = min(positions)
    line_start = old.rfind("\n", 0, first_pos) + 1

    support = old[line_start:handle_old]
    if len(support.strip()) < 100:
        fail("recovered support slice is suspiciously small; refusing")

    # Ensure the recovered slice actually contains all compile-log symbols.
    missing_backup = [name for name in NEEDED if name not in support]
    if missing_backup:
        fail("backup support slice missing expected symbols: " + ", ".join(missing_backup))

    # Avoid reintroducing the old DND engine. The support tail should start after
    # dndStartGame/dndHandleInput in the backup; refuse if any DND engine markers
    # or starter-room fingerprints are present.
    forbidden = [
        "// BLOOM_DND_PLAYABLE_V0_1",
        "static void dndStartGame()",
        '"#..c...^',
        '"#....+......!#"',
    ]
    found_forbidden = [x for x in forbidden if x in support]
    if found_forbidden:
        fail("recovered support slice overlaps old DND engine: " + ", ".join(found_forbidden))

    # Most of these names should currently be missing as definitions. If all of
    # them already exist, there is nothing to repair.
    already = [name for name in NEEDED if name in current[:handle_cur]]
    if len(already) == len(NEEDED):
        print("All support symbols already present before handleInput; no repair needed.")
        return

    insertion = (
        "// BLOOM_SUPPORT_RESTORED_AFTER_DND_V2\n"
        "// Restored verbatim from .ino.pre_dnd_v2_repair after the infinite-DND\n"
        "// replacement accidentally consumed this unrelated support region.\n"
        + support.rstrip() + "\n\n"
    )

    repaired = current[:handle_cur] + insertion + current[handle_cur:]

    # Verify new DND survives and restored support names are visible.
    required_after = [
        "// BLOOM_DND_INFINITE_ROOMS_DEPTH_V1",
        "// BLOOM_DND_GUARANTEED_EXIT_V1",
        "// BLOOM_DND_ENGINE_OWNERSHIP_PROBE_V1",
        MARKER,
    ] + NEEDED
    missing_after = [x for x in required_after if x not in repaired]
    if missing_after:
        fail("post-restore verification failed: " + ", ".join(missing_after))

    target.write_text(repaired)
    print(f"Restored Bloom System/startup/screensaver support: {target}")
    print(f"Source backup: {backup}")
    print(f"Support slice begins at backup symbol: {first_name}")
    print("Infinite 30x16 DND engine remains installed.")
    print("Next: compile again; do NOT flash unless compile succeeds.")


if __name__ == "__main__":
    main()
