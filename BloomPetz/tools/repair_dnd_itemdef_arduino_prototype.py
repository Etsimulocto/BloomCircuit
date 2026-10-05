#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: repair_dnd_itemdef_arduino_prototype.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1]).expanduser().resolve()
s = p.read_text()

marker = "BLOOM_DND_ITEMDEF_FORWARD_DECL_V1"
if marker in s:
    print("DndItemDef Arduino prototype repair already present")
    raise SystemExit(0)

# Arduino auto-generates function prototypes before later sketch declarations.
# A forward declaration is sufficient because helper signatures only use
# const DndItemDef&, while the complete struct remains defined later before
# the helper function bodies.
prefix = "// BLOOM_DND_ITEMDEF_FORWARD_DECL_V1\nstruct DndItemDef;\n\n"
p.write_text(prefix + s)

print("REPAIRED DndItemDef Arduino auto-prototype visibility")
print(f"patched: {p}")
