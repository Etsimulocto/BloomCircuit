#!/usr/bin/env python3
"""Rebalance BloomPetz stat growth for long-term/year-scale play.

Player-facing stat values use four decimal places of percent (0.0000%).
The save format remains a 0.0..1.0 float internally.

New growth scale:
- action stat hit: 0.0010% .. 0.0050% = raw 0.000010 .. 0.000050
- treat stat hit:  0.0010% .. 0.0050% = raw 0.000010 .. 0.000050

Also changes action result and serial telemetry to report percent with four decimals.
This patch does NOT alter already-earned stats in existing pet saves.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_YEAR_SCALE_STAT_GROWTH_V1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"Could not find {label}; refusing to guess")
    return s.replace(old, new, 1)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_yearscale_stat_growth.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Year-scale stat growth patch already applied.")
        return

    # Confirm the known live scale before changing anything.
    if "static constexpr float GAIN_MIN = 0.0001f;" not in s:
        raise SystemExit("Expected old GAIN_MIN=0.0001f not found; refusing to guess")
    if "static constexpr float GAIN_MAX = 0.0050f;" not in s:
        raise SystemExit("Expected old GAIN_MAX=0.0050f not found; refusing to guess")
    if "float gain = random(1,51) / 10000.0f;" not in s:
        raise SystemExit("Expected old treat gain formula not found; refusing to guess")

    # Put a durable marker near the constants.
    s = replace_once(
        s,
        "static constexpr float GAIN_MIN = 0.0001f;\nstatic constexpr float GAIN_MAX = 0.0050f;",
        MARKER + "\n"
        "// Internal save values are 0..1. Player-facing values are percent with 4 decimals.\n"
        "// 0.000010 raw = 0.0010%; 0.000050 raw = 0.0050%.\n"
        "static constexpr float GAIN_MIN = 0.000010f;\n"
        "static constexpr float GAIN_MAX = 0.000050f;",
        "action gain constants",
    )

    # Update the nearby top-of-file documentation if it still has the old scale.
    s = s.replace(
        "//   - response-speed gain 0.0001..0.0050",
        "//   - response-speed gain 0.0010%..0.0050% (4-decimal percent display)",
        1,
    )

    # Treats used a separate old fast path; bring them onto the same long-term scale.
    s = replace_once(
        s,
        "float gain = random(1,51) / 10000.0f;",
        "float gain = random(10,51) / 1000000.0f;  // 0.0010%..0.0050%",
        "treat gain formula",
    )

    # Player-facing action result: show percent, four decimals, not a six-decimal raw float.
    old_result = 'String result = firstRewardToday ? (String("+")+String(gain,4)+"  E-12.5") : "FUN ONLY TODAY";'
    new_result = 'String result = firstRewardToday ? (String("+")+String(gain * 100.0f,4)+"% E-12.5") : "FUN ONLY TODAY";'
    s = replace_once(s, old_result, new_result, "action result formatting")

    # Serial telemetry: keep it human-readable in the same four-decimal percent unit.
    old_gain_log = 'Serial.printf("BP|GAIN|source=%s|stat=%u|amount=%.6f|value=%.6f\\n", ACTION_NAMES[action], stat, gain, p.stats[stat]);'
    new_gain_log = 'Serial.printf("BP|GAIN|source=%s|stat=%u|amount_pct=%.4f|value_pct=%.4f\\n", ACTION_NAMES[action], stat, gain * 100.0f, p.stats[stat] * 100.0f);'
    s = replace_once(s, old_gain_log, new_gain_log, "per-stat gain telemetry")

    old_treat_log = 'Serial.printf("BP|TREAT|stat=%u|gain=%.6f|today=%u\\n", stat, gain, p.treatsToday);'
    new_treat_log = 'Serial.printf("BP|TREAT|stat=%u|gain_pct=%.4f|today=%u\\n", stat, gain * 100.0f, p.treatsToday);'
    s = replace_once(s, old_treat_log, new_treat_log, "treat telemetry")

    old_action_log = 'Serial.printf("BP|ACTION|name=%s|response_ms=%lu|gain=%.6f|rewarded=%u|energy=%.1f\\n", ACTION_NAMES[selectedAction], (unsigned long)responseMs, gain, firstRewardToday, p.foodEnergy);'
    if old_action_log in s:
        new_action_log = 'Serial.printf("BP|ACTION|name=%s|response_ms=%lu|gain_pct=%.4f|rewarded=%u|energy=%.1f\\n", ACTION_NAMES[selectedAction], (unsigned long)responseMs, gain * 100.0f, firstRewardToday, p.foodEnergy);'
        s = s.replace(old_action_log, new_action_log, 1)
    else:
        # Local builds may have slightly different tail fields; safely rewrite only the format token/name.
        s, n = re.subn(
            r'Serial\.printf\("BP\|ACTION\|name=%s\|response_ms=%lu\|gain=%.6f\|rewarded=%u\|energy=%.1f\\n",\s*ACTION_NAMES\[selectedAction\],\s*\(unsigned long\)responseMs,\s*gain,',
            'Serial.printf("BP|ACTION|name=%s|response_ms=%lu|gain_pct=%.4f|rewarded=%u|energy=%.1f\\n", ACTION_NAMES[selectedAction], (unsigned long)responseMs, gain * 100.0f,',
            s,
            count=1,
        )
        if n != 1:
            raise SystemExit("Could not safely rewrite action telemetry; refusing partial patch")

    p.write_text(s)
    print(f"Year-scale stat growth applied to {p}")
    print("Action/treat stat hits are now 0.0010%..0.0050% each.")
    print("Player-facing gain text/telemetry now uses percent with 4 decimals.")
    print("Existing pet stat values were NOT changed by this patch.")


if __name__ == "__main__":
    main()
