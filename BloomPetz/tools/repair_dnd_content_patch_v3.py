#!/usr/bin/env python3
from pathlib import Path

p = Path.home() / "BloomCircuit/BloomPetz/tools/patch_dnd_content_expansion_v1.py"
s = p.read_text()

bad = 's = s.replace("String(DND_SYMBOL_COUNT),"UD MOVE B BACK"",\n                  "String(DND_SYMBOL_COUNT_EXPANDED),\\"UD MOVE B BACK\\"")'

good = '''s = s.replace(
    'String(DND_SYMBOL_COUNT),"UD MOVE B BACK"',
    'String(DND_SYMBOL_COUNT_EXPANDED),"UD MOVE B BACK"'
)'''

if bad in s:
    s = s.replace(bad, good, 1)
else:
    # Repair the malformed two-line form produced by v2 even if whitespace differs.
    lines = s.splitlines()
    out = []
    i = 0
    repaired = False
    while i < len(lines):
        line = lines[i]
        if 's = s.replace("String(DND_SYMBOL_COUNT),' in line and 'UD MOVE B BACK' in line:
            out.extend(good.splitlines())
            repaired = True
            # Skip continuation line if present.
            if i + 1 < len(lines) and 'DND_SYMBOL_COUNT_EXPANDED' in lines[i + 1]:
                i += 2
            else:
                i += 1
            continue
        out.append(line)
        i += 1
    if repaired:
        s = "\n".join(out) + "\n"
    else:
        raise SystemExit("Malformed symbol-count replacement line not found")

p.write_text(s)

# Syntax-check the patcher itself before reporting success.
compile(s, str(p), "exec")
print("REPAIRED DND content patcher quoting")
print("Python syntax check: PASS")
print(f"patched: {p}")
