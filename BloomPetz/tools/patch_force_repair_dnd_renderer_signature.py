#!/usr/bin/env python3
"""Force-repair the malformed dndRenderFull() signature caused by a guard inserted
inside the multiline parameter list.

This script targets the exact broken shape reported by the compiler and rewrites
only the function header/guard. It refuses to write unless exactly one malformed
renderer is found.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOM_DND_RENDERER_SIGNATURE_FORCE_REPAIR_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_force_repair_dnd_renderer_signature.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("DND renderer signature force-repair already applied.")
        return

    pat = re.compile(
        r"static void dndRenderFull\(const String &r0, const String &r1,\s*"
        r"(?://[^\n]*\n\s*)*"
        r"if \(uiMode != DND_PLACEHOLDER\) return;\s*"
        r"const String &r2, const String &r3\) \{",
        re.S,
    )

    matches = list(pat.finditer(s))
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one malformed dndRenderFull() header, found {len(matches)}; refusing to guess")

    replacement = (
        "static void dndRenderFull(const String &r0, const String &r1,\n"
        "                          const String &r2, const String &r3) {\n"
        f"  {MARKER}\n"
        "  if (uiMode != DND_PLACEHOLDER) return;"
    )

    s = pat.sub(replacement, s, count=1)

    # Sanity checks before writing.
    good = (
        "static void dndRenderFull(const String &r0, const String &r1,\n"
        "                          const String &r2, const String &r3) {"
    )
    if good not in s:
        raise SystemExit("Repair validation failed: correct four-argument signature not present")

    bad = re.search(
        r"static void dndRenderFull\([^\{]{0,300}if \(uiMode != DND_PLACEHOLDER\) return;[^\{]{0,300}\{",
        s,
        re.S,
    )
    if bad:
        raise SystemExit("Repair validation failed: a guard still appears inside the dndRenderFull parameter list")

    p.write_text(s)
    print(f"Force-repaired dndRenderFull() signature: {p}")
    print("Restored four String arguments and moved the DND ownership guard inside the function body.")


if __name__ == "__main__":
    main()
