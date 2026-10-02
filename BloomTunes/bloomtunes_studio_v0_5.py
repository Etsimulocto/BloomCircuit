#!/usr/bin/env python3
"""BloomTunes Studio v0.5 — adds long-form Meditation Mode to v0.4.

Keeps the proven v0.4 sequencer intact and layers a compact meditation builder
on top. Meditation output is always mono.
"""
from __future__ import annotations

import math, os, shutil, struct, subprocess, tempfile, threading, wave
import tkinter as tk
from tkinter import ttk, messagebox

import bloomtunes_studio as base

SR = base.SR

MEDITATION_PRESETS = {
    "100 → 528 / 5m": (100.0, 528.0, 5.0, "SINE", 32.0, "LINEAR"),
    "174 → 528 / 10m": (174.0, 528.0, 10.0, "SINE", 28.0, "LOG"),
    "396 → 963 / 8m": (396.0, 963.0, 8.0, "SINE", 26.0, "LOG"),
    "528 Hold / 10m": (528.0, 528.0, 10.0, "SINE", 24.0, "LINEAR"),
    "Low Calm 80 → 174 / 5m": (80.0, 174.0, 5.0, "SINE", 30.0, "LOG"),
    "Deep Rise 55 → 285 / 10m": (55.0, 285.0, 10.0, "TRIANGLE", 24.0, "LOG"),
}


def clamp(x, lo=-1.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


class MeditationEngine:
    def __init__(self):
        self.process = None
        self.path = None
        self.lock = threading.Lock()

    @staticmethod
    def osc(kind: str, phase: float) -> float:
        p = phase % 1.0
        if kind == "SINE":
            return math.sin(2.0 * math.pi * p)
        if kind == "TRIANGLE":
            return 4.0 * abs(p - 0.5) - 1.0
        if kind == "SAW":
            return 2.0 * p - 1.0
        if kind == "SQUARE":
            return 1.0 if p < 0.5 else -1.0
        return math.sin(2.0 * math.pi * p)

    def stop(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
            self.process = None
            if self.path:
                try:
                    os.unlink(self.path)
                except OSError:
                    pass
                self.path = None

    def render_wav(self, start_hz: float, end_hz: float, minutes: float,
                   waveform: str, volume: float, curve: str,
                   fx: base.MasterFX, path: str):
        seconds = max(1.0, minutes * 60.0)
        total = int(seconds * SR)
        phase = 0.0
        attack = min(3.0, seconds * 0.05)
        release = min(5.0, seconds * 0.08)
        master = clamp((volume / 100.0) * (fx.master / 100.0), 0.0, 1.0)
        drive = max(0.0, fx.drive)
        trem_d = clamp(fx.trem_depth / 100.0, 0.0, 1.0)
        trem_r = max(0.0, fx.trem_rate)
        pwm_d = clamp(fx.pwm_depth / 100.0, 0.0, 1.0)
        pwm_r = max(0.0, fx.pwm_rate)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            frames = bytearray()
            for i in range(total):
                t = i / SR
                u = i / max(1, total - 1)
                if curve == "LOG" and start_hz > 0 and end_hz > 0:
                    freq = start_hz * ((end_hz / start_hz) ** u)
                else:
                    freq = start_hz + (end_hz - start_hz) * u
                phase += freq / SR
                env = min(1.0, t / max(attack, 1e-6)) * min(1.0, (seconds - t) / max(release, 1e-6))
                s = self.osc(waveform, phase) * env
                if trem_d > 0.0 and trem_r > 0.0:
                    s *= 1.0 - trem_d * (0.5 + 0.5 * math.sin(2 * math.pi * trem_r * t))
                if pwm_d > 0.0 and pwm_r > 0.0:
                    s *= 1.0 if (t * pwm_r) % 1.0 < 0.5 else 1.0 - pwm_d
                if drive > 0.1:
                    g = 1.0 + drive / 8.0
                    s = math.tanh(s * g) / max(1e-6, math.tanh(g))
                s = clamp(s * master)
                frames.extend(struct.pack("<h", int(s * 32767)))
                if len(frames) >= 131072:
                    wf.writeframesraw(frames)
                    frames.clear()
            if frames:
                wf.writeframesraw(frames)

    @staticmethod
    def player(path):
        players = [
            ("aplay", ["aplay", "-q", path]),
            ("paplay", ["paplay", path]),
            ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]),
        ]
        return next((cmd for exe, cmd in players if shutil.which(exe)), None)

    def play(self, *args):
        self.stop()
        fd, path = tempfile.mkstemp(prefix="bloom_meditation_", suffix=".wav")
        os.close(fd)
        self.render_wav(*args, path)
        cmd = self.player(path)
        if not cmd:
            os.unlink(path)
            raise RuntimeError("No audio player found (aplay, paplay, ffplay)")
        with self.lock:
            self.path = path
            self.process = subprocess.Popen(cmd)


class Studio(base.Studio):
    def __init__(self):
        super().__init__()
        self.title("BloomTunes Studio v0.5 — Sequencer + Meditation Mode")
        self.med_engine = MeditationEngine()
        self._build_meditation_panel()

    def _build_meditation_panel(self):
        panel = ttk.Frame(self, style="Panel.TFrame", padding=6)
        panel.place(relx=1.0, x=-10, y=48, anchor="ne")

        ttk.Label(panel, text="MEDITATION MODE", style="Panel.TLabel",
                  font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, columnspan=8, sticky="w")

        self.med_start = tk.DoubleVar(value=100.0)
        self.med_end = tk.DoubleVar(value=528.0)
        self.med_minutes = tk.DoubleVar(value=5.0)
        self.med_volume = tk.DoubleVar(value=32.0)
        self.med_wave = tk.StringVar(value="SINE")
        self.med_curve = tk.StringVar(value="LINEAR")
        self.med_preset = tk.StringVar(value="100 → 528 / 5m")

        ttk.Label(panel, text="START Hz", style="Panel.TLabel").grid(row=1, column=0)
        ttk.Entry(panel, width=7, textvariable=self.med_start).grid(row=1, column=1, padx=2)
        ttk.Label(panel, text="END Hz", style="Panel.TLabel").grid(row=1, column=2)
        ttk.Entry(panel, width=7, textvariable=self.med_end).grid(row=1, column=3, padx=2)
        ttk.Label(panel, text="MIN", style="Panel.TLabel").grid(row=1, column=4)
        ttk.Entry(panel, width=5, textvariable=self.med_minutes).grid(row=1, column=5, padx=2)
        ttk.Label(panel, text="VOL", style="Panel.TLabel").grid(row=1, column=6)
        ttk.Entry(panel, width=5, textvariable=self.med_volume).grid(row=1, column=7, padx=2)

        ttk.Combobox(panel, width=9, state="readonly", values=["SINE", "TRIANGLE", "SAW", "SQUARE"], textvariable=self.med_wave).grid(row=2, column=0, columnspan=2, padx=2, pady=(4,0))
        ttk.Combobox(panel, width=8, state="readonly", values=["LINEAR", "LOG"], textvariable=self.med_curve).grid(row=2, column=2, columnspan=2, padx=2, pady=(4,0))
        ttk.Combobox(panel, width=19, state="readonly", values=list(MEDITATION_PRESETS), textvariable=self.med_preset).grid(row=2, column=4, columnspan=2, padx=2, pady=(4,0))
        ttk.Button(panel, text="LOAD", command=self.load_med_preset).grid(row=2, column=6, padx=2, pady=(4,0))
        ttk.Button(panel, text="PLAY", command=self.play_meditation).grid(row=2, column=7, padx=2, pady=(4,0))
        ttk.Button(panel, text="STOP MEDITATION", command=self.med_engine.stop).grid(row=3, column=4, columnspan=4, sticky="ew", pady=(4,0))

    def load_med_preset(self):
        s, e, m, w, v, c = MEDITATION_PRESETS[self.med_preset.get()]
        self.med_start.set(s); self.med_end.set(e); self.med_minutes.set(m)
        self.med_wave.set(w); self.med_volume.set(v); self.med_curve.set(c)
        self.status.set(f"Meditation preset: {self.med_preset.get()}")

    def play_meditation(self):
        try:
            start = float(self.med_start.get()); end = float(self.med_end.get())
            minutes = float(self.med_minutes.get()); volume = float(self.med_volume.get())
            if not (1 <= start <= 20000 and 1 <= end <= 20000):
                raise ValueError("Start/end frequency must be 1–20000 Hz")
            if not (0.05 <= minutes <= 180):
                raise ValueError("Meditation time must be 0.05–180 minutes")
            if not (0 <= volume <= 100):
                raise ValueError("Volume must be 0–100")
        except Exception as ex:
            messagebox.showerror("BloomTunes Meditation", str(ex)); return

        self.sync_fx()
        fx = base.MasterFX(**base.asdict(self.song.fx))
        self.status.set(f"Rendering meditation {start:g} → {end:g} Hz / {minutes:g} min...")

        def worker():
            try:
                self.med_engine.play(start, end, minutes, self.med_wave.get(), volume,
                                     self.med_curve.get(), fx)
                self.after(0, lambda: self.status.set(
                    f"Meditation playing — {start:g} → {end:g} Hz / {minutes:g} min / MONO"))
            except Exception as ex:
                self.after(0, lambda: messagebox.showerror("BloomTunes Meditation", str(ex)))
        threading.Thread(target=worker, daemon=True).start()

    def close(self):
        self.med_engine.stop()
        super().close()


if __name__ == "__main__":
    Studio().mainloop()
