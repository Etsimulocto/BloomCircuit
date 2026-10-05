#!/usr/bin/env python3
"""Stop BLOOM SYSTEM/startup repainting over the full-width DND screen.

Targets local firmware after:
- patch_dnd_playable_v0_1.py
- patch_dnd_fullwidth_hud.py

The DND game intentionally owns the OLED while uiMode == DND_PLACEHOLDER.
The legacy startup/system service can still repaint the launcher if it continues
running, which causes the visible alternating narrow/full-width screen flicker.
This patch makes serviceStartupUi() immediately yield whenever DND owns the UI.
"""
from pathlib import Path
import sys

MARKER = "// BLOOM_DND_STOP_LAUNCHER_FLICKER_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_dnd_stop_launcher_flicker.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("DND launcher-flicker guard already applied.")
        return

    required = [
        "// BLOOM_DND_PLAYABLE_V0_1",
        "// BLOOM_DND_FULLWIDTH_HUD_V1",
        "static void serviceStartupUi() {",
        "DND_PLACEHOLDER",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required anchors missing: " + ", ".join(missing))

    old = "static void serviceStartupUi() {\n"
    new = (
        "static void serviceStartupUi() {\n"
        f"  {MARKER}\n"
        "  // DND has its own full-width renderer. Do not let the old launcher\n"
        "  // or startup UI repaint the OLED while the game is active.\n"
        "  if (uiMode == DND_PLACEHOLDER) return;\n"
    )

    if old not in s:
        raise SystemExit("Exact serviceStartupUi() opening not found; refusing to guess")

    s = s.replace(old, new, 1)
    p.write_text(s)

    print(f"DND screen ownership guard applied: {p}")
    print("While uiMode == DND_PLACEHOLDER, startup/system repainting is disabled.")


if __name__ == "__main__":
    main()
