#!/usr/bin/env python3
from pathlib import Path

patch = Path(__file__).resolve().parent / "patch_dnd_content_expansion_v1.py"
s = patch.read_text()

marker = "DND_CONTENT_PATCH_V2_SYMBOL_FIX"
if marker in s:
    print("DND content patch V2 symbol fix already present")
    raise SystemExit(0)

start = s.find("s, count = re.subn(\n")
end_marker = '    raise SystemExit("DND_SYMBOL_COUNT declaration not found")\n'
end = s.find(end_marker, start)
if start == -1 or end == -1:
    raise SystemExit("Could not find old DND_SYMBOL_COUNT patch block")
end += len(end_marker)

replacement = '''# DND_CONTENT_PATCH_V2_SYMBOL_FIX\n# Do not depend on where the legacy DND_SYMBOL_COUNT constant is declared.\n# The expanded browser owns its own count.\n'''
s = s[:start] + replacement + s[end:]

old_new_symbols = '''new_symbols = '''
pos = s.find(old_new_symbols)
if pos == -1:
    raise SystemExit("new_symbols anchor not found")

# Change only the generated replacement arrays to use an independent 48-entry count.
block_start = s.find("new_symbols = '''", pos)
block_end = s.find("'''\nif old_symbols not in s:", block_start)
if block_start == -1 or block_end == -1:
    raise SystemExit("new_symbols block bounds not found")
block = s[block_start:block_end]
block = block.replace(
    "new_symbols = '''static const char DND_SYMBOL_GLYPHS[DND_SYMBOL_COUNT] = {",
    "new_symbols = '''static const uint8_t DND_SYMBOL_COUNT_EXPANDED = 48;\\nstatic const char DND_SYMBOL_GLYPHS[DND_SYMBOL_COUNT_EXPANDED] = {",
    1,
)
block = block.replace(
    "static const char* const DND_SYMBOL_NAMES[DND_SYMBOL_COUNT] = {",
    "static const char* const DND_SYMBOL_NAMES[DND_SYMBOL_COUNT_EXPANDED] = {",
    1,
)
s = s[:block_start] + block + s[block_end:]

needle = 's = s.replace(old_symbols, new_symbols, 1)\n'
if needle not in s:
    raise SystemExit("symbol replacement anchor not found")
extra = needle + '''# Retarget only the DND symbol-browser runtime references to the expanded count.\ns = s.replace("(dndSymbolIndex+DND_SYMBOL_COUNT-1U)%DND_SYMBOL_COUNT",\n              "(dndSymbolIndex+DND_SYMBOL_COUNT_EXPANDED-1U)%DND_SYMBOL_COUNT_EXPANDED")\ns = s.replace("(dndSymbolIndex+1U)%DND_SYMBOL_COUNT",\n              "(dndSymbolIndex+1U)%DND_SYMBOL_COUNT_EXPANDED")\ns = s.replace("String(DND_SYMBOL_COUNT),\"UD MOVE B BACK\"",\n              "String(DND_SYMBOL_COUNT_EXPANDED),\"UD MOVE B BACK\"")\n'''
s = s.replace(needle, extra, 1)

patch.write_text(s)
print("REPAIRED content expansion patch V2")
print("  no dependency on legacy DND_SYMBOL_COUNT declaration")
print("  expanded Symbols browser uses independent 48-entry count")
print(f"patched: {patch}")
