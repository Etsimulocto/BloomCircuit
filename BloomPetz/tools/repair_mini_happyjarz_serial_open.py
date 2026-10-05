#!/usr/bin/env python3
"""Make BloomPetz Mini use the known-good Happy Jarz serial-open pattern.

Desktop-only repair. Firmware is untouched.

Replaces BloomPetz Mini's explicit DTR/RTS manipulation around serial open with
the simple pyserial open used by the working Happy Jarz controller:

    serial.Serial(port, BAUD, timeout=..., write_timeout=...)

This avoids manually toggling USB CDC control lines when Mini attaches.
"""
from pathlib import Path
import re
import sys

MARKER = "# BLOOMPETZ_HAPPYJARZ_SERIAL_OPEN_V1"


def fail(msg: str):
    raise SystemExit(msg)


def main():
    if len(sys.argv) != 2:
        fail("usage: repair_mini_happyjarz_serial_open.py <bloompetz_mini.py>")

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        fail(f"Mini not found: {p}")

    original = p.read_text()
    s = original

    # Match either compact rebuilt form or typed form of _open_port().
    pat = re.compile(
        r"(?ms)^    def _open_port\(self,\s*port(?:\s*:\s*str)?\)(?:\s*->\s*serial\.Serial)?\s*:\n"
        r"(?P<body>(?:        .*\n)+?)"
        r"(?=^    def )"
    )
    m = pat.search(s)
    if not m:
        fail("could not locate _open_port() method")

    new_method = '''    def _open_port(self, port):\n        # BLOOMPETZ_HAPPYJARZ_SERIAL_OPEN_V1\n        # Match the proven Happy Jarz controller: simple pyserial open, no\n        # manual DTR/RTS toggling around USB CDC attach.\n        return serial.Serial(\n            port,\n            BAUD,\n            timeout=0.25,\n            write_timeout=0.25,\n        )\n\n'''

    s = s[:m.start()] + new_method + s[m.end():]

    # Add a file marker once, without disturbing shebang/future import ordering.
    if MARKER not in s:
        future = "from __future__ import annotations\n"
        if future in s:
            s = s.replace(future, future + "\n" + MARKER + "\n", 1)
        else:
            lines = s.splitlines(True)
            insert_at = 1 if lines and lines[0].startswith("#!") else 0
            lines.insert(insert_at, MARKER + "\n")
            s = "".join(lines)

    # Syntax-check before writing.
    try:
        compile(s, str(p), "exec")
    except SyntaxError as exc:
        fail(f"patched Mini failed Python syntax check: {exc}")

    backup = p.with_suffix(p.suffix + ".pre_happyjarz_serial_open")
    if not backup.exists():
        backup.write_text(original)
    p.write_text(s)

    print(f"Repaired Mini: {p}")
    print("serial open: Happy Jarz pattern (no manual DTR/RTS toggling)")
    print("Python syntax check: PASS")
    print("Firmware untouched; no compile/flash required.")


if __name__ == "__main__":
    main()
