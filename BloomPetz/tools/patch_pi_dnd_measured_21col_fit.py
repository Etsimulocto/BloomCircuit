#!/usr/bin/env python3
"""Fit all 21 DND mirror columns to the Pi Mini width using Tk font measurement.

Why this exists:
The previous DND width patch guessed DejaVu Sans Mono 12 bold would fit 21
characters inside the 192px Mini window. On the Raspberry Pi's actual Tk/font
rendering it is wider than 192px, so the rightmost ~2 characters are clipped.
That makes a 14-column OLED map appear as only ~12 columns in the Pi app.

This patch changes ONLY desktop/bloompetz_mini.py:
- imports tkinter.font
- replaces fixed DND_FONT with a runtime-measured font
- chooses the largest bold DejaVu Sans Mono size whose 21 M characters fit
  inside SCREEN_W with a 2px safety margin
- preserves the exact same 21-character serial content and DND geometry

No firmware compile or flash is required.
"""
from pathlib import Path
import sys

MARKER = "# BLOOMPETZ_DND_MEASURED_FIT_V1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"missing expected {label}; refusing to guess")
    return s.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_pi_dnd_measured_21col_fit.py <bloompetz_v0_1.ino>")

    fw = Path(sys.argv[1]).expanduser().resolve()
    if not fw.exists():
        raise SystemExit(f"firmware not found: {fw}")
    desktop = fw.parents[2] / "desktop" / "bloompetz_mini.py"
    if not desktop.exists():
        raise SystemExit(f"desktop app not found: {desktop}")

    s = desktop.read_text()
    if MARKER in s:
        print("Pi DND measured-fit patch already applied.")
        return

    required = [
        'import tkinter as tk',
        'DND_FONT = ("DejaVu Sans Mono", 12, "bold")',
        'def _apply_screen_font(self):',
        'MIRROR_COLS = 21',
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("desktop anchors missing: " + ", ".join(missing))

    s = replace_once(
        s,
        'import tkinter as tk\n',
        'import tkinter as tk\nimport tkinter.font as tkfont\n',
        "tkinter import",
    )

    s = replace_once(
        s,
        'DND_FONT = ("DejaVu Sans Mono", 12, "bold")\n# BLOOMPETZ_DND_FILL_WIDTH_V1\n',
        '# BLOOMPETZ_DND_FILL_WIDTH_V1\n' + MARKER + '\n',
        "fixed DND font constant",
    )

    old = '''    def _apply_screen_font(self):
        font = DND_FONT if self.dnd_mode else FONT
        for label in self.line_labels:
            label.configure(font=font)

'''
    new = '''    def _dnd_font_for_width(self):
        """Largest local mono font that truly fits all 21 DND columns."""
        usable = SCREEN_W - 2
        best = ("DejaVu Sans Mono", 8, "bold")
        # Measure the widest representative 21-char mono row on THIS Pi/Tk.
        sample = "M" * MIRROR_COLS
        for size in range(8, 17):
            f = tkfont.Font(family="DejaVu Sans Mono", size=size, weight="bold")
            if f.measure(sample) <= usable:
                best = ("DejaVu Sans Mono", size, "bold")
            else:
                break
        return best

    def _apply_screen_font(self):
        font = self._dnd_font_for_width() if self.dnd_mode else FONT
        for label in self.line_labels:
            label.configure(font=font)

'''
    s = replace_once(s, old, new, "screen font helper")

    desktop.write_text(s)
    print(f"Pi Mini DND font now measured to fit all 21 columns: {desktop}")
    print("No firmware flash needed; restart BloomPetz Mini only.")


if __name__ == "__main__":
    main()
