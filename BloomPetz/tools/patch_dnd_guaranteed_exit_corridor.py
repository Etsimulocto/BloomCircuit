#!/usr/bin/env python3
"""Guarantee every infinite DND room has at least one reachable exit.

Fixes the first infinite-room generator bug: doors were placed randomly on the
outer border after random internal wall scars were generated, but no connectivity
check existed. A room could therefore spawn with every exit cut off from the
player.

This patch replaces only the door-placement block inside the current infinite
DND engine. It keeps the 30x16 room, 14x4 camera, 7-char HUD, depth scaling,
and disposable one-way room behavior unchanged.
"""
from pathlib import Path
import sys

MARKER = "// BLOOM_DND_GUARANTEED_EXIT_V1"

OLD = r'''  // 2-4 one-way exits. Stepping through any one destroys this room and creates
  // the next random room. No return edge is stored.
  uint8_t doors = (uint8_t)random(2,5);
  for (uint8_t i=0;i<doors;++i) {
    uint8_t side = (uint8_t)random(4);
    if (side == 0) dndMap[0][random(2,DND_ROOM_W-2)] = '+';
    else if (side == 1) dndMap[DND_ROOM_H-1][random(2,DND_ROOM_W-2)] = '+';
    else if (side == 2) dndMap[random(2,DND_ROOM_H-2)][0] = '+';
    else dndMap[random(2,DND_ROOM_H-2)][DND_ROOM_W-1] = '+';
  }
'''

NEW = r'''  // BLOOM_DND_GUARANTEED_EXIT_V1
  // Always create one guaranteed reachable one-way exit first. Random wall scars
  // may partition the room, so carve a Manhattan corridor from the player to the
  // cell directly inside the chosen border door. This prevents unwinnable rooms.
  uint8_t guaranteedSide = (uint8_t)random(4);
  int8_t doorX = dndPlayerX;
  int8_t doorY = dndPlayerY;
  int8_t goalX = dndPlayerX;
  int8_t goalY = dndPlayerY;

  if (guaranteedSide == 0) {          // top
    doorX = (int8_t)random(2, DND_ROOM_W-2);
    doorY = 0;
    goalX = doorX;
    goalY = 1;
  } else if (guaranteedSide == 1) {   // bottom
    doorX = (int8_t)random(2, DND_ROOM_W-2);
    doorY = DND_ROOM_H-1;
    goalX = doorX;
    goalY = DND_ROOM_H-2;
  } else if (guaranteedSide == 2) {   // left
    doorX = 0;
    doorY = (int8_t)random(2, DND_ROOM_H-2);
    goalX = 1;
    goalY = doorY;
  } else {                            // right
    doorX = DND_ROOM_W-1;
    doorY = (int8_t)random(2, DND_ROOM_H-2);
    goalX = DND_ROOM_W-2;
    goalY = doorY;
  }

  int8_t carveX = dndPlayerX;
  int8_t carveY = dndPlayerY;
  dndMap[(uint8_t)carveY][(uint8_t)carveX] = '.';
  while (carveX != goalX) {
    carveX += (goalX > carveX) ? 1 : -1;
    dndMap[(uint8_t)carveY][(uint8_t)carveX] = '.';
  }
  while (carveY != goalY) {
    carveY += (goalY > carveY) ? 1 : -1;
    dndMap[(uint8_t)carveY][(uint8_t)carveX] = '.';
  }
  dndMap[(uint8_t)doorY][(uint8_t)doorX] = '+';

  // Add 1-3 extra random one-way exits for variety. They do not need individual
  // connectivity guarantees because the room already has one proven route out.
  uint8_t extraDoors = (uint8_t)random(1,4);
  for (uint8_t i=0;i<extraDoors;++i) {
    uint8_t side = (uint8_t)random(4);
    if (side == 0) dndMap[0][random(2,DND_ROOM_W-2)] = '+';
    else if (side == 1) dndMap[DND_ROOM_H-1][random(2,DND_ROOM_W-2)] = '+';
    else if (side == 2) dndMap[random(2,DND_ROOM_H-2)][0] = '+';
    else dndMap[random(2,DND_ROOM_H-2)][DND_ROOM_W-1] = '+';
  }
'''


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_dnd_guaranteed_exit_corridor.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"firmware not found: {p}")

    s = p.read_text()
    if MARKER in s:
        print("Guaranteed DND exit corridor already applied.")
        return
    if "// BLOOM_DND_INFINITE_ROOMS_DEPTH_V1" not in s:
        raise SystemExit("infinite-room DND engine marker missing; refusing to guess")
    if OLD not in s:
        raise SystemExit("current random-door block not found; refusing to guess")

    s = s.replace(OLD, NEW, 1)
    p.write_text(s)
    print(f"Guaranteed reachable DND exit applied: {p}")
    print("Every generated room now has one carved path from player spawn to a + door.")
    print("Compile, flash, then restart BloomPetz Mini.")


if __name__ == "__main__":
    main()
