#!/usr/bin/env python3
"""BloomTunes v0.2 — Raspberry Pi procedural synth workbench.

Tkinter tuning app for designing HAPPY JARZ sound recipes on the Pi.
No sample files and no non-standard Python packages are required.
Audio is rendered to a temporary stereo WAV and played through aplay,
paplay, or ffplay. Settings can be saved as JSON for later ESP32 porting.
"""

from __future__ import annotations

import json
import math
import os
import random
import shutil
import struct
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass, asdict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

SAMPLE_RATE = 44100
SOLFEGGIO = [174.0, 285.0, 396.0, 417.0, 528.0, 639.0, 741.0, 852.0, 963.0]


def clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def midi_like_note(freq: float) -> str:
    if freq <= 0:
        return "--"
    n = round(69 + 12 * math.log2(freq / 440.0))
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[n % 12]}{n // 12 - 1}"


@dataclass
class Patch:
    mode: str = "TONE"
    waveform: str = "SINE"
    frequency: float = 528.0
    detune_cents: float = 0.0
    pulse_width: float = 50.0
    harmonics: int = 1
    harmonic_falloff: float = 65.0
    master: float = 24.0
    attack: float = 0.03
    decay: float = 0.12
    sustain: float = 70.0
    release: float = 0.30
    lfo_rate: float = 0.20
    lfo_depth: float = 0.0
    vibrato_rate: float = 5.0
    vibrato_depth: float = 0.0
    noise: float = 0.0
    lowpass: float = 100.0
    highpass: float = 0.0
    density: float = 3.0
    randomness: float = 25.0
    glide: float = 0.0
    duration: float = 6.0
    seed: int = 825


FACTORY_PATCHES: dict[str, Patch] = {
    "Pure 528": Patch(mode="TONE", waveform="SINE", frequency=528, master=20, attack=0.08, release=0.55),
    "Warm Drone": Patch(mode="DRONE", waveform="SINE", frequency=174, harmonics=3, harmonic_falloff=58, master=18, attack=1.0, release=1.5, lfo_rate=0.07, lfo_depth=12),
    "Soft Chimes": Patch(mode="CHIMES", waveform="SINE", frequency=528, master=21, attack=0.005, release=0.55, density=1.8, randomness=40),
    "Rain": Patch(mode="RAIN", waveform="NOISE", master=24, lowpass=58, highpass=12, density=8.0, randomness=75),
    "Wind": Patch(mode="WIND", waveform="NOISE", master=22, lowpass=26, highpass=2, lfo_rate=0.08, lfo_depth=60, randomness=35),
    "Particles": Patch(mode="PARTICLES", waveform="SINE", frequency=639, master=21, release=0.25, density=3.0, randomness=65),
    "Galaxy": Patch(mode="GALAXY", waveform="SINE", frequency=196, harmonics=4, master=18, attack=0.8, release=1.2, lfo_rate=0.05, lfo_depth=18, density=1.2, randomness=55),
}


class SynthEngine:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.last_path: str | None = None
        self.lock = threading.Lock()

    @staticmethod
    def osc(kind: str, phase: float, pulse_width: float) -> float:
        p = phase % 1.0
        if kind == "SINE":
            return math.sin(2.0 * math.pi * p)
        if kind == "SQUARE":
            return 1.0 if p < pulse_width / 100.0 else -1.0
        if kind == "TRIANGLE":
            return 4.0 * abs(p - 0.5) - 1.0
        if kind == "SAW":
            return 2.0 * p - 1.0
        return random.uniform(-1.0, 1.0)

    @staticmethod
    def env(t: float, total: float, p: Patch) -> float:
        a = max(0.001, p.attack)
        d = max(0.001, p.decay)
        r = max(0.001, p.release)
        sustain = clamp(p.sustain / 100.0, 0.0, 1.0)
        release_start = max(a + d, total - r)
        if t < a:
            return t / a
        if t < a + d:
            x = (t - a) / d
            return 1.0 + (sustain - 1.0) * x
        if t < release_start:
            return sustain
        if t < total:
            x = (t - release_start) / max(total - release_start, 0.001)
            return sustain * (1.0 - x)
        return 0.0

    @staticmethod
    def filters(samples: list[float], lowpass_pct: float, highpass_pct: float) -> list[float]:
        out = samples
        if lowpass_pct < 99.9:
            # Percentage maps to a one-pole smoothing coefficient.
            alpha = 0.002 + (lowpass_pct / 100.0) ** 2 * 0.45
            y = 0.0
            lp: list[float] = []
            for x in out:
                y += alpha * (x - y)
                lp.append(y)
            out = lp
        if highpass_pct > 0.1 and out:
            alpha = 0.995 - min(0.35, highpass_pct / 300.0)
            prev_x = out[0]
            prev_y = 0.0
            hp: list[float] = []
            for x in out:
                y = alpha * (prev_y + x - prev_x)
                hp.append(y)
                prev_x, prev_y = x, y
            out = hp
        return out

    def tone(self, p: Patch, seconds: float, base_freq: float | None = None) -> list[float]:
        n = int(seconds * SAMPLE_RATE)
        out = [0.0] * n
        phase = 0.0
        base = max(20.0, base_freq if base_freq is not None else p.frequency)
        detune = 2.0 ** (p.detune_cents / 1200.0)
        for i in range(n):
            t = i / SAMPLE_RATE
            amp_lfo = 1.0 - (p.lfo_depth / 100.0) * 0.5 * (1.0 + math.sin(2 * math.pi * p.lfo_rate * t))
            vib = 2.0 ** (((p.vibrato_depth / 100.0) * 100.0 * math.sin(2 * math.pi * p.vibrato_rate * t)) / 1200.0)
            freq = base * detune * vib
            phase += freq / SAMPLE_RATE
            s = 0.0
            weight = 1.0
            total_w = 0.0
            for h in range(1, max(1, int(p.harmonics)) + 1):
                s += weight * self.osc(p.waveform, phase * h, p.pulse_width)
                total_w += weight
                weight *= clamp(p.harmonic_falloff / 100.0, 0.0, 1.0)
            if total_w:
                s /= total_w
            if p.noise > 0:
                s += random.uniform(-1, 1) * (p.noise / 100.0)
            out[i] = s * self.env(t, seconds, p) * amp_lfo
        return self.filters(out, p.lowpass, p.highpass)

    def add_event(self, target: list[float], event: list[float], start: int, gain: float = 1.0) -> None:
        for i, x in enumerate(event):
            j = start + i
            if j >= len(target):
                break
            target[j] += x * gain

    def render(self, p: Patch) -> tuple[list[float], list[float]]:
        random.seed(p.seed)
        seconds = clamp(p.duration, 1.0, 30.0)
        n = int(seconds * SAMPLE_RATE)
        mode = p.mode.upper()

        if mode == "TONE":
            mono = self.tone(p, seconds)
        elif mode == "DRONE":
            mono = self.tone(p, seconds)
        elif mode in {"CHIMES", "PARTICLES"}:
            mono = [0.0] * n
            count = max(1, int(seconds * p.density))
            for _ in range(count):
                spread = p.randomness / 100.0
                if random.random() < 0.65:
                    f = random.choice(SOLFEGGIO)
                else:
                    f = p.frequency * (2.0 ** random.uniform(-spread, spread))
                event_len = random.uniform(0.08, 0.38 if mode == "PARTICLES" else 0.8)
                ep = Patch(**asdict(p))
                ep.attack = min(ep.attack, 0.015)
                ep.release = min(max(ep.release, 0.08), event_len * 0.9)
                ep.duration = event_len
                event = self.tone(ep, event_len, f)
                if mode == "PARTICLES":
                    event = [x * math.exp(-5.0 * i / max(1, len(event))) for i, x in enumerate(event)]
                self.add_event(mono, event, random.randrange(max(1, n - len(event))))
        elif mode == "RAIN":
            mono = [random.uniform(-1, 1) * 0.18 for _ in range(n)]
            mono = self.filters(mono, min(p.lowpass, 70), max(p.highpass, 5))
            for _ in range(max(10, int(seconds * p.density))):
                f = random.uniform(900, 3200)
                ep = Patch(**asdict(p))
                ep.waveform = "SINE"
                ep.attack = 0.001
                ep.release = 0.06
                ep.harmonics = 2
                event = self.tone(ep, 0.07, f)
                self.add_event(mono, event, random.randrange(max(1, n - len(event))), random.uniform(0.08, 0.25))
        elif mode == "WIND":
            raw = [random.uniform(-1, 1) for _ in range(n)]
            raw = self.filters(raw, min(p.lowpass, 40), p.highpass)
            mono = []
            for i, x in enumerate(raw):
                t = i / SAMPLE_RATE
                swell = 0.16 + 0.32 * (0.5 + 0.5 * math.sin(2 * math.pi * max(0.01, p.lfo_rate) * t))
                mono.append(x * swell)
        elif mode == "GALAXY":
            mono = self.tone(p, seconds)
            for _ in range(max(4, int(seconds * p.density))):
                f = random.choice(SOLFEGGIO[2:])
                ep = Patch(**asdict(p))
                ep.waveform = "SINE"
                ep.attack = 0.005
                ep.release = 0.35
                ep.harmonics = 2
                event = self.tone(ep, 0.4, f)
                self.add_event(mono, event, random.randrange(max(1, n - len(event))), 0.25)
        else:
            mono = self.tone(p, seconds)

        peak = max((abs(x) for x in mono), default=1.0)
        if peak > 1.0:
            mono = [x / peak for x in mono]

        gain = clamp(p.master / 100.0, 0.0, 1.0)
        mono = [clamp(x * gain) for x in mono]
        # Slight stereo spread for Pi auditioning; final HAPPY JARZ speaker remains mono.
        left = mono
        right = [clamp(x * 0.96) for x in mono]
        return left, right

    @staticmethod
    def write_wav(left: list[float], right: list[float], path: str) -> None:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            frames = bytearray()
            for l, r in zip(left, right):
                frames.extend(struct.pack("<hh", int(clamp(l) * 32767), int(clamp(r) * 32767)))
            wf.writeframes(frames)

    def stop(self) -> None:
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
            self.process = None
            if self.last_path:
                try:
                    os.unlink(self.last_path)
                except OSError:
                    pass
                self.last_path = None

    def play(self, p: Patch) -> None:
        self.stop()
        left, right = self.render(p)
        fd, path = tempfile.mkstemp(prefix="bloomtunes_", suffix=".wav")
        os.close(fd)
        self.write_wav(left, right, path)
        players = [
            ("aplay", ["aplay", "-q", path]),
            ("paplay", ["paplay", path]),
            ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]),
        ]
        command = None
        for exe, cmd in players:
            if shutil.which(exe):
                command = cmd
                break
        if command is None:
            os.unlink(path)
            raise RuntimeError("No audio player found (aplay, paplay, or ffplay).")
        with self.lock:
            self.last_path = path
            self.process = subprocess.Popen(command)


class BloomTunesApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("BloomTunes — Procedural Synth Lab")
        self.geometry("1180x790")
        self.minsize(1040, 700)
        self.engine = SynthEngine()
        self.vars: dict[str, tk.Variable] = {}
        self.status = tk.StringVar(value="Ready — tune a patch and press PLAY")
        self._build()
        self.load_patch(FACTORY_PATCHES["Pure 528"])
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="BloomTunes", font=("TkDefaultFont", 20, "bold")).pack(side="left")
        ttk.Label(top, text="Pi procedural synth → HAPPY JARZ recipe lab").pack(side="left", padx=12)

        preset_var = tk.StringVar(value="Pure 528")
        preset = ttk.Combobox(top, state="readonly", width=18, textvariable=preset_var, values=list(FACTORY_PATCHES))
        preset.pack(side="right", padx=4)
        ttk.Button(top, text="LOAD FACTORY", command=lambda: self.load_patch(FACTORY_PATCHES[preset_var.get()])).pack(side="right", padx=4)

        toolbar = ttk.Frame(self, padding=(10, 0, 10, 8))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="▶ PLAY", command=self.play).pack(side="left", padx=3)
        ttk.Button(toolbar, text="■ STOP", command=self.stop).pack(side="left", padx=3)
        ttk.Button(toolbar, text="RANDOMIZE", command=self.randomize).pack(side="left", padx=3)
        ttk.Button(toolbar, text="SOLFEGGIO →", command=self.next_solfeggio).pack(side="left", padx=3)
        ttk.Button(toolbar, text="SAVE PATCH", command=self.save_patch).pack(side="right", padx=3)
        ttk.Button(toolbar, text="LOAD PATCH", command=self.open_patch).pack(side="right", padx=3)

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        body.columnconfigure((0, 1, 2, 3), weight=1)
        body.rowconfigure(0, weight=1)

        self.osc_frame = ttk.LabelFrame(body, text="OSCILLATOR", padding=10)
        self.env_frame = ttk.LabelFrame(body, text="ENVELOPE", padding=10)
        self.mod_frame = ttk.LabelFrame(body, text="MOD / FILTER", padding=10)
        self.texture_frame = ttk.LabelFrame(body, text="TEXTURE / PERFORMANCE", padding=10)
        for i, frame in enumerate((self.osc_frame, self.env_frame, self.mod_frame, self.texture_frame)):
            frame.grid(row=0, column=i, sticky="nsew", padx=5)

        self.add_choice(self.osc_frame, "mode", "MODE", ["TONE", "DRONE", "CHIMES", "RAIN", "WIND", "PARTICLES", "GALAXY"])
        self.add_choice(self.osc_frame, "waveform", "WAVE", ["SINE", "SQUARE", "TRIANGLE", "SAW", "NOISE"])
        self.add_knob(self.osc_frame, "frequency", "FREQUENCY Hz", 40, 2000, 1)
        self.add_knob(self.osc_frame, "detune_cents", "DETUNE cents", -100, 100, 1)
        self.add_knob(self.osc_frame, "pulse_width", "PULSE WIDTH %", 5, 95, 1)
        self.add_knob(self.osc_frame, "harmonics", "HARMONICS", 1, 8, 1)
        self.add_knob(self.osc_frame, "harmonic_falloff", "HARMONIC FALL %", 0, 100, 1)
        self.add_knob(self.osc_frame, "master", "MASTER %", 0, 50, 1)

        self.add_knob(self.env_frame, "attack", "ATTACK sec", 0.001, 3.0, 0.001)
        self.add_knob(self.env_frame, "decay", "DECAY sec", 0.001, 3.0, 0.001)
        self.add_knob(self.env_frame, "sustain", "SUSTAIN %", 0, 100, 1)
        self.add_knob(self.env_frame, "release", "RELEASE sec", 0.01, 5.0, 0.01)
        ttk.Separator(self.env_frame).pack(fill="x", pady=8)
        ttk.Label(self.env_frame, text="ADSR controls the shape of each generated tone.\nShort A/R = plink. Long A/R = wash/drone.", wraplength=210).pack(anchor="w")

        self.add_knob(self.mod_frame, "lfo_rate", "AMP LFO Hz", 0.01, 8.0, 0.01)
        self.add_knob(self.mod_frame, "lfo_depth", "AMP LFO DEPTH %", 0, 100, 1)
        self.add_knob(self.mod_frame, "vibrato_rate", "VIBRATO Hz", 0.1, 15, 0.1)
        self.add_knob(self.mod_frame, "vibrato_depth", "VIBRATO DEPTH %", 0, 100, 1)
        self.add_knob(self.mod_frame, "noise", "NOISE MIX %", 0, 100, 1)
        self.add_knob(self.mod_frame, "lowpass", "LOW PASS %", 0, 100, 1)
        self.add_knob(self.mod_frame, "highpass", "HIGH PASS %", 0, 100, 1)

        self.add_knob(self.texture_frame, "density", "EVENTS / sec", 0.2, 20, 0.1)
        self.add_knob(self.texture_frame, "randomness", "RANDOMNESS %", 0, 100, 1)
        self.add_knob(self.texture_frame, "glide", "GLIDE % (reserved)", 0, 100, 1)
        self.add_knob(self.texture_frame, "duration", "PREVIEW sec", 1, 20, 1)
        self.add_knob(self.texture_frame, "seed", "RANDOM SEED", 0, 9999, 1)

        info = ttk.LabelFrame(self, text="PATCH READOUT", padding=8)
        info.pack(fill="x", padx=10, pady=(0, 8))
        self.readout = tk.StringVar()
        ttk.Label(info, textvariable=self.readout, font=("TkFixedFont", 10)).pack(anchor="w")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=5).pack(fill="x", side="bottom")
        self.after(250, self.refresh_readout)

    def add_choice(self, parent: ttk.Frame, key: str, label: str, values: list[str]) -> None:
        ttk.Label(parent, text=label).pack(anchor="w")
        var = tk.StringVar()
        self.vars[key] = var
        ttk.Combobox(parent, state="readonly", values=values, textvariable=var).pack(fill="x", pady=(0, 7))

    def add_knob(self, parent: ttk.Frame, key: str, label: str, lo: float, hi: float, resolution: float) -> None:
        ttk.Label(parent, text=label).pack(anchor="w")
        var = tk.DoubleVar()
        self.vars[key] = var
        scale = tk.Scale(parent, from_=hi, to=lo, variable=var, resolution=resolution, orient="vertical", length=105, showvalue=True)
        scale.pack(fill="x", pady=(0, 5))

    def current_patch(self) -> Patch:
        data: dict[str, object] = {}
        for key in asdict(Patch()):
            v = self.vars[key].get()
            if key in {"harmonics", "seed"}:
                v = int(round(float(v)))
            data[key] = v
        return Patch(**data)

    def load_patch(self, p: Patch) -> None:
        for key, value in asdict(p).items():
            self.vars[key].set(value)
        self.status.set(f"Loaded patch: {p.mode} / {p.waveform}")

    def refresh_readout(self) -> None:
        try:
            p = self.current_patch()
            self.readout.set(
                f"{p.mode:<10} {p.waveform:<8}  {p.frequency:7.1f} Hz ({midi_like_note(p.frequency):>3})  "
                f"A {p.attack:.3f}  D {p.decay:.3f}  S {p.sustain:.0f}%  R {p.release:.2f}  "
                f"LFO {p.lfo_rate:.2f}/{p.lfo_depth:.0f}%  density {p.density:.1f}/s  master {p.master:.0f}%"
            )
        except Exception:
            pass
        self.after(250, self.refresh_readout)

    def play(self) -> None:
        p = self.current_patch()
        self.status.set("Rendering procedural audio…")
        def worker() -> None:
            try:
                self.engine.play(p)
                self.after(0, lambda: self.status.set(f"Playing {p.mode} — {p.frequency:.1f} Hz / {p.waveform}"))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("BloomTunes", str(exc)))
                self.after(0, lambda: self.status.set("Playback error"))
        threading.Thread(target=worker, daemon=True).start()

    def stop(self) -> None:
        self.engine.stop()
        self.status.set("Stopped")

    def next_solfeggio(self) -> None:
        current = float(self.vars["frequency"].get())
        nxt = next((f for f in SOLFEGGIO if f > current + 0.5), SOLFEGGIO[0])
        self.vars["frequency"].set(nxt)
        self.status.set(f"Solfeggio: {nxt:.0f} Hz")

    def randomize(self) -> None:
        p = self.current_patch()
        p.frequency = random.choice(SOLFEGGIO)
        p.waveform = random.choice(["SINE", "TRIANGLE", "SAW"])
        p.detune_cents = random.randint(-18, 18)
        p.harmonics = random.randint(1, 5)
        p.harmonic_falloff = random.randint(35, 80)
        p.attack = random.uniform(0.005, 0.8)
        p.release = random.uniform(0.08, 1.6)
        p.lfo_rate = random.uniform(0.03, 1.2)
        p.lfo_depth = random.randint(0, 45)
        p.vibrato_depth = random.randint(0, 20)
        p.noise = random.randint(0, 20)
        p.density = random.uniform(0.7, 7.0)
        p.randomness = random.randint(20, 90)
        p.seed = random.randint(0, 9999)
        self.load_patch(p)
        self.status.set("Randomized — press PLAY")

    def save_patch(self) -> None:
        path = filedialog.asksaveasfilename(title="Save BloomTunes patch", defaultextension=".json", filetypes=[("BloomTunes patch", "*.json")])
        if not path:
            return
        Path(path).write_text(json.dumps(asdict(self.current_patch()), indent=2) + "\n", encoding="utf-8")
        self.status.set(f"Saved {Path(path).name}")

    def open_patch(self) -> None:
        path = filedialog.askopenfilename(title="Load BloomTunes patch", filetypes=[("BloomTunes patch", "*.json"), ("JSON", "*.json")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            defaults = asdict(Patch())
            defaults.update({k: v for k, v in data.items() if k in defaults})
            self.load_patch(Patch(**defaults))
            self.status.set(f"Loaded {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("BloomTunes", f"Could not load patch:\n{exc}")

    def on_close(self) -> None:
        self.engine.stop()
        self.destroy()


if __name__ == "__main__":
    BloomTunesApp().mainloop()
