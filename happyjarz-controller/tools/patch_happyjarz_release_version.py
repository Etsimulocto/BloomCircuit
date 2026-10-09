#!/usr/bin/env python3
"""Stage standalone editors + INFO manual + board arcade, then inject firmware/VERSION."""

from pathlib import Path
import re
import shutil
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_release_version.py <staged .ino>")

sketch = Path(sys.argv[1])
controller_dir = Path(__file__).resolve().parent.parent
firmware_dir = controller_dir / "firmware"
version_file = firmware_dir / "VERSION"
version = version_file.read_text(encoding="utf-8").strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    raise SystemExit(f"invalid firmware VERSION: {version!r}")

# Standalone clock editor: set local date/time directly from touch controls.
manual_clock_patch = Path(__file__).with_name("patch_happyjarz_manual_clock.py")
if not manual_clock_patch.exists():
    raise SystemExit(f"release staging failed: missing manual clock patch {manual_clock_patch}")
subprocess.run([sys.executable, str(manual_clock_patch), str(sketch)], check=True)

# Standalone SETTINGS editors reuse the existing alarm/timer state.
settings_patch = Path(__file__).with_name("patch_happyjarz_settings_menu.py")
if not settings_patch.exists():
    raise SystemExit(f"release staging failed: missing settings patch {settings_patch}")
subprocess.run([sys.executable, str(settings_patch), str(sketch)], check=True)

# Late brightness patch deliberately lifts the old 50% product ceiling to 100%
# and turns MENU -> LIGHTS into a live SOLID brightness tuner.
brightness_patch = Path(__file__).with_name("patch_happyjarz_brightness_editor.py")
if not brightness_patch.exists():
    raise SystemExit(f"release staging failed: missing brightness patch {brightness_patch}")
subprocess.run([sys.executable, str(brightness_patch), str(sketch)], check=True)

# Board-local INFO / manual pages. Apply after menu/editors so it can extend the
# final menu count and input router without earlier patches rewriting it.
info_patch = Path(__file__).with_name("patch_happyjarz_info_manual.py")
if not info_patch.exists():
    raise SystemExit(f"release staging failed: missing info manual patch {info_patch}")
subprocess.run([sys.executable, str(info_patch), str(sketch)], check=True)

# Arcade is part of the product firmware now. Copy its normal Arduino translation
# units into the staged sketch directory, then patch the already-staged OLED/menu.
arcade_h = firmware_dir / "happyjarz_arcade.h"
arcade_cpp = firmware_dir / "happyjarz_arcade.cpp"
arcade_patch = Path(__file__).with_name("patch_happyjarz_arcade.py")
for required in (arcade_h, arcade_cpp, arcade_patch):
    if not required.exists():
        raise SystemExit(f"release staging failed: missing arcade file {required}")

shutil.copy2(arcade_h, sketch.parent / arcade_h.name)
shutil.copy2(arcade_cpp, sketch.parent / arcade_cpp.name)
subprocess.run([sys.executable, str(arcade_patch), str(sketch)], check=True)

# Final one-hour software sleep runs after arcade so it can freeze arcade state
# and intercept the final physical-input router without disturbing wake logic.
sleep_patch = Path(__file__).with_name("patch_happyjarz_sleep_mode.py")
if not sleep_patch.exists():
    raise SystemExit(f"release staging failed: missing sleep patch {sleep_patch}")
subprocess.run([sys.executable, str(sleep_patch), str(sketch)], check=True)

# Finalize logical input ordering after all menu/game patches have inserted their
# handlers. This keeps the sleep layer's first wake check physical-only, then
# merges host/gamepad KEY events before every menu/game router.
unified_input_patch = Path(__file__).with_name("patch_happyjarz_unified_input_order.py")
if not unified_input_patch.exists():
    raise SystemExit(f"release staging failed: missing unified input patch {unified_input_patch}")
subprocess.run([sys.executable, str(unified_input_patch), str(sketch)], check=True)

s = sketch.read_text(encoding="utf-8")
pattern = r'static const char \*HJ_FW_VERSION = "[^"]+";'
replacement = f'static const char *HJ_FW_VERSION = "{version}";'
s, count = re.subn(pattern, replacement, s, count=1)
if count != 1:
    raise SystemExit("release version patch failed: HJ_FW_VERSION marker not found")

sketch.write_text(s, encoding="utf-8")
print(f"Applied HAPPY JARZ firmware release version {version} with standalone editors + 0-100 brightness + INFO manual + board arcade staged.")
