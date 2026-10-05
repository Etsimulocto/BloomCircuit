#!/usr/bin/env python3
"""Repair BLOOM app screen-ownership guards after prototype matching bug.

The original patch searched for signatures such as `static void drawHome()` and
could hit a forward declaration (`static void drawHome();`). It then found the
next opening brace, which could belong to an unrelated function such as
creatorMaxLen().

This repair:
1. removes every prior BLOOM_APP_SCREEN_OWNERSHIP_V1 marker + ownership guard pair,
2. inserts guards only after exact renderer definitions containing `{`,
3. validates that creatorMaxLen() contains no ownership guard.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOM_APP_SCREEN_OWNERSHIP_V1"
REPAIR_MARKER = "// BLOOM_APP_SCREEN_OWNERSHIP_REPAIR_V2"

GUARDS = [
    "if (uiMode != HOME) return;",
    "if (uiMode != SLOT_PICKER) return;",
    "if (uiMode != SYSTEM_MENU) return;",
    "if (uiMode != DND_PLACEHOLDER) return;",
]


def insert_exact(s: str, opening: str, guard: str, label: str) -> str:
    pos = s.find(opening)
    if pos < 0:
        raise SystemExit(f"Exact renderer definition not found for {label}: {opening}")
    line_end = s.find("\n", pos)
    if line_end < 0:
        raise SystemExit(f"No newline after renderer opening for {label}")
    nearby = s[line_end + 1:line_end + 240]
    if guard in nearby:
        print(f"already correct: {label}")
        return s
    insert = f"  {REPAIR_MARKER}\n  {guard}\n"
    s = s[:line_end + 1] + insert + s[line_end + 1:]
    print(f"repaired: {label}")
    return s


def function_body(s: str, opening: str) -> str:
    start = s.find(opening)
    if start < 0:
        return ""
    brace = s.find("{", start)
    depth = 0
    for i in range(brace, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return s[start:]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_repair_app_screen_ownership.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"firmware not found: {p}")
    s = p.read_text()

    # Remove marker+guard pairs from the buggy patch wherever they landed.
    pair = re.compile(
        r"^[ \t]*// BLOOM_APP_SCREEN_OWNERSHIP_V1[ \t]*\n"
        r"[ \t]*if \(uiMode != (?:HOME|SLOT_PICKER|SYSTEM_MENU|DND_PLACEHOLDER)\) return;[ \t]*\n",
        re.M,
    )
    s, removed = pair.subn("", s)
    print(f"removed {removed} old ownership guard pair(s)")

    # Also clean any orphaned ownership guards that immediately follow a repair marker
    # from a partially edited local file. Only exact known guard lines are considered.
    for guard in GUARDS:
        bad = f"  {MARKER}\n  {guard}\n"
        s = s.replace(bad, "")

    # Exact definitions only. The opening brace is part of the match so forward
    # declarations such as `static void drawHome();` cannot be selected.
    targets = [
        ("static void drawHome() {", "if (uiMode != HOME) return;", "BloomPetz HOME"),
        ("static void drawStartupSlotPicker() {", "if (uiMode != SLOT_PICKER) return;", "BloomPetz slot picker"),
        ("static void drawBloomSystemMenu() {", "if (uiMode != SYSTEM_MENU) return;", "BLOOM SYSTEM launcher"),
        ("static void dndRenderFull(const String &r0, const String &r1,", "if (uiMode != DND_PLACEHOLDER) return;", "DND full-width renderer"),
    ]

    for opening, guard, label in targets:
        s = insert_exact(s, opening, guard, label)

    # Safety validation for the exact compile failure we just saw.
    creator = function_body(s, "static uint8_t creatorMaxLen(uint8_t")
    if not creator:
        raise SystemExit("creatorMaxLen() not found during validation")
    for guard in GUARDS:
        if guard in creator:
            raise SystemExit(f"ownership guard still incorrectly present in creatorMaxLen(): {guard}")

    p.write_text(s)
    print(f"Screen ownership repaired safely: {p}")
    print("Validated: creatorMaxLen() has no ownership guard.")
    print("Renderer guards now target exact function definitions, never prototypes.")


if __name__ == "__main__":
    main()
