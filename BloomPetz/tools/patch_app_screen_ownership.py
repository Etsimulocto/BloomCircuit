#!/usr/bin/env python3
"""Enforce hard screen ownership between BLOOM SYSTEM, BloomPetz, and DND.

This is a defensive UI isolation patch for the current locally-patched firmware.
It prevents stale timers/services from repainting another app's screen.

Rules:
- drawHome() may draw only while uiMode == HOME
- drawStartupSlotPicker() may draw only while uiMode == SLOT_PICKER
- drawBloomSystemMenu() may draw only while uiMode == SYSTEM_MENU
- dndRenderFull() may draw only while uiMode == DND_PLACEHOLDER

The patch is intentionally renderer-level rather than trying to guess which old
service/ticker is still firing. A stale service can run, but it cannot steal the OLED.
"""
from pathlib import Path
import sys

MARKER = "// BLOOM_APP_SCREEN_OWNERSHIP_V1"


def guard_function(s: str, signature: str, guard: str, label: str):
    pos = s.find(signature)
    if pos < 0:
        print(f"skip: {label} not found")
        return s, False
    brace = s.find('{', pos)
    if brace < 0:
        raise SystemExit(f"opening brace missing for {label}")
    line_end = s.find('\n', brace)
    if line_end < 0:
        raise SystemExit(f"newline missing after {label} opening brace")
    look = s[line_end + 1: line_end + 220]
    if guard in look:
        print(f"already guarded: {label}")
        return s, False
    insert = f"  {MARKER}\n  {guard}\n"
    s = s[:line_end + 1] + insert + s[line_end + 1:]
    print(f"guarded: {label}")
    return s, True


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_app_screen_ownership.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"firmware not found: {p}")
    s = p.read_text()

    required = ["enum UiMode", "SYSTEM_MENU", "DND_PLACEHOLDER", "static void drawHome()"]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("required anchors missing: " + ", ".join(missing))

    changed = False
    for sig, guard, label in [
        ("static void drawHome()", "if (uiMode != HOME) return;", "BloomPetz HOME"),
        ("static void drawStartupSlotPicker()", "if (uiMode != SLOT_PICKER) return;", "BloomPetz slot picker"),
        ("static void drawBloomSystemMenu()", "if (uiMode != SYSTEM_MENU) return;", "BLOOM SYSTEM launcher"),
        ("static void dndRenderFull(", "if (uiMode != DND_PLACEHOLDER) return;", "DND full-width renderer"),
    ]:
        s, did = guard_function(s, sig, guard, label)
        changed = changed or did

    if not changed and MARKER in s:
        print("Screen ownership patch already applied.")
        return

    p.write_text(s)
    print(f"Hard app screen ownership applied: {p}")
    print("SYSTEM / PETZ / DND can no longer repaint each other's active screen.")


if __name__ == "__main__":
    main()
