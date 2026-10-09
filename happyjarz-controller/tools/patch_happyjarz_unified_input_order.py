#!/usr/bin/env python3
"""Move host/gamepad virtual keys ahead of every menu/game input router.

Later UI patches insert their handlers immediately after the physical touch scan.
That can place CLOCK/SETTINGS/INFO/ARCADE handlers before the host-sync q[] merge,
making those screens physical-touch-only. This final staging patch relocates the
host merge immediately after the sleep layer's physical-only wake check, so:

1. physical touch is scanned,
2. physical-only sleep wake logic runs,
3. host/gamepad one-shot keys merge into q[],
4. every menu/game/saver/HOME router sees the same logical controls.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_unified_input_order.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

merge = r'''  // Merge one-shot host events after reading physical touch. Existing menu,
  // game, saver and HOME code below this point sees one unified q[] array.
  for (uint8_t i=0; i<INPUT_COUNT; ++i) {
    if (hjHostKeyPending[i]) {
      q[i] = true;
      hjHostKeyPending[i] = false;
    }
  }
'''

if s.count(merge) != 1:
    raise SystemExit(
        f"unified-input-order patch failed: expected exactly one host merge block, found {s.count(merge)}"
    )

sleep_tail = r'''  if (hjAnyPhysicalPress) {
    hjSleepLastActivityMs = millis();
    if (hjSleepActive) {
      hjWakeFromSleep("TOUCH");
      for (uint8_t i=0; i<INPUT_COUNT; ++i) latched[i] = q[i];
      return;
    }
  }
'''

if sleep_tail not in s:
    raise SystemExit("unified-input-order patch failed: physical sleep-wake block not found")

s = s.replace(merge, "", 1)

new_merge = r'''
  // HAPPYJARZ_UNIFIED_INPUT_ORDER_V1
  // Physical-only sleep wake has already run. From here down, physical touch
  // and host/gamepad KEY events are intentionally the same logical controls.
  for (uint8_t i=0; i<INPUT_COUNT; ++i) {
    if (hjHostKeyPending[i]) {
      q[i] = true;
      hjHostKeyPending[i] = false;
    }
  }
'''

s = s.replace(sleep_tail, sleep_tail + new_merge, 1)

p.write_text(s, encoding="utf-8")
print("Applied HAPPY JARZ unified input order: gamepad/host keys now precede every menu/game router.")
