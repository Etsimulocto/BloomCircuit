#!/usr/bin/env python3
"""Move the HOME stat ticker from line 2 to line 3.

After patch_home_name_stat_ticker.py:
- Line 2 stays PET NAME at all times.
- Line 3 alternates every 10 seconds between the normal selected action line
  and the rotating canonical STAT NAME + 0.0000% ticker.
- Long stat text keeps the existing 350 ms marquee behavior.
- Leaves line 1 pet-art/saying ticker and line 4 status/control ticker alone.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_HOME_STATS_LINE3_V1"
OLD_MARKER = "// BLOOMPETZ_HOME_NAME_STAT_TICKER_V1"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_move_home_stats_to_line3.py <bloompetz_v0_1.ino>")

    ino = Path(sys.argv[1]).expanduser().resolve()
    s = ino.read_text()

    if MARKER in s:
        print("HOME stats already moved to line 3.")
        return
    if OLD_MARKER not in s:
        raise SystemExit("Existing HOME stat ticker patch not found; apply patch_home_name_stat_ticker.py first")

    # Rename the ticker helper for clarity and change its non-stat phase from
    # pet name to the normal HOME action text supplied by drawHome().
    s = s.replace("static String homeLine2Ticker(const PetSave &p) {", "static String homeLine3Ticker(const PetSave &p, const String &normalLine3) {", 1)
    s = s.replace("  if (!homeNameStatShowingStat) return String(p.name);", "  if (!homeNameStatShowingStat) return normalLine3;", 1)

    # Locate drawHome and rewrite only the occupied pet's final render call.
    dm = re.search(r"static void drawHome\(\) \{(?P<body>.*?)\n\}", s, re.S)
    if not dm:
        raise SystemExit("Could not isolate drawHome()")
    body = dm.group("body")
    renders = list(re.finditer(r"renderDisplay\(([^;]+)\);", body))
    if not renders:
        raise SystemExit("drawHome renderDisplay call not found")
    r = renders[-1]
    inner = r.group(1)
    parts = [x.strip() for x in inner.split(",", 3)]
    if len(parts) != 4:
        raise SystemExit("Unexpected drawHome renderDisplay shape")

    # The previous patch should have homeLine2Ticker(p) in argument 2.
    # Restore line 2 to the pet name and put the ticker on line 3, using the
    # existing line-3 action expression as the normal phase.
    if "homeLine2Ticker(p)" not in parts[1] and "homeLine3Ticker" not in parts[2]:
        raise SystemExit("Could not find current HOME line-2 stat ticker; refusing to guess")

    normal_line3 = parts[2]
    new_call = f"renderDisplay({parts[0]}, String(p.name), homeLine3Ticker(p, {normal_line3}), {parts[3]});"
    new_body = body[:r.start()] + new_call + body[r.end():]
    s = s[:dm.start("body")] + new_body + s[dm.end("body"):]

    # Add marker near the old ticker marker so repeat application is safe.
    s = s.replace(OLD_MARKER, OLD_MARKER + "\n" + MARKER, 1)

    ino.write_text(s)
    print(f"Moved HOME stat ticker to line 3 in {ino}")
    print("HOME: line 2 = pet name; line 3 alternates action/stat every 10s; long stats marquee.")


if __name__ == "__main__":
    main()
