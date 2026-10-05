#!/usr/bin/env python3
"""Repair a misplaced DND ownership guard inside the multiline dndRenderFull signature.

A previous screen-ownership repair inserted:

    if (uiMode != DND_PLACEHOLDER) return;

between the first and second parameter lines of dndRenderFull(), producing compile errors.
This script removes any misplaced ownership guard near that function signature and reinserts
it only after the function's opening brace.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOM_DND_RENDER_GUARD_REPAIR_V1"
OWN_MARKER = "// BLOOM_APP_SCREEN_OWNERSHIP_V1"
GUARD = "if (uiMode != DND_PLACEHOLDER) return;"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_repair_dnd_renderer_guard.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"firmware not found: {p}")

    s = p.read_text()

    start = s.find("static void dndRenderFull(")
    if start < 0:
        raise SystemExit("dndRenderFull() not found")

    # Bound the signature/body opening tightly so we only touch this function.
    brace = s.find("{", start)
    if brace < 0 or brace - start > 500:
        raise SystemExit("dndRenderFull() opening brace not found safely")

    sig = s[start:brace]

    # Remove misplaced ownership marker/guard pairs from inside the multiline signature.
    sig = re.sub(r"\n\s*// BLOOM_APP_SCREEN_OWNERSHIP_V1\s*\n\s*if \(uiMode != DND_PLACEHOLDER\) return;\s*", "\n", sig)
    sig = re.sub(r"\n\s*if \(uiMode != DND_PLACEHOLDER\) return;\s*", "\n", sig)
    s = s[:start] + sig + s[brace:]

    # Recompute brace after signature normalization.
    start = s.find("static void dndRenderFull(")
    brace = s.find("{", start)
    nl = s.find("\n", brace)
    if nl < 0:
        raise SystemExit("newline after dndRenderFull() opening brace not found")

    body_head = s[nl + 1:nl + 240]
    if GUARD not in body_head:
        ins = (
            f"  {MARKER}\n"
            f"  {OWN_MARKER}\n"
            f"  {GUARD}\n"
        )
        s = s[:nl + 1] + ins + s[nl + 1:]

    # Validate signature is syntactically shaped as 4 String refs before writing.
    check = re.search(
        r"static void dndRenderFull\(const String &r0, const String &r1,\s*"
        r"const String &r2, const String &r3\) \{",
        s,
        re.S,
    )
    if not check:
        raise SystemExit("dndRenderFull() signature is still malformed; refusing to write")

    # Also ensure no guard text remains between '(' and '{'.
    st = s.find("static void dndRenderFull(")
    br = s.find("{", st)
    if GUARD in s[st:br] or OWN_MARKER in s[st:br]:
        raise SystemExit("ownership guard still present inside dndRenderFull() signature")

    p.write_text(s)
    print(f"Repaired multiline dndRenderFull() guard placement: {p}")
    print("Validated 4-argument signature and guard only inside function body.")


if __name__ == "__main__":
    main()
