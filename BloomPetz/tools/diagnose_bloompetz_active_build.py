#!/usr/bin/env python3
from pathlib import Path
import hashlib
import subprocess

ROOT = Path.home() / "BloomCircuit"
print("=== BloomPetz active-build diagnosis ===")
print(f"Repo root: {ROOT}")

inos = sorted(ROOT.rglob("*.ino"))
print("\n-- INO files --")
for p in inos:
    try:
        s = p.read_text(errors="ignore")
    except Exception:
        continue
    flags = []
    for marker in [
        "BLOOM_DND_INFINITE_ROOMS_DEPTH_V1",
        "BLOOM_DND_GUARANTEED_EXIT_V1",
        "BLOOM_DND_ENGINE_OWNERSHIP_PROBE_V1",
        "GEN30 LIVE",
        "#..c...^",
        "#....+",
        "DND BEGINS",
    ]:
        if marker in s:
            flags.append(marker)
    sha = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    print(f"{p}\n  sha256={sha}\n  markers={flags or ['none']}")

print("\n-- Candidate sketch dirs --")
for p in inos:
    if p.parent.name == p.stem:
        print(f"Arduino sketch dir: {p.parent}")

print("\n-- Compiled binaries under repo --")
for p in sorted(ROOT.rglob("*.bin")):
    try:
        b = p.read_bytes()
    except Exception:
        continue
    flags = []
    for marker in [b"GEN30 LIVE", b"ROOM 1 MOD +/-1", b"THROUGH DOOR", b"DND BEGINS"]:
        if marker in b:
            flags.append(marker.decode(errors="ignore"))
    sha = hashlib.sha256(b).hexdigest()[:12]
    print(f"{p}\n  bytes={len(b)} sha256={sha}\n  embedded={flags or ['none']}")

print("\n-- Running Mini process --")
subprocess.run("pgrep -af bloompetz_mini.py || true", shell=True)

print("\n-- USB ports --")
subprocess.run("ls -l /dev/ttyACM* 2>/dev/null || true", shell=True)

print("\n=== IMPORTANT ===")
print("The sketch we intend to build is:")
print(ROOT / "BloomPetz/firmware/bloompetz_v0_1/bloompetz_v0_1.ino")
print("It MUST contain GEN30 LIVE and BLOOM_DND_INFINITE_ROOMS_DEPTH_V1.")
print("If it does, but the flashed board never shows GEN30 LIVE, the upload is using a stale/different build artifact.")
