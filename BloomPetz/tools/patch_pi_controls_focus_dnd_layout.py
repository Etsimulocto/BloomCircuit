#!/usr/bin/env python3
"""Polish BloomPetz Mini controls and DND layout after the 21-column mirror patch.

Targets the locally patched desktop/bloompetz_mini.py after
patch_pi_dnd_mirror_controls.py.

Changes:
- D-pad buttons display arrow glyphs instead of UP/DOWN/LEFT/RIGHT words.
- Enlarges/re-spaces controller buttons.
- Adds WASD alongside arrow-key controls.
- Automatically focuses the Mini when the pointer enters the app, so keyboard
  control works without first clicking a tiny text/control element.
- Detects DND from mirrored 21-column frames and hides BloomPetz side-art lanes
  while DND is active; restores them automatically for normal BloomPetz/System.
- Keeps the existing KEY UP/DOWN/LEFT/RIGHT/A/B serial protocol unchanged.

This patch only edits the desktop app. No firmware flash is required.
"""
from pathlib import Path
import re
import sys

MARKER = "# BLOOMPETZ_PI_CONTROL_LAYOUT_V2"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_pi_controls_focus_dnd_layout.py <bloompetz_v0_1.ino>")

    fw = Path(sys.argv[1]).expanduser().resolve()
    if not fw.exists():
        raise SystemExit(f"firmware not found: {fw}")
    desktop = fw.parents[2] / "desktop" / "bloompetz_mini.py"
    if not desktop.exists():
        raise SystemExit(f"desktop app not found: {desktop}")

    s = desktop.read_text()
    if MARKER in s:
        print("Pi control/layout V2 already applied.")
        return

    required = [
        "# BLOOMPETZ_DND_CONTROLS_V1",
        "MIRROR_COLS = 21",
        "def _button_key(self, key: str):",
        "self.btn_up = add_btn",
        "def _handle_line(self, line: str):",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("required patched-app anchors missing: " + ", ".join(missing))

    # Stamp marker beside existing controller constants.
    anchor = "MIRROR_COLS = 21\n"
    s = s.replace(anchor, anchor + MARKER + "\n", 1)

    # Track current app display mode.
    anchor = "        self.pet_name = \"NO PET\"\n"
    if anchor not in s:
        raise SystemExit("pet_name state anchor missing")
    s = s.replace(anchor, anchor + "        self.dnd_mode = False\n", 1)

    # Replace the compact controller placements with clearer arrow controls.
    replacements = {
        'self.btn_up = add_btn("UP", "UP", 38, 2)': 'self.btn_up = add_btn("↑", "UP", 40, 1, 38, 28)',
        'self.btn_left = add_btn("LEFT", "LEFT", 4, 28)': 'self.btn_left = add_btn("←", "LEFT", 1, 30, 38, 28)',
        'self.btn_down = add_btn("DOWN", "DOWN", 38, 28)': 'self.btn_down = add_btn("↓", "DOWN", 40, 30, 38, 28)',
        'self.btn_right = add_btn("RIGHT", "RIGHT", 72, 28)': 'self.btn_right = add_btn("→", "RIGHT", 79, 30, 38, 28)',
        'self.btn_a = add_btn("A", "A", 124, 8, 28, 28)': 'self.btn_a = add_btn("A", "A", 128, 5, 28, 28)',
        'self.btn_b = add_btn("B", "B", 158, 25, 28, 28)': 'self.btn_b = add_btn("B", "B", 161, 27, 28, 28)',
    }
    for old, new in replacements.items():
        if old not in s:
            raise SystemExit(f"controller placement anchor missing: {old}")
        s = s.replace(old, new, 1)

    # Make button glyphs slightly larger and easier to hit/read.
    s = s.replace('font=("DejaVu Sans", 8, "bold"), bd=1, relief="raised",',
                  'font=("DejaVu Sans", 11, "bold"), bd=1, relief="raised",', 1)

    # Add WASD while retaining arrows + A/B. Use lowercase keysyms to avoid
    # duplicate Shift variants; physical A/B remain game actions.
    old_mapping = '''        mapping = {
            "Up":"UP", "Down":"DOWN", "Left":"LEFT", "Right":"RIGHT",
            "a":"A", "A":"A", "b":"B", "B":"B"
        }
'''
    new_mapping = '''        mapping = {
            "Up":"UP", "Down":"DOWN", "Left":"LEFT", "Right":"RIGHT",
            "w":"UP", "s":"DOWN", "a":"LEFT", "d":"RIGHT",
            "q":"A", "e":"B",
            "space":"A", "Return":"A", "BackSpace":"B"
        }
'''
    if old_mapping not in s:
        raise SystemExit("keyboard mapping block missing")
    s = s.replace(old_mapping, new_mapping, 1)

    # Hover-to-focus makes the small controller act like a game surface. This
    # cannot intercept keys while another application is intentionally focused,
    # but moving the pointer over Mini immediately gives it keyboard control.
    bind_anchor = "        self._bind_keys()\n"
    if bind_anchor not in s:
        raise SystemExit("_bind_keys call anchor missing")
    s = s.replace(bind_anchor,
                  bind_anchor + '        self.bind_all("<Enter>", self._focus_on_enter, add="+")\n', 1)

    method_anchor = "    def _bind_keys(self):\n"
    if method_anchor not in s:
        raise SystemExit("_bind_keys method anchor missing")
    focus_method = '''    def _focus_on_enter(self, _event=None):
        try:
            self.focus_force()
        except Exception:
            pass

'''
    s = s.replace(method_anchor, focus_method + method_anchor, 1)

    # Add one layout switch. In DND the side canvases are hidden so the 21-char
    # mirrored rows own the whole 192px width. Normal BloomPetz/System restores
    # them automatically.
    handle_anchor = "    def _handle_line(self, line: str):\n"
    if handle_anchor not in s:
        raise SystemExit("_handle_line anchor missing")
    mode_method = '''    def _set_dnd_layout(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self.dnd_mode:
            return
        self.dnd_mode = enabled
        if enabled:
            self.left_art.place_forget()
            self.right_art.place_forget()
        else:
            self.left_art.place(x=0, y=0)
            self.right_art.place(x=SCREEN_W - SIDE_W, y=0)
            self._draw_side_art()

'''
    s = s.replace(handle_anchor, mode_method + handle_anchor, 1)

    # Replace BP|SCREEN parsing block so we can detect a true 21-column DND
    # frame BEFORE padding. Normal launcher/Petz rows are <=16 chars.
    old = '''        fields = self._fields(line)
        for i in range(4):
            text = fields.get(str(i+1), self.screen_lines[i])[:MIRROR_COLS].ljust(MIRROR_COLS)
            self.screen_lines[i] = text
            self.line_labels[i].configure(text=text)
'''
    new = '''        fields = self._fields(line)
        raw_rows = [fields.get(str(i+1), self.screen_lines[i]).rstrip() for i in range(4)]
        self._set_dnd_layout(any(len(row) > 16 for row in raw_rows))
        for i in range(4):
            text = raw_rows[i][:MIRROR_COLS].ljust(MIRROR_COLS)
            self.screen_lines[i] = text
            self.line_labels[i].configure(text=text)
'''
    if old not in s:
        raise SystemExit("21-column BP|SCREEN parser block missing")
    s = s.replace(old, new, 1)

    desktop.write_text(s)
    print(f"Pi Mini controls/layout V2 applied: {desktop}")
    print("D-pad labels: arrows; keyboard: arrows/WASD + Q/E (A/B actions); hover focuses Mini.")
    print("DND 21-column frames now hide Pi side-art automatically. No firmware flash needed.")


if __name__ == "__main__":
    main()
