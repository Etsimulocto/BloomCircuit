#!/usr/bin/env python3
"""Add DND room archetypes plus Linux gamepad input to BloomPetz Mini.

Firmware changes are intentionally narrow:
- requires the live 30x16 infinite-room DND engine
- preserves depth scaling, camera, door logic, combat, and display ownership
- replaces ONLY the old random wall-scar geometry section inside dndGenerateRoom()
- adds weighted room archetypes with distinct geometry/content flavor

Desktop changes:
- adds dependency-free Linux joystick support through /dev/input/js*
- maps joystick/hat X/Y to LEFT/RIGHT/UP/DOWN
- maps button 0 -> A and button 1 -> B
- emits the existing KEY <name> serial protocol, so keyboard/clicks/gamepad all share one path

The physical Happy Jarz six-touch D-pad+A/B remains untouched and works offline.
"""
from pathlib import Path
import sys

FW_MARKER = "// BLOOM_DND_ROOM_ARCHETYPES_V1"
DESKTOP_MARKER = "# BLOOMPETZ_LINUX_GAMEPAD_V1"

STYLE_DECLS = r'''// BLOOM_DND_ROOM_ARCHETYPES_V1
enum DndRoomStyle : uint8_t {
  DND_ROOM_RUINS=0,
  DND_ROOM_HALL,
  DND_ROOM_CORRIDORS,
  DND_ROOM_CHAMBERS,
  DND_ROOM_TRAP_RUN,
  DND_ROOM_TREASURE,
  DND_ROOM_DEN,
  DND_ROOM_VOID
};
static DndRoomStyle dndRoomStyle = DND_ROOM_RUINS;
static const char* const DND_ROOM_STYLE_NAMES[8] = {
  "RUINS", "HALL", "CORRIDORS", "CHAMBERS",
  "TRAP RUN", "TREASURE", "DEN", "VOID"
};
'''

GEOMETRY = r'''  // BLOOM_DND_ROOM_ARCHETYPES_V1
  // Weighted room personality. Geometry changes; the existing door generator,
  // depth scaling, enemy spawning, loot generation, and camera continue below.
  uint8_t styleRoll = (uint8_t)random(100);
  if      (styleRoll < 24) dndRoomStyle = DND_ROOM_RUINS;
  else if (styleRoll < 40) dndRoomStyle = DND_ROOM_HALL;
  else if (styleRoll < 55) dndRoomStyle = DND_ROOM_CORRIDORS;
  else if (styleRoll < 69) dndRoomStyle = DND_ROOM_CHAMBERS;
  else if (styleRoll < 80) dndRoomStyle = DND_ROOM_TRAP_RUN;
  else if (styleRoll < 89) dndRoomStyle = DND_ROOM_TREASURE;
  else if (styleRoll < 96) dndRoomStyle = DND_ROOM_DEN;
  else                     dndRoomStyle = DND_ROOM_VOID;

  if (dndRoomStyle == DND_ROOM_RUINS) {
    // Broken short wall scars, close to the original generator but less uniform.
    uint8_t scars = (uint8_t)(8 + random(8));
    for (uint8_t i=0; i<scars; ++i) {
      int x = (int)random(2, DND_ROOM_W-2);
      int y = (int)random(2, DND_ROOM_H-2);
      bool horiz = random(2) == 0;
      int len = (int)random(2, 6);
      for (int j=0; j<len; ++j) {
        int xx = x + (horiz ? j : 0);
        int yy = y + (horiz ? 0 : j);
        if (xx>0 && xx<DND_ROOM_W-1 && yy>0 && yy<DND_ROOM_H-1) dndMap[yy][xx] = '#';
      }
    }
  }
  else if (dndRoomStyle == DND_ROOM_HALL) {
    // Broad open hall with deliberate pillars.
    for (int y=3; y<DND_ROOM_H-2; y+=4) {
      for (int x=4; x<DND_ROOM_W-3; x+=6) {
        if (random(100) < 78) dndMap[y][x] = '#';
      }
    }
  }
  else if (dndRoomStyle == DND_ROOM_CORRIDORS) {
    // Three long broken walls create lanes without becoming a hard maze.
    const int xs[3] = {7, 15, 23};
    for (uint8_t k=0; k<3; ++k) {
      int x = xs[k];
      int gap1 = 3 + (int)random(3);
      int gap2 = 9 + (int)random(4);
      for (int y=1; y<DND_ROOM_H-1; ++y) {
        if (y != gap1 && y != gap1+1 && y != gap2 && y != gap2+1) dndMap[y][x] = '#';
      }
    }
  }
  else if (dndRoomStyle == DND_ROOM_CHAMBERS) {
    // A cross divides the floor into four chambers; several doorways keep it connected.
    int mx = DND_ROOM_W/2;
    int my = DND_ROOM_H/2;
    for (int y=1; y<DND_ROOM_H-1; ++y) dndMap[y][mx] = '#';
    for (int x=1; x<DND_ROOM_W-1; ++x) dndMap[my][x] = '#';
    dndMap[3][mx]='.'; dndMap[4][mx]='.';
    dndMap[DND_ROOM_H-4][mx]='.'; dndMap[DND_ROOM_H-5][mx]='.';
    dndMap[my][6]='.'; dndMap[my][7]='.';
    dndMap[my][DND_ROOM_W-7]='.'; dndMap[my][DND_ROOM_W-8]='.';
  }
  else if (dndRoomStyle == DND_ROOM_TRAP_RUN) {
    // Open lanes with alternating barricades and extra depth-scaled trap tiles.
    for (int y=3; y<DND_ROOM_H-2; y+=3) {
      bool fromLeft = ((y/3) & 1) == 0;
      if (fromLeft) {
        for (int x=2; x<DND_ROOM_W-8; ++x) dndMap[y][x] = '#';
      } else {
        for (int x=8; x<DND_ROOM_W-2; ++x) dndMap[y][x] = '#';
      }
    }
    for (uint8_t i=0; i<10; ++i) {
      int tx=(int)random(2,DND_ROOM_W-2), ty=(int)random(2,DND_ROOM_H-2);
      if (dndMap[ty][tx]=='.') dndMap[ty][tx]='^';
    }
  }
  else if (dndRoomStyle == DND_ROOM_TREASURE) {
    // Central vault with four entrances and guaranteed visible treasure flavor.
    int x0=9, x1=20, y0=4, y1=11;
    for (int x=x0; x<=x1; ++x) { dndMap[y0][x]='#'; dndMap[y1][x]='#'; }
    for (int y=y0; y<=y1; ++y) { dndMap[y][x0]='#'; dndMap[y][x1]='#'; }
    dndMap[y0][14]='.'; dndMap[y1][15]='.'; dndMap[7][x0]='.'; dndMap[8][x1]='.';
    dndMap[6][13]='c'; dndMap[9][16]='c'; dndMap[7][16]='$'; dndMap[9][13]='w';
  }
  else if (dndRoomStyle == DND_ROOM_DEN) {
    // Arena/ring room; good for enemy-heavy encounters from the existing spawner.
    int x0=6, x1=23, y0=3, y1=12;
    for (int x=x0; x<=x1; ++x) { dndMap[y0][x]='#'; dndMap[y1][x]='#'; }
    for (int y=y0; y<=y1; ++y) { dndMap[y][x0]='#'; dndMap[y][x1]='#'; }
    dndMap[y0][14]='.'; dndMap[y1][15]='.'; dndMap[7][x0]='.'; dndMap[8][x1]='.';
    for (uint8_t i=0; i<4; ++i) {
      int tx=(int)random(8,22), ty=(int)random(5,11);
      if (dndMap[ty][tx]=='.') dndMap[ty][tx]='^';
    }
  }
  else {
    // VOID: eerie mostly-open floor with isolated 2x2 islands.
    for (int y=3; y<DND_ROOM_H-3; y+=5) {
      for (int x=4; x<DND_ROOM_W-4; x+=7) {
        if (random(100) < 70) {
          dndMap[y][x]='#'; dndMap[y][x+1]='#';
          dndMap[y+1][x]='#'; dndMap[y+1][x+1]='#';
        }
      }
    }
  }

  // Never let personality geometry spawn the player inside a wall/object.
  // Keep a small local breathing zone; the guaranteed-exit patch below will then
  // carve at least one complete route from this zone to a one-way + door.
  for (int dy=-1; dy<=1; ++dy) {
    for (int dx=-1; dx<=1; ++dx) {
      int xx=dndPlayerX+dx, yy=dndPlayerY+dy;
      if (xx>0 && xx<DND_ROOM_W-1 && yy>0 && yy<DND_ROOM_H-1) dndMap[yy][xx]='.';
    }
  }
  dndQueue(String("ROOM ") + String(dndRoomNumber) + " " + DND_ROOM_STYLE_NAMES[(uint8_t)dndRoomStyle]);

'''

GAMEPAD_METHODS = r'''    # BLOOMPETZ_LINUX_GAMEPAD_V1
    def _gamepad_worker(self):
        """Read Linux joystick API devices and feed the existing KEY protocol.

        No pygame/evdev dependency is needed. Most USB/Bluetooth controllers expose
        /dev/input/js0. Axes 0/1 are the left stick; axes 6/7 commonly carry the
        D-pad/hat. Button 0 maps to A and button 1 maps to B.
        """
        axis_state = {}
        while self.running:
            devices = sorted(glob.glob("/dev/input/js*"))
            if not devices:
                time.sleep(0.75)
                continue
            dev = devices[0]
            fd = None
            try:
                fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
                axis_state.clear()
                while self.running and os.path.exists(dev):
                    try:
                        packet = os.read(fd, 8)
                    except BlockingIOError:
                        time.sleep(0.01)
                        continue
                    except OSError:
                        break
                    if len(packet) != 8:
                        time.sleep(0.01)
                        continue
                    _ms, value, etype, number = struct.unpack("IhBB", packet)
                    etype &= ~0x80  # strip JS_EVENT_INIT
                    if etype == 0x01:  # button
                        if value:
                            if number == 0:
                                self.send("KEY A")
                            elif number == 1:
                                self.send("KEY B")
                    elif etype == 0x02 and number in (0, 1, 6, 7):  # axis/hat
                        pos = -1 if value < -16000 else (1 if value > 16000 else 0)
                        old = axis_state.get(number, 0)
                        axis_state[number] = pos
                        if pos == 0 or pos == old:
                            continue
                        if number in (0, 6):
                            self.send("KEY LEFT" if pos < 0 else "KEY RIGHT")
                        else:
                            self.send("KEY UP" if pos < 0 else "KEY DOWN")
            except OSError:
                time.sleep(0.75)
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            time.sleep(0.35)

'''


def fail(msg: str):
    raise SystemExit(msg)


def patch_firmware(path: Path):
    s = path.read_text()
    if FW_MARKER in s:
        print("DND room archetypes already applied.")
        return
    required = [
        "// BLOOM_DND_INFINITE_ROOMS_DEPTH_V1",
        "// BLOOM_DND_GUARANTEED_EXIT_V1",
        "static constexpr uint8_t DND_ROOM_W = 30;",
        "static constexpr uint8_t DND_ROOM_H = 16;",
        "static void dndGenerateRoom(bool announce)",
        "static uint16_t dndDeepestRoom = 1;",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        fail("firmware missing live infinite-room anchors: " + ", ".join(missing))

    decl_anchor = "static uint16_t dndDeepestRoom = 1;\n"
    s = s.replace(decl_anchor, decl_anchor + STYLE_DECLS, 1)

    start_marker = "  // Scatter short wall scars/pillars while keeping a generous open-room feel."
    end_marker = "  // BLOOM_DND_GUARANTEED_EXIT_V1"
    a = s.find(start_marker)
    b = s.find(end_marker, a + 1)
    if a < 0 or b < 0 or b <= a:
        fail("could not locate the proven geometry section; refusing to guess")
    s = s[:a] + GEOMETRY + s[b:]

    backup = path.with_suffix(path.suffix + ".pre_room_personality")
    if not backup.exists():
        backup.write_text(path.read_text())
    path.write_text(s)
    print(f"DND room archetypes applied: {path}")
    print("Styles: RUINS / HALL / CORRIDORS / CHAMBERS / TRAP RUN / TREASURE / DEN / VOID")


def patch_desktop(path: Path):
    s = path.read_text()
    if DESKTOP_MARKER in s:
        print("Linux gamepad support already applied.")
        return
    for anchor in ("class BloomPetzMini", "def send(self, command: str):", "threading.Thread(target=self._serial_worker, daemon=True).start()"):
        if anchor not in s:
            fail(f"desktop Mini missing anchor {anchor!r}; refusing to guess")

    if "import struct\n" not in s:
        if "import subprocess\n" in s:
            s = s.replace("import subprocess\n", "import subprocess\nimport struct\n", 1)
        else:
            fail("desktop import anchor missing")

    serial_thread = "        threading.Thread(target=self._serial_worker, daemon=True).start()\n"
    gamepad_thread = serial_thread + "        threading.Thread(target=self._gamepad_worker, daemon=True).start()  # BLOOMPETZ_LINUX_GAMEPAD_V1\n"
    s = s.replace(serial_thread, gamepad_thread, 1)

    send_anchor = "    def send(self, command: str):\n"
    s = s.replace(send_anchor, GAMEPAD_METHODS + send_anchor, 1)

    backup = path.with_suffix(path.suffix + ".pre_gamepad")
    if not backup.exists():
        backup.write_text(path.read_text())
    path.write_text(s)
    print(f"Linux USB/Bluetooth gamepad support applied: {path}")
    print("Mapping: stick/hat -> D-pad; button 0 -> A; button 1 -> B")


def main():
    if len(sys.argv) != 2:
        fail("usage: patch_dnd_room_personality_gamepad.py <bloompetz_v0_1.ino>")
    fw = Path(sys.argv[1]).expanduser().resolve()
    if not fw.exists():
        fail(f"firmware not found: {fw}")

    # Expected live layout: .../BloomPetz/firmware/bloompetz_v0_1/bloompetz_v0_1.ino
    bloompetz = fw.parents[2]
    desktop = bloompetz / "desktop" / "bloompetz_mini.py"
    if not desktop.exists():
        fail(f"desktop Mini not found: {desktop}")

    patch_firmware(fw)
    patch_desktop(desktop)
    print("Patch complete. Compile firmware before flashing, then restart Mini.")


if __name__ == "__main__":
    main()
