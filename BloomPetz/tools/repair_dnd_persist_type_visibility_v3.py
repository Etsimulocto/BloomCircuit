#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_dnd_persist_type_visibility_v3.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()
marker = "BLOOM_DND_PERSIST_TYPE_VISIBILITY_V3"
if marker in s:
    print("DND persist type visibility V3 already present")
    raise SystemExit(0)

# Do not depend on the exact formatting/location of the struct body.  The
# compiler already proves the checksum function exists and references the type.
if "dndPersistChecksumV1" not in s:
    raise SystemExit("dndPersistChecksumV1 function not found; persistence patch may not be present")

# If a real forward declaration is already present, nothing else is needed.
if "struct DndPersistV1;" in s:
    print("DndPersistV1 forward declaration already present")
    raise SystemExit(0)

insert = "// BLOOM_DND_PERSIST_TYPE_VISIBILITY_V3\nstruct DndPersistV1;\n\n"

# Put it immediately after the leading include/blank region.  This is early
# enough for Arduino's generated prototypes regardless of where the full struct
# definition later appears in the .ino.
lines = s.splitlines(True)
idx = 0
while idx < len(lines):
    t = lines[idx].strip()
    if t == "" or lines[idx].lstrip().startswith("#include"):
        idx += 1
        continue
    break
lines.insert(idx, insert)
p.write_text(''.join(lines))

print("REPAIRED DndPersistV1 Arduino auto-prototype visibility V3")
print("  no struct-body anchor required")
print("  forward declaration inserted near top of sketch")
print("patched:", p)
