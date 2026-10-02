#!/usr/bin/env python3
"""Stage standalone clock/settings + board arcade, then inject firmware/VERSION."""

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

# Standalone SETTINGS editors reuse the existing alarm/timer/display state and
# persistSettings() path. Apply after the manual clock patch because both extend
# the final OLED detail-page control router.
settings_patch = Path(__file__).with_name("patch_happyjarz_settings_menu.py")
if not settings_patch.exists():
    raise SystemExit(f"release staging failed: missing settings patch {settings_patch}")
subprocess.run([sys.executable, str(settings_patch), str(sketch)], check=True)

# Arcade is part of the product firmware now. Copy its normal Arduino translation
# units into the staged sketch directory, then patch the already-staged OLED/menu
# code so MAIN MENU -> GAMES launches the arcade through the known-good U8g2 layer.
arcade_h = firmware_dir / "happyjarz_arcade.h"
arcade_cpp = firmware_dir / "happyjarz_arcade.cpp"
arcade_patch = Path(__file__).with_name("patch_happyjarz_arcade.py")
for required in (arcade_h, arcade_cpp, arcade_patch):
    if not required.exists():
        raise SystemExit(f"release staging failed: missing arcade file {required}")

shutil.copy2(arcade_h, sketch.parent / arcade_h.name)
shutil.copy2(arcade_cpp, sketch.parent / arcade_cpp.name)
subprocess.run([sys.executable, str(arcade_patch), str(sketch)], check=True)

s = sketch.read_text(encoding="utf-8")
pattern = r'static const char \*HJ_FW_VERSION = "[^"]+";'
replacement = f'static const char *HJ_FW_VERSION = "{version}";'
s, count = re.subn(pattern, replacement, s, count=1)
if count != 1:
    raise SystemExit("release version patch failed: HJ_FW_VERSION marker not found")

sketch.write_text(s, encoding="utf-8")
print(f"Applied HAPPY JARZ firmware release version {version} with manual clock + settings + board arcade staged.")
