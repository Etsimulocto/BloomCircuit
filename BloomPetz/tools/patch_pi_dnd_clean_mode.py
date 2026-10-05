#!/usr/bin/env python3
"""Clean BloomPetz Mini DND presentation and keyboard mapping.

Targets desktop/bloompetz_mini.py after the DND mirror/controller patches.

Changes:
- keyboard is ONLY arrows + A/B, matching the six physical controls
- DND mode hides both animated side-art lanes
- DND mode blanks the pet-name text in the header
- BLOOM SYSTEM / BloomPetz restore pet name + side art automatically
- DND detection is sticky until a BLOOM SYSTEM frame is seen, so short DND menu
  rows do not accidentally bring BloomPetz chrome back

Desktop-only patch. No firmware flash required.
"""
from pathlib import Path
import re
import sys

MARKER = "# BLOOMPETZ_PI_DND_CLEAN_MODE_V1"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_pi_dnd_clean_mode.py <bloompetz_v0_1.ino>")

    fw = Path(sys.argv[1]).expanduser().resolve()
    if not fw.exists():
        raise SystemExit(f"firmware not found: {fw}")
    desktop = fw.parents[2] / "desktop" / "bloompetz_mini.py"
    if not desktop.exists():
        raise SystemExit(f"desktop app not found: {desktop}")

    s = desktop.read_text()
    if MARKER in s:
        print("Pi DND clean mode already applied.")
        return

    required = [
        "MIRROR_COLS = 21",
        "def _bind_keys(self):",
        "def _set_dnd_layout(self, enabled: bool):",
        "def _handle_line(self, line: str):",
        "self.title_label.configure(text=self.pet_name)",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("required anchors missing: " + ", ".join(missing))

    # Stamp marker beside mirror constants.
    s = s.replace("MIRROR_COLS = 21\n", "MIRROR_COLS = 21\n" + MARKER + "\n", 1)

    # Replace whatever expanded keyboard mapping is present with the exact
    # six-control grammar: arrows for directions, A/B for actions.
    start = s.find("    def _bind_keys(self):")
    end = s.find("    def _key_press(self, key: str):", start)
    if start < 0 or end < 0:
        raise SystemExit("could not bound _bind_keys()")

    block = s[start:end]
    map_start = block.find("        mapping = {")
    loop_start = block.find("        for keysym, bpkey in mapping.items():")
    if map_start < 0 or loop_start < 0:
        raise SystemExit("keyboard mapping anchors missing")
    new_map = '''        mapping = {
            "Up": "UP",
            "Down": "DOWN",
            "Left": "LEFT",
            "Right": "RIGHT",
            "a": "A",
            "A": "A",
            "b": "B",
            "B": "B",
        }
'''
    block = block[:map_start] + new_map + block[loop_start:]
    s = s[:start] + block + s[end:]

    # Replace DND layout switch so DND strips BloomPetz chrome: no side art and
    # no pet name. Restore both when leaving DND.
    start = s.find("    def _set_dnd_layout(self, enabled: bool):")
    end = s.find("    def _handle_line(self, line: str):", start)
    if start < 0 or end < 0:
        raise SystemExit("could not bound _set_dnd_layout()")

    new_layout = '''    def _set_dnd_layout(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self.dnd_mode:
            # Keep header text correct even if STATUS arrives while DND is active.
            if enabled:
                self.title_label.configure(text="")
            return

        self.dnd_mode = enabled
        if enabled:
            self.left_art.place_forget()
            self.right_art.place_forget()
            self.title_label.configure(text="")
        else:
            self.left_art.place(x=0, y=0)
            self.right_art.place(x=SCREEN_W - SIDE_W, y=0)
            self.title_label.configure(text=self.pet_name)
            self._draw_side_art()

'''
    s = s[:start] + new_layout + s[end:]

    # STATUS updates should not reinsert the pet name while DND owns the screen.
    old = '            self.title_label.configure(text=self.pet_name)\n            return\n'
    new = '            self.title_label.configure(text="" if self.dnd_mode else self.pet_name)\n            return\n'
    if old not in s:
        raise SystemExit("STATUS title update anchor missing")
    s = s.replace(old, new, 1)

    # Strengthen screen-mode detection. A full 21-column frame enters DND.
    # Once entered, stay in DND even on short menu/info rows until BLOOM SYSTEM
    # is explicitly seen again.
    old = '''        fields = self._fields(line)
        raw_rows = [fields.get(str(i+1), self.screen_lines[i]).rstrip() for i in range(4)]
        self._set_dnd_layout(any(len(row) > 16 for row in raw_rows))
        for i in range(4):
'''
    new = '''        fields = self._fields(line)
        raw_rows = [fields.get(str(i+1), self.screen_lines[i]).rstrip() for i in range(4)]
        is_system = any("BLOOM SYSTEM" in row for row in raw_rows)
        has_full_dnd_row = any(len(row) > 16 for row in raw_rows)
        if is_system:
            self._set_dnd_layout(False)
        elif has_full_dnd_row:
            self._set_dnd_layout(True)
        for i in range(4):
'''
    if old not in s:
        raise SystemExit("DND screen detection block missing")
    s = s.replace(old, new, 1)

    # Do not waste cycles drawing hidden side art while DND is active.
    needle = '''    def _animate_side_art(self):
        if not self.running:
            return
'''
    repl = '''    def _animate_side_art(self):
        if not self.running:
            return
        if getattr(self, "dnd_mode", False):
            self.after(SIDE_TICK_MS, self._animate_side_art)
            return
'''
    if needle in s:
        s = s.replace(needle, repl, 1)

    desktop.write_text(s)
    print(f"Pi DND clean mode applied: {desktop}")
    print("DND: no side art, no pet-name header. System/Petz restore both.")
    print("Keyboard: arrows + A/B only. On-screen buttons remain arrows + A/B.")


if __name__ == "__main__":
    main()
