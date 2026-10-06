#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_dnd_persist_type_visibility_v2.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_DND_PERSIST_TYPE_VISIBILITY_V2"
if marker in s:
    print("DND persist type visibility V2 already present")
    raise SystemExit(0)

needle = "// BLOOM_PET_DND_PERSISTENCE_V1\nstruct DndPersistV1 {"
if needle not in s:
    raise SystemExit("exact DndPersistV1 declaration not found")

insert = "// BLOOM_DND_PERSIST_TYPE_VISIBILITY_V2\nstruct DndPersistV1;\n\n"

lines = s.splitlines(True)
idx = 0
while idx < len(lines) and (lines[idx].lstrip().startswith('#include') or lines[idx].strip() == ''):
    idx += 1
lines.insert(idx, insert)
s = ''.join(lines)

p.write_text(s)
print("REPAIRED DndPersistV1 Arduino auto-prototype visibility V2")
print("  corrected persistence marker match")
print("  added forward declaration before Arduino-generated prototypes")
print("patched:", p)
