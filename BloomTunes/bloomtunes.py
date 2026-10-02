#!/usr/bin/env python3
"""BloomTunes v0.1

Pi-first procedural audio playground for HAPPY JARZ.
Generates simple mono PCM WAV audio with no external Python packages.
"""

from __future__ import annotations

import math
import os
import random
import shutil
import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from typing import Callable, Iterable

SAMPLE_RATE = 44100
MASTER = 0.28

SOLFEGGIO = [174.0, 285.0, 396.0, 417.0, 528.0, 639.0, 741.0, 852.0, 963.0]


def clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def envelope(t: float, duration: float, attack: float = 0.03, release: float = 0.12) -> float:
    if duration <= 0:
        return 0.0
    a = min(1.0, t / max(attack, 1e-6))
    r = min(1.0, (duration - t) / max(release, 1e-6))
    return max(0.0, min(a, r))


def sine(freq: float, duration: float, amp: float = 1.0) -> list[float]:
    n = int(duration * SAMPLE_RATE)
    return [
        amp * envelope(i / SAMPLE_RATE, duration) * math.sin(2.0 * math.pi * freq * i / SAMPLE_RATE)
        for i in range(n)
    ]


def silence(duration: float) -> list[float]:
    return [0.0] * int(duration * SAMPLE_RATE)


def mix(buffers: Iterable[list[float]]) -> list[float]:
    buffers = list(buffers)
    if not buffers:
        return []
    length = max(len(b) for b in buffers)
    out = [0.0] * length
    for b in buffers:
        for i, sample in enumerate(b):
            out[i] += sample
    peak = max((abs(x) for x in out), default=1.0)
    if peak > 1.0:
        out = [x / peak for x in out]
    return out


def concat(*buffers: list[float]) -> list[float]:
    out: list[float] = []
    for b in buffers:
        out.extend(b)
    return out


def noise(duration: float, amp: float = 0.25) -> list[float]:
    n = int(duration * SAMPLE_RATE)
    return [random.uniform(-amp, amp) for _ in range(n)]


def lowpass(samples: list[float], alpha: float) -> list[float]:
    y = 0.0
    out = []
    for x in samples:
        y += alpha * (x - y)
        out.append(y)
    return out


def highpass(samples: list[float], alpha: float) -> list[float]:
    if not samples:
        return []
    prev_x = samples[0]
    prev_y = 0.0
    out = []
    for x in samples:
        y = alpha * (prev_y + x - prev_x)
        out.append(y)
        prev_x = x
        prev_y = y
    return out


def plink(freq: float, duration: float = 0.22, amp: float = 0.55) -> list[float]:
    n = int(duration * SAMPLE_RATE)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        decay = math.exp(-9.0 * t / max(duration, 1e-6))
        fundamental = math.sin(2 * math.pi * freq * t)
        shimmer = 0.35 * math.sin(2 * math.pi * freq * 2.02 * t)
        out.append(amp * decay * (fundamental + shimmer) / 1.35)
    return out


def preset_chimes(seconds: float = 12.0) -> list[float]:
    out: list[float] = []
    while len(out) < int(seconds * SAMPLE_RATE):
        f = random.choice(SOLFEGGIO)
        out.extend(plink(f, random.uniform(0.16, 0.42), random.uniform(0.25, 0.55)))
        out.extend(silence(random.uniform(0.25, 1.4)))
    return out[: int(seconds * SAMPLE_RATE)]


def preset_rain(seconds: float = 12.0) -> list[float]:
    base = lowpass(noise(seconds, 0.18), 0.025)
    drops = [0.0] * len(base)
    count = max(12, int(seconds * 7))
    for _ in range(count):
        start = random.randrange(max(1, len(drops) - 4000))
        p = plink(random.uniform(900.0, 2600.0), random.uniform(0.025, 0.10), random.uniform(0.03, 0.13))
        for i, x in enumerate(p):
            j = start + i
            if j >= len(drops):
                break
            drops[j] += x
    return mix([base, drops])


def preset_wind(seconds: float = 12.0) -> list[float]:
    raw = lowpass(noise(seconds, 0.55), 0.004)
    out = []
    for i, x in enumerate(raw):
        t = i / SAMPLE_RATE
        swell = 0.35 + 0.28 * math.sin(2 * math.pi * 0.08 * t) + 0.12 * math.sin(2 * math.pi * 0.19 * t)
        out.append(x * max(0.05, swell))
    return out


def preset_particles(seconds: float = 12.0) -> list[float]:
    out = [0.0] * int(seconds * SAMPLE_RATE)
    for _ in range(max(10, int(seconds * 2.5))):
        start = random.randrange(max(1, len(out) - 12000))
        base = random.choice(SOLFEGGIO[2:])
        p = concat(
            plink(base * 1.25, 0.09, 0.27),
            plink(base, 0.15, 0.22),
            plink(base * 0.75, 0.18, 0.16),
        )
        for i, x in enumerate(p):
            j = start + i
            if j >= len(out):
                break
            out[j] += x
    return out


def preset_galaxy(seconds: float = 12.0) -> list[float]:
    n = int(seconds * SAMPLE_RATE)
    drone = [0.0] * n
    for i in range(n):
        t = i / SAMPLE_RATE
        slow = 0.5 + 0.5 * math.sin(2 * math.pi * 0.055 * t)
        drone[i] = 0.10 * slow * (
            math.sin(2 * math.pi * 196.0 * t)
            + 0.55 * math.sin(2 * math.pi * 396.0 * t)
            + 0.25 * math.sin(2 * math.pi * 528.0 * t)
        )
    sparkles = preset_particles(seconds)
    return mix([drone, [x * 0.55 for x in sparkles]])


PRESETS: dict[str, Callable[[float], list[float]]] = {
    "chimes": preset_chimes,
    "rain": preset_rain,
    "wind": preset_wind,
    "particles": preset_particles,
    "galaxy": preset_galaxy,
}


def write_wav(samples: list[float], path: str) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for x in samples:
            value = int(clamp(x * MASTER) * 32767)
            frames.extend(struct.pack("<h", value))
        wf.writeframes(frames)


def play_file(path: str) -> None:
    players = [
        ("aplay", ["aplay", "-q", path]),
        ("paplay", ["paplay", path]),
        ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]),
    ]
    for exe, command in players:
        if shutil.which(exe):
            subprocess.run(command, check=False)
            return
    raise SystemExit("No supported player found. Install/use aplay, paplay, or ffplay.")


def main() -> None:
    print("BloomTunes v0.1")
    print("Procedural sound lab — no samples required.\n")
    names = list(PRESETS)
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    print("  r. random")
    print("  q. quit")

    while True:
        choice = input("\nBloomTunes> ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            break
        if choice in {"r", "random"}:
            name = random.choice(names)
        elif choice.isdigit() and 1 <= int(choice) <= len(names):
            name = names[int(choice) - 1]
        elif choice in PRESETS:
            name = choice
        else:
            print("Choose a preset number/name, r, or q.")
            continue

        print(f"Generating {name}...")
        samples = PRESETS[name](12.0)
        fd, path = tempfile.mkstemp(prefix="bloomtunes_", suffix=".wav")
        os.close(fd)
        try:
            write_wav(samples, path)
            play_file(path)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


if __name__ == "__main__":
    main()
