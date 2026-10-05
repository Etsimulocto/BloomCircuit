#!/usr/bin/env python3
"""Expand DND to 7 HUD + 14 map columns and polish BloomPetz Mini DND layout/theme.

Targets the current locally evolved firmware plus the consolidated BloomPetz Mini V3.

Firmware changes:
- DND_MAP_W 12 -> 14
- DND_HUD_W 9 -> 7
- starter room widened to 14 real map cells
- keeps total OLED width at 21 chars (7 + 14)

Desktop changes:
- DND rows left-anchor at x=0 instead of remaining centered
- normal BLOOM SYSTEM/BloomPetz rows restore centered layout
- controller panel/buttons use the current app foreground/background theme
- D-pad uses bg with fg text/trim; A/B use the inverse pair
- theme changes immediately recolor the controller

No other firmware/game behavior is changed.
"""
from pathlib import Path
import re
import sys

MARKER_FW = "// BLOOM_DND_14COL_MAP_V1"
MARKER_APP = "# BLOOMPETZ_DND_LEFT_THEME_CONTROLS_V1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"missing expected {label}; refusing to guess")
    return s.replace(old, new, 1)


def patch_firmware(p: Path) -> None:
    s = p.read_text()
    if MARKER_FW in s:
        print("Firmware 14-column DND patch already applied.")
        return

    required = [
        "static constexpr uint8_t DND_MAP_W = 12;",
        "static constexpr uint8_t DND_HUD_W = 9;",
        '"############"',
        '"#..c...^...#"',
        '"#....+....!#"',
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("live firmware anchors missing: " + ", ".join(missing))

    s = replace_once(
        s,
        "static constexpr uint8_t DND_MAP_W = 12;",
        f"{MARKER_FW}\nstatic constexpr uint8_t DND_MAP_W = 14;",
        "DND_MAP_W",
    )
    s = replace_once(s, "static constexpr uint8_t DND_HUD_W = 9;",
                     "static constexpr uint8_t DND_HUD_W = 7;", "DND_HUD_W")

    # Widen the actual starter room, not merely the buffer.
    s = replace_once(s, '"############",', '"##############",', "starter row 0")
    s = replace_once(s, '"#..c...^...#",', '"#..c...^.....#",', "starter row 1")
    s = replace_once(s, '"#....+....!#",', '"#....+......!#",', "starter row 2")
    # Last wall row is a second identical literal. Replace the next remaining 12-wall row.
    s = replace_once(s, '"############"', '"##############"', "starter row 3")

    # Spread the two larger enemies into the new columns while keeping rat unchanged.
    s = s.replace('dndEnemies[1] = {\'g\', "GOBLIN",   8, 1,',
                  'dndEnemies[1] = {\'g\', "GOBLIN",  10, 1,', 1)
    s = s.replace('dndEnemies[2] = {\'s\', "SKELETON", 9, 2,',
                  'dndEnemies[2] = {\'s\', "SKELETON",11, 2,', 1)

    p.write_text(s)
    print(f"DND geometry updated: {p}")
    print("OLED allocation is now 7 HUD + 14 MAP = 21 columns.")


def patch_desktop(p: Path) -> None:
    s = p.read_text()
    if MARKER_APP in s:
        print("Desktop DND left/theme patch already applied.")
        return

    required = [
        "class BloomPetzMini(tk.Tk):",
        "def _set_dnd_mode(self, enabled: bool):",
        "def _apply_theme(self):",
        'self.btn_up = add_btn("↑","UP",40,1)',
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("desktop V3 anchors missing: " + ", ".join(missing))

    # Stamp marker after MIRROR_COLS so this remains easy to detect.
    s = replace_once(s, "MIRROR_COLS = 21\n", "MIRROR_COLS = 21\n" + MARKER_APP + "\n",
                     "MIRROR_COLS marker")

    # Remember all six buttons as a group and theme them immediately.
    button_anchor = '        self.btn_b = add_btn("B","B",161,30,28,28)\n'
    button_extra = '''        self.btn_b = add_btn("B","B",161,30,28,28)\n        self.controller_buttons = [\n            self.btn_up, self.btn_down, self.btn_left, self.btn_right, self.btn_a, self.btn_b\n        ]\n        self._apply_controller_theme()\n'''
    s = replace_once(s, button_anchor, button_extra, "controller button block")

    # Add a single controller-theme helper before side-art drawing.
    anchor = "    def _draw_particle(self, canvas, p):\n"
    helper = '''    def _apply_controller_theme(self):\n        if not hasattr(self, "controller_buttons"):\n            return\n        self.controls.configure(bg=self.bg_color)\n        # D-pad: normal app pairing. A/B: inverse pairing for visual grouping.\n        for b in (self.btn_up, self.btn_down, self.btn_left, self.btn_right):\n            b.configure(\n                bg=self.bg_color, fg=self.text_color,\n                activebackground=self.text_color, activeforeground=self.bg_color,\n                highlightbackground=self.text_color, highlightcolor=self.text_color,\n                highlightthickness=2, bd=1, relief="raised"\n            )\n        for b in (self.btn_a, self.btn_b):\n            b.configure(\n                bg=self.text_color, fg=self.bg_color,\n                activebackground=self.bg_color, activeforeground=self.text_color,\n                highlightbackground=self.text_color, highlightcolor=self.text_color,\n                highlightthickness=2, bd=1, relief="raised"\n            )\n\n'''
    s = replace_once(s, anchor, helper + anchor, "controller theme helper anchor")

    # Replace DND mode switch so DND text truly starts at the left edge.
    old_mode = '''    def _set_dnd_mode(self, enabled: bool):\n        enabled = bool(enabled)\n        if enabled == self.dnd_mode: return\n        self.dnd_mode = enabled\n        if enabled:\n            self.left_art.place_forget(); self.right_art.place_forget()\n            self.title_label.configure(text="")\n        else:\n            self.left_art.place(x=0,y=0); self.right_art.place(x=SCREEN_W-SIDE_W,y=0)\n            self.title_label.configure(text=self.pet_name)\n            self._draw_side_art()\n'''
    new_mode = '''    def _set_dnd_mode(self, enabled: bool):\n        enabled = bool(enabled)\n        if enabled == self.dnd_mode:\n            return\n        self.dnd_mode = enabled\n        if enabled:\n            self.left_art.place_forget()\n            self.right_art.place_forget()\n            self.title_label.configure(text="")\n            # DND owns the full mirror width: start every row at x=0.\n            for i, label in enumerate(self.line_labels):\n                label.place_forget()\n                label.place(x=0, rely=(i+0.5)/4.0, anchor="w")\n        else:\n            self.left_art.place(x=0,y=0)\n            self.right_art.place(x=SCREEN_W-SIDE_W,y=0)\n            self.title_label.configure(text=self.pet_name)\n            for i, label in enumerate(self.line_labels):\n                label.place_forget()\n                label.place(relx=0.5, rely=(i+0.5)/4.0, anchor="center")\n            self._draw_side_art()\n'''
    s = replace_once(s, old_mode, new_mode, "DND layout switch")

    # Recolor controls whenever the user picks a new two-color theme.
    old_apply = '''    def _apply_theme(self):\n        self.screen.configure(bg=self.bg_color); self.color_label.configure(fg=self.text_color)\n        for label in self.line_labels: label.configure(fg=self.text_color,bg=self.bg_color)\n        self._draw_side_art()\n'''
    new_apply = '''    def _apply_theme(self):\n        self.screen.configure(bg=self.bg_color)\n        self.color_label.configure(fg=self.text_color)\n        for label in self.line_labels:\n            label.configure(fg=self.text_color,bg=self.bg_color)\n        self._apply_controller_theme()\n        self._draw_side_art()\n'''
    s = replace_once(s, old_apply, new_apply, "theme apply method")

    p.write_text(s)
    print(f"Pi Mini DND layout/controller theme updated: {p}")
    print("DND rows now anchor at x=0; controls track the app's two-color theme.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_dnd_14col_map_theme_controls.py <bloompetz_v0_1.ino>")
    fw = Path(sys.argv[1]).expanduser().resolve()
    if not fw.exists():
        raise SystemExit(f"firmware not found: {fw}")
    desktop = fw.parents[2] / "desktop" / "bloompetz_mini.py"
    if not desktop.exists():
        raise SystemExit(f"desktop app not found: {desktop}")
    patch_firmware(fw)
    patch_desktop(desktop)
    print("Ready: compile/flash firmware, then restart BloomPetz Mini.")


if __name__ == "__main__":
    main()
