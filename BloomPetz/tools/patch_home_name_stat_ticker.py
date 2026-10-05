#!/usr/bin/env python3
"""Add a HOME line-2 name/stat ticker with marquee support.

Behavior:
- HOME line 2 alternates every 10 seconds:
    PET NAME -> STAT + VALUE -> PET NAME -> next STAT + VALUE ...
- Stat phases advance sequentially through all 200 canonical stats.
- Long stat strings marquee across the 16-character OLED row.
- Values are shown as percentages with 4 decimal places, e.g. affection 0.0000%.
- Reads canonical stat names from BloomPetz/data/stats/stat_manifest.json and category JSON files.
- Leaves menu/stats browser/action/result screens untouched.
"""
from pathlib import Path
import json
import re
import sys

MARKER = "// BLOOMPETZ_HOME_NAME_STAT_TICKER_V1"


def cpp_quote(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_home_name_stat_ticker.py <bloompetz_v0_1.ino>")

    ino = Path(sys.argv[1]).expanduser().resolve()
    s = ino.read_text()
    if MARKER in s:
        print("HOME name/stat ticker already applied.")
        return

    # Resolve repo root from .../BloomPetz/firmware/bloompetz_v0_1/bloompetz_v0_1.ino
    bloompetz = ino.parents[2]
    stats_dir = bloompetz / "data" / "stats"
    manifest_path = stats_dir / "stat_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"stat manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    names = []
    for cat in manifest.get("categories", []):
        fp = stats_dir / cat["file"]
        if not fp.exists():
            raise SystemExit(f"stat file missing: {fp}")
        d = json.loads(fp.read_text())
        vals = d.get("stats", [])
        if len(vals) != 10:
            raise SystemExit(f"expected 10 stats in {fp}, got {len(vals)}")
        names.extend(vals)

    if len(names) != 200:
        raise SystemExit(f"expected 200 canonical stat names, got {len(names)}")

    names_cpp = ",\n".join("  " + cpp_quote(x) for x in names)

    # Insert ticker engine before drawHome so drawHome can call homeLine2Ticker().
    draw_anchor = "static void drawHome() {"
    pos = s.find(draw_anchor)
    if pos < 0:
        raise SystemExit("drawHome() not found")

    block = f'''{MARKER}
static const char* const HOME_STAT_NAMES[STAT_COUNT] = {{
{names_cpp}
}};
static constexpr uint32_t HOME_NAME_STAT_MODE_MS = 10000UL;
static constexpr uint32_t HOME_NAME_STAT_MARQUEE_MS = 350UL;
static uint32_t homeNameStatModeStartedMs = 0;
static uint32_t homeNameStatMarqueeMs = 0;
static uint16_t homeNameStatIndex = 0;
static uint16_t homeNameStatOffset = 0;
static bool homeNameStatShowingStat = false;

static String homeStatFullText(const PetSave &p) {{
  uint16_t idx = homeNameStatIndex % STAT_COUNT;
  String value = String(p.stats[idx] * 100.0f, 4) + "%";
  return String(HOME_STAT_NAMES[idx]) + " " + value;
}}

static String homeLine2Ticker(const PetSave &p) {{
  if (!homeNameStatShowingStat) return String(p.name);
  String msg = homeStatFullText(p);
  if (msg.length() <= 16) return msg;

  String looped = msg + "    " + msg;
  uint16_t cycle = (uint16_t)(msg.length() + 4);
  uint16_t off = cycle ? (homeNameStatOffset % cycle) : 0;
  while (off + 16 > looped.length()) looped += "    " + msg;
  return looped.substring(off, off + 16);
}}

static void serviceHomeNameStatTicker() {{
  if (uiMode != HOME) return;
  PetSave &p = pets[activeSlot];
  if (!p.occupied) return;

  uint32_t now = millis();
  if (homeNameStatModeStartedMs == 0) homeNameStatModeStartedMs = now;

  if (now - homeNameStatModeStartedMs >= HOME_NAME_STAT_MODE_MS) {{
    homeNameStatModeStartedMs = now;
    homeNameStatShowingStat = !homeNameStatShowingStat;
    homeNameStatOffset = 0;
    homeNameStatMarqueeMs = now;
    if (homeNameStatShowingStat) {{
      homeNameStatIndex = (uint16_t)((homeNameStatIndex + 1U) % STAT_COUNT);
    }}
    drawHome();
    return;
  }}

  if (homeNameStatShowingStat) {{
    String msg = homeStatFullText(p);
    if (msg.length() > 16 && now - homeNameStatMarqueeMs >= HOME_NAME_STAT_MARQUEE_MS) {{
      homeNameStatMarqueeMs = now;
      homeNameStatOffset++;
      drawHome();
    }}
  }}
}}

'''
    s = s[:pos] + block + s[pos:]

    # Patch only drawHome's occupied final render call, preserving current line1/3/4 logic.
    dm = re.search(r"static void drawHome\(\) \{(?P<body>.*?)\n\}", s, re.S)
    if not dm:
        raise SystemExit("could not isolate drawHome()")
    body = dm.group("body")
    renders = list(re.finditer(r"renderDisplay\(([^;]+)\);", body))
    if not renders:
        raise SystemExit("drawHome renderDisplay call not found")
    r = renders[-1]
    inner = r.group(1)
    parts = [x.strip() for x in inner.split(",", 3)]
    if len(parts) != 4:
        raise SystemExit("unexpected drawHome renderDisplay shape")
    new_call = f"renderDisplay({parts[0]}, homeLine2Ticker(p), {parts[2]}, {parts[3]});"
    new_body = body[:r.start()] + new_call + body[r.end():]
    s = s[:dm.start("body")] + new_body + s[dm.end("body"):]

    # Hook service into loop exactly once.
    if "serviceHomeNameStatTicker();" not in s:
        loop_anchor = "void loop() {"
        lp = s.find(loop_anchor)
        if lp < 0:
            raise SystemExit("loop() not found")
        nl = s.find("\n", lp)
        s = s[:nl+1] + "  serviceHomeNameStatTicker();\n" + s[nl+1:]

    ino.write_text(s)
    print(f"HOME name/stat ticker applied to {ino}")
    print("Line 2 alternates 10s pet name / 10s next stat; long stat text marquees at 350ms/char.")
    print("Loaded 200 canonical stat names from BloomPetz/data/stats.")


if __name__ == "__main__":
    main()
