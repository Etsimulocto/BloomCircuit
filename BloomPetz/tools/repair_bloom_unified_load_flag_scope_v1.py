#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_bloom_unified_load_flag_scope_v1.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_UNIFIED_LOAD_FLAG_SCOPE_V1"
if marker in s:
    print("Unified BLOOM load-flag scope repair already present")
    raise SystemExit(0)

if "bloomUnifiedLoadedOnce" not in s:
    raise SystemExit("bloomUnifiedLoadedOnce symbol not found")

forward = "// BLOOM_SYSTEM_UNIFIED_SAVE_FORWARD_V1\nstatic void saveBloomSystemState();\nstatic bool loadBloomSystemState();\n\n"
if forward not in s:
    raise SystemExit("unified save forward-declaration block not found")

# Remove the later definition from the unified-save implementation block so
# beginBootSplash() can reference the flag without a duplicate definition.
s = s.replace("static bool bloomUnifiedLoadedOnce = false;\n", "", 1)

replacement = (
    "// BLOOM_SYSTEM_UNIFIED_SAVE_FORWARD_V1\n"
    "static void saveBloomSystemState();\n"
    "static bool loadBloomSystemState();\n"
    "// BLOOM_UNIFIED_LOAD_FLAG_SCOPE_V1\n"
    "static bool bloomUnifiedLoadedOnce = false;\n\n"
)
s = s.replace(forward, replacement, 1)

p.write_text(s)
print("REPAIRED unified BLOOM load flag scope V1")
print("  bloomUnifiedLoadedOnce moved before beginBootSplash()")
print("  unified save/load logic unchanged")
print("patched:", p)
