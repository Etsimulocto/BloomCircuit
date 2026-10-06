#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_dnd_persist_type_visibility_v1.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_DND_PERSIST_TYPE_VISIBILITY_V1"
if marker in s:
    print("DND persist type visibility repair already present")
    raise SystemExit(0)

needle = "// BLOOM_DND_PERSISTENCE_V1\nstruct DndPersistV1 {"
if needle not in s:
    raise SystemExit("DndPersistV1 struct marker not found")

# Arduino auto-generates prototypes before later custom struct definitions.
# A forward declaration at file scope is enough for const-reference prototypes.
insert = "// BLOOM_DND_PERSIST_TYPE_VISIBILITY_V1\nstruct DndPersistV1;\n\n"

# Put the declaration before the first ordinary function definition / generated prototype region.
# Prefer immediately after includes if possible.
lines = s.splitlines(True)
idx = 0
while idx < len(lines) and (lines[idx].lstrip().startswith('#include') or lines[idx].strip() == ''):
    idx += 1
lines.insert(idx, insert)
s = ''.join(lines)

p.write_text(s)
print("REPAIRED DndPersistV1 Arduino auto-prototype visibility")
print("patched:", p)
