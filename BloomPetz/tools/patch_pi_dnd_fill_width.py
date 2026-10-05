#!/usr/bin/env python3
"""Make Pi Mini DND visually fill the same width as the physical OLED.

The firmware already uses the full 21-character OLED width. The Pi Mini mirrors
those same 21 logical columns, but DejaVu Sans Mono 10 is too narrow for the
192px desktop canvas, leaving visible empty space on the right.

This patch changes ONLY the desktop app:
- adds a dedicated DND font sized to make 21 columns span the mirror width
- switches to that font while DND is active
- restores the normal BloomPetz font outside DND
- keeps the exact same 21-character content and serial protocol

No firmware compile/flash is required.
"""
from pathlib import Path
import sys

MARKER = "# BLOOMPETZ_DND_FILL_WIDTH_V1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"missing expected {label}; refusing to guess")
    return s.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_pi_dnd_fill_width.py <bloompetz_v0_1.ino>")

    fw = Path(sys.argv[1]).expanduser().resolve()
    if not fw.exists():
        raise SystemExit(f"firmware not found: {fw}")
    desktop = fw.parents[2] / "desktop" / "bloompetz_mini.py"
    if not desktop.exists():
        raise SystemExit(f"desktop app not found: {desktop}")

    s = desktop.read_text()
    if MARKER in s:
        print("Pi DND fill-width patch already applied.")
        return

    required = [
        'FONT = ("DejaVu Sans Mono", 10, "bold")',
        'def _set_dnd_mode(self, enabled: bool):',
        'self.line_labels',
        '# BLOOMPETZ_DND_LEFT_THEME_CONTROLS_V1',
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("desktop anchors missing: " + ", ".join(missing))

    # 21 columns at DejaVu Sans Mono 12 bold occupy almost the full 192px
    # mirror width on Raspberry Pi Tk. Keep the normal BloomPetz font unchanged.
    old = 'FONT = ("DejaVu Sans Mono", 10, "bold")\n'
    new = (
        'FONT = ("DejaVu Sans Mono", 10, "bold")\n'
        'DND_FONT = ("DejaVu Sans Mono", 12, "bold")\n'
        f'{MARKER}\n'
    )
    s = replace_once(s, old, new, "font constants")

    # Add a helper so mode switches control both geometry and font from one place.
    anchor = '    def _set_dnd_mode(self, enabled: bool):\n'
    helper = '''    def _apply_screen_font(self):\n        font = DND_FONT if self.dnd_mode else FONT\n        for label in self.line_labels:\n            label.configure(font=font)\n\n'''
    s = replace_once(s, anchor, helper + anchor, "DND mode method")

    # When DND mode changes, immediately apply the matching font.
    old = '''        self.dnd_mode = enabled\n        if enabled:\n'''
    new = '''        self.dnd_mode = enabled\n        self._apply_screen_font()\n        if enabled:\n'''
    s = replace_once(s, old, new, "DND mode assignment")

    desktop.write_text(s)
    print(f"Pi Mini DND now scales 21 columns to fill the mirror width: {desktop}")
    print("Firmware unchanged; restart BloomPetz Mini only.")


if __name__ == "__main__":
    main()
