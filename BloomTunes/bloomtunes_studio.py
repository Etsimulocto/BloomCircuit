#!/usr/bin/env python3
"""BloomTunes Studio v0.3

Dark-mode, Pi-first, sample-free mono synth sequencer for HAPPY JARZ.
Eight procedural synth tracks -> one mono master bus -> effects -> mono WAV.
No third-party Python packages required.
"""
from __future__ import annotations

import json, math, os, random, shutil, struct, subprocess, tempfile, threading, wave
from dataclasses import dataclass, asdict, field
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

SR = 44100
STEPS = 16
ROWS = 24
BASE_MIDI = 48  # C3..B4
SOLFEGGIO = [174.0, 285.0, 396.0, 417.0, 528.0, 639.0, 741.0, 852.0, 963.0]

BG = "#111318"; PANEL = "#1a1d24"; PANEL2 = "#222631"; GRID = "#2d3240"
TEXT = "#e8eaf0"; MUTED = "#8f98aa"; ACCENT = "#70d6ff"; NOTE = "#ff70a6"; PLAY = "#ffd670"
TRACK_COLORS = ["#70d6ff", "#ff70a6", "#ffd670", "#7bf1a8", "#b388ff", "#ff9f68", "#7ee8fa", "#f7aef8"]


def clamp(x, lo=-1.0, hi=1.0): return lo if x < lo else hi if x > hi else x

def midi_hz(n: int) -> float: return 440.0 * (2.0 ** ((n - 69) / 12.0))

def midi_name(n: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[n % 12]}{n // 12 - 1}"

@dataclass
class Note:
    step: int
    row: int
    length: int = 1
    velocity: float = 0.8

@dataclass
class Track:
    name: str = "Track"
    waveform: str = "SINE"
    volume: float = 65.0
    octave: int = 0
    pulse_width: float = 50.0
    attack: float = 0.01
    release: float = 0.18
    mute: bool = False
    notes: list[Note] = field(default_factory=list)

@dataclass
class MasterFX:
    master: float = 45.0
    low: float = 0.0
    mid: float = 0.0
    high: float = 0.0
    drive: float = 0.0
    pwm_rate: float = 0.0
    pwm_depth: float = 0.0
    phaser_rate: float = 0.0
    phaser_depth: float = 0.0
    echo_ms: float = 0.0
    echo_mix: float = 0.0
    lowpass: float = 100.0
    highpass: float = 0.0

@dataclass
class Song:
    bpm: float = 90.0
    bars: int = 1
    tracks: list[Track] = field(default_factory=list)
    fx: MasterFX = field(default_factory=MasterFX)


def default_song() -> Song:
    waves = ["SINE", "SQUARE", "TRIANGLE", "SAW", "SINE", "TRIANGLE", "SQUARE", "SINE"]
    return Song(tracks=[Track(name=f"T{i+1}", waveform=waves[i]) for i in range(8)])

class Engine:
    def __init__(self):
        self.process = None; self.path = None; self.lock = threading.Lock()

    @staticmethod
    def osc(kind: str, phase: float, pw: float) -> float:
        p = phase % 1.0
        if kind == "SINE": return math.sin(2*math.pi*p)
        if kind == "SQUARE": return 1.0 if p < pw/100.0 else -1.0
        if kind == "TRIANGLE": return 4.0*abs(p-0.5)-1.0
        if kind == "SAW": return 2.0*p-1.0
        return random.uniform(-1,1)

    def note(self, tr: Track, freq: float, seconds: float, vel: float) -> list[float]:
        n = max(1, int(seconds*SR)); out = [0.0]*n; phase = 0.0
        a = max(0.001, min(tr.attack, seconds*0.4)); r = max(0.001, min(tr.release, seconds*0.7))
        for i in range(n):
            t = i/SR; phase += freq/SR
            env = min(1.0, t/a) * min(1.0, (seconds-t)/r)
            out[i] = self.osc(tr.waveform, phase, tr.pulse_width) * env * vel
        return out

    @staticmethod
    def add(dst, src, start, gain=1.0):
        for i,x in enumerate(src):
            j = start+i
            if j >= len(dst): break
            dst[j] += x*gain

    @staticmethod
    def onepole_low(samples, alpha):
        y=0.0; out=[]
        for x in samples:
            y += alpha*(x-y); out.append(y)
        return out

    @staticmethod
    def onepole_high(samples, alpha):
        if not samples: return []
        px=samples[0]; py=0.0; out=[]
        for x in samples:
            y = alpha*(py+x-px); out.append(y); px=x; py=y
        return out

    def effects(self, mono: list[float], fx: MasterFX) -> list[float]:
        out = mono[:]
        # Simple three-band tone shaping: derive low and high bands, leave remainder as mid.
        if out and (abs(fx.low)>0.1 or abs(fx.mid)>0.1 or abs(fx.high)>0.1):
            low = self.onepole_low(out, 0.015)
            high = self.onepole_high(out, 0.93)
            lg = 10**(fx.low/20); mg = 10**(fx.mid/20); hg = 10**(fx.high/20)
            out = [clamp(low[i]*lg + (out[i]-low[i]-high[i])*mg + high[i]*hg) for i in range(len(out))]
        if fx.lowpass < 99.9:
            alpha = 0.002 + (fx.lowpass/100.0)**2*0.45
            out = self.onepole_low(out, alpha)
        if fx.highpass > 0.1:
            alpha = 0.995 - min(0.35, fx.highpass/300.0)
            out = self.onepole_high(out, alpha)
        if fx.drive > 0.1:
            g = 1.0 + fx.drive/9.0
            norm = math.tanh(g)
            out = [math.tanh(x*g)/norm for x in out]
        # PWM-style amplitude chop on the final mono bus.
        if fx.pwm_depth > 0.1 and fx.pwm_rate > 0.01:
            d = fx.pwm_depth/100.0
            for i,x in enumerate(out):
                t=i/SR; gate = 1.0 if (t*fx.pwm_rate)%1.0 < 0.5 else 1.0-d
                out[i]=x*gate
        # Lightweight phaser: modulated short delay mixed against dry signal.
        if fx.phaser_depth > 0.1 and fx.phaser_rate > 0.01:
            dry=out[:]; depth=fx.phaser_depth/100.0
            maxd=max(2,int(0.004*SR))
            for i in range(len(out)):
                lfo=0.5+0.5*math.sin(2*math.pi*fx.phaser_rate*i/SR)
                d=1+int(lfo*maxd)
                wet=dry[i-d] if i>=d else 0.0
                out[i]=clamp(dry[i]*(1-0.45*depth)+wet*(0.45*depth))
        if fx.echo_mix > 0.1 and fx.echo_ms > 1:
            delay=int(fx.echo_ms*SR/1000.0); mix=fx.echo_mix/100.0
            dry=out[:]
            for i in range(delay,len(out)):
                out[i]=clamp(out[i]+dry[i-delay]*0.55*mix)
        gain = fx.master/100.0
        peak=max((abs(x) for x in out), default=1.0)
        if peak>1.0: out=[x/peak for x in out]
        return [clamp(x*gain) for x in out]

    def render(self, song: Song) -> list[float]:
        beat=60.0/max(30.0,song.bpm); step_sec=beat/4.0
        total=step_sec*STEPS*max(1,song.bars)
        mono=[0.0]*int(total*SR)
        for tr in song.tracks:
            if tr.mute: continue
            for note in tr.notes:
                start = int(note.step*step_sec*SR)
                dur = max(step_sec*0.2, note.length*step_sec)
                midi = BASE_MIDI + (ROWS-1-note.row) + 12*tr.octave
                src = self.note(tr, midi_hz(midi), dur, note.velocity)
                self.add(mono, src, start, tr.volume/100.0)
        return self.effects(mono, song.fx)

    @staticmethod
    def write_wav(mono, path):
        with wave.open(path,"wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
            frames=bytearray()
            for x in mono: frames.extend(struct.pack("<h", int(clamp(x)*32767)))
            wf.writeframes(frames)

    def stop(self):
        with self.lock:
            if self.process and self.process.poll() is None: self.process.terminate()
            self.process=None
            if self.path:
                try: os.unlink(self.path)
                except OSError: pass
                self.path=None

    def play(self, song: Song):
        self.stop(); mono=self.render(song)
        fd,path=tempfile.mkstemp(prefix="bloomtunes_studio_",suffix=".wav"); os.close(fd)
        self.write_wav(mono,path)
        candidates=[("aplay",["aplay","-q",path]),("paplay",["paplay",path]),("ffplay",["ffplay","-nodisp","-autoexit","-loglevel","quiet",path])]
        cmd=next((c for e,c in candidates if shutil.which(e)),None)
        if not cmd: raise RuntimeError("No audio player found: install/use aplay, paplay, or ffplay")
        with self.lock: self.path=path; self.process=subprocess.Popen(cmd)

class Studio(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("BloomTunes Studio — 8 Track Mono Synth")
        self.geometry("1380x880"); self.minsize(1120,720); self.configure(bg=BG)
        self.engine=Engine(); self.song=default_song(); self.track_index=0; self.note_len=1
        self.cell_w=44; self.cell_h=22; self.label_w=52
        self.status=tk.StringVar(value="Ready — 8 tracks → mono master")
        self._style(); self._build(); self.redraw(); self.protocol("WM_DELETE_WINDOW", self.close)

    def _style(self):
        s=ttk.Style(self); s.theme_use("clam")
        s.configure("TFrame",background=BG); s.configure("Panel.TFrame",background=PANEL)
        s.configure("TLabel",background=BG,foreground=TEXT); s.configure("Panel.TLabel",background=PANEL,foreground=TEXT)
        s.configure("Title.TLabel",background=BG,foreground=ACCENT,font=("TkDefaultFont",20,"bold"))
        s.configure("TButton",background=PANEL2,foreground=TEXT,padding=6); s.map("TButton",background=[("active","#343a49")])
        s.configure("TCombobox",fieldbackground=PANEL2,background=PANEL2,foreground=TEXT)
        s.configure("Horizontal.TScale",background=PANEL)
        s.configure("TCheckbutton",background=PANEL,foreground=TEXT)

    def _build(self):
        head=ttk.Frame(self,padding=10); head.pack(fill="x")
        ttk.Label(head,text="BloomTunes Studio",style="Title.TLabel").pack(side="left")
        ttk.Label(head,text="sample-free • 8 tracks • forced mono",foreground=MUTED).pack(side="left",padx=14)
        ttk.Button(head,text="PLAY",command=self.play).pack(side="right",padx=4)
        ttk.Button(head,text="STOP",command=self.engine.stop).pack(side="right",padx=4)
        ttk.Button(head,text="SAVE",command=self.save).pack(side="right",padx=4)
        ttk.Button(head,text="LOAD",command=self.load).pack(side="right",padx=4)

        control=ttk.Frame(self,style="Panel.TFrame",padding=8); control.pack(fill="x",padx=10)
        self.bpm=tk.DoubleVar(value=self.song.bpm); self.length=tk.IntVar(value=1)
        ttk.Label(control,text="BPM",style="Panel.TLabel").pack(side="left")
        ttk.Spinbox(control,from_=30,to=240,width=6,textvariable=self.bpm,command=self.sync).pack(side="left",padx=(4,12))
        ttk.Label(control,text="NOTE SIZE",style="Panel.TLabel").pack(side="left")
        cb=ttk.Combobox(control,width=8,state="readonly",values=["1/16","1/8","3/16","1/4"],textvariable=tk.StringVar(value="1/16")); cb.pack(side="left",padx=4)
        cb.bind("<<ComboboxSelected>>",lambda e:self.set_len(cb.get()))
        ttk.Button(control,text="CLEAR TRACK",command=self.clear_track).pack(side="left",padx=12)
        ttk.Button(control,text="CLEAR ALL",command=self.clear_all).pack(side="left")
        ttk.Label(control,textvariable=self.status,style="Panel.TLabel").pack(side="right")

        tracks=ttk.Frame(self,padding=(10,8)); tracks.pack(fill="x")
        self.track_buttons=[]
        for i in range(8):
            b=tk.Button(tracks,text=f"T{i+1}",bg=TRACK_COLORS[i],fg="#101216",relief="flat",padx=12,pady=6,command=lambda i=i:self.select_track(i))
            b.pack(side="left",padx=3); self.track_buttons.append(b)

        strip=ttk.Frame(self,style="Panel.TFrame",padding=8); strip.pack(fill="x",padx=10)
        self.wave=tk.StringVar(value="SINE"); self.vol=tk.DoubleVar(value=65); self.oct=tk.IntVar(value=0); self.pw=tk.DoubleVar(value=50); self.attack=tk.DoubleVar(value=.01); self.release=tk.DoubleVar(value=.18); self.mute=tk.BooleanVar(value=False)
        ttk.Label(strip,text="TRACK",style="Panel.TLabel").pack(side="left",padx=(0,6))
        ttk.Combobox(strip,width=9,state="readonly",values=["SINE","SQUARE","TRIANGLE","SAW","NOISE"],textvariable=self.wave).pack(side="left",padx=3)
        self._slider(strip,"VOL",self.vol,0,100,110); self._slider(strip,"PWM",self.pw,5,95,100); self._slider(strip,"ATT",self.attack,.001,1,90); self._slider(strip,"REL",self.release,.01,2,90)
        ttk.Label(strip,text="OCT",style="Panel.TLabel").pack(side="left",padx=(8,2)); ttk.Spinbox(strip,from_=-2,to=2,width=4,textvariable=self.oct).pack(side="left")
        ttk.Checkbutton(strip,text="MUTE",variable=self.mute).pack(side="left",padx=10)
        ttk.Button(strip,text="APPLY",command=self.apply_track).pack(side="left",padx=4)

        mid=ttk.Frame(self,padding=10); mid.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(mid,bg="#0d0f13",highlightthickness=0)
        xs=ttk.Scrollbar(mid,orient="horizontal",command=self.canvas.xview); ys=ttk.Scrollbar(mid,orient="vertical",command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xs.set,yscrollcommand=ys.set)
        self.canvas.grid(row=0,column=0,sticky="nsew"); ys.grid(row=0,column=1,sticky="ns"); xs.grid(row=1,column=0,sticky="ew")
        mid.rowconfigure(0,weight=1); mid.columnconfigure(0,weight=1)
        self.canvas.bind("<Button-1>",self.grid_click)

        fx=ttk.Frame(self,style="Panel.TFrame",padding=8); fx.pack(fill="x",padx=10,pady=(0,10))
        self.fxvars={}
        fxspec=[("MASTER",45,0,100),("LOW",0,-12,12),("MID",0,-12,12),("HIGH",0,-12,12),("DRIVE",0,0,100),("PWM RATE",0,0,20),("PWM DEPTH",0,0,100),("PHASER RATE",0,0,8),("PHASER DEPTH",0,0,100),("ECHO ms",0,0,700),("ECHO MIX",0,0,70),("LP",100,0,100),("HP",0,0,100)]
        for name,val,lo,hi in fxspec:
            v=tk.DoubleVar(value=val); self.fxvars[name]=v; self._slider(fx,name,v,lo,hi,82)

    def _slider(self,parent,name,var,lo,hi,width):
        box=ttk.Frame(parent,style="Panel.TFrame"); box.pack(side="left",padx=3)
        ttk.Label(box,text=name,style="Panel.TLabel",font=("TkDefaultFont",8)).pack()
        ttk.Scale(box,from_=lo,to=hi,variable=var,orient="horizontal",length=width).pack()

    def set_len(self,text): self.note_len={"1/16":1,"1/8":2,"3/16":3,"1/4":4}[text]
    def sync(self): self.song.bpm=float(self.bpm.get())

    def select_track(self,i):
        self.apply_track(); self.track_index=i; tr=self.song.tracks[i]
        self.wave.set(tr.waveform); self.vol.set(tr.volume); self.oct.set(tr.octave); self.pw.set(tr.pulse_width); self.attack.set(tr.attack); self.release.set(tr.release); self.mute.set(tr.mute); self.redraw()

    def apply_track(self):
        tr=self.song.tracks[self.track_index]; tr.waveform=self.wave.get(); tr.volume=float(self.vol.get()); tr.octave=int(self.oct.get()); tr.pulse_width=float(self.pw.get()); tr.attack=float(self.attack.get()); tr.release=float(self.release.get()); tr.mute=bool(self.mute.get())

    def sync_fx(self):
        f=self.song.fx; m=self.fxvars
        f.master=m["MASTER"].get(); f.low=m["LOW"].get(); f.mid=m["MID"].get(); f.high=m["HIGH"].get(); f.drive=m["DRIVE"].get(); f.pwm_rate=m["PWM RATE"].get(); f.pwm_depth=m["PWM DEPTH"].get(); f.phaser_rate=m["PHASER RATE"].get(); f.phaser_depth=m["PHASER DEPTH"].get(); f.echo_ms=m["ECHO ms"].get(); f.echo_mix=m["ECHO MIX"].get(); f.lowpass=m["LP"].get(); f.highpass=m["HP"].get()

    def redraw(self):
        c=self.canvas; c.delete("all"); W=self.label_w+STEPS*self.cell_w; H=ROWS*self.cell_h
        c.configure(scrollregion=(0,0,W,H+24))
        tr=self.song.tracks[self.track_index]
        for r in range(ROWS):
            y=r*self.cell_h; midi=BASE_MIDI+(ROWS-1-r)+12*tr.octave
            black=(midi%12) in {1,3,6,8,10}; bg="#151821" if black else "#1b1f29"
            c.create_rectangle(0,y,W,y+self.cell_h,fill=bg,outline=GRID)
            c.create_text(self.label_w-5,y+self.cell_h/2,text=midi_name(midi),fill=MUTED,anchor="e",font=("TkDefaultFont",8))
        for s in range(STEPS+1):
            x=self.label_w+s*self.cell_w; col="#586174" if s%4==0 else GRID
            c.create_line(x,0,x,H,fill=col,width=2 if s%4==0 else 1)
            if s<STEPS: c.create_text(x+4,10,text=str(s+1),fill=MUTED,anchor="nw",font=("TkDefaultFont",7))
        color=TRACK_COLORS[self.track_index]
        for n in tr.notes:
            x=self.label_w+n.step*self.cell_w+2; y=n.row*self.cell_h+2; w=max(1,n.length)*self.cell_w-4
            c.create_rectangle(x,y,x+w,y+self.cell_h-4,fill=color,outline="",tags="note")

    def grid_click(self,e):
        x=self.canvas.canvasx(e.x); y=self.canvas.canvasy(e.y)
        if x<self.label_w or y<0: return
        step=int((x-self.label_w)//self.cell_w); row=int(y//self.cell_h)
        if not (0<=step<STEPS and 0<=row<ROWS): return
        tr=self.song.tracks[self.track_index]
        hit=next((n for n in tr.notes if n.row==row and n.step<=step<n.step+n.length),None)
        if hit: tr.notes.remove(hit)
        else:
            tr.notes=[n for n in tr.notes if not (n.step==step and n.row==row)]
            tr.notes.append(Note(step=step,row=row,length=min(self.note_len,STEPS-step)))
        self.redraw()

    def clear_track(self): self.song.tracks[self.track_index].notes.clear(); self.redraw()
    def clear_all(self):
        for t in self.song.tracks: t.notes.clear()
        self.redraw()

    def play(self):
        self.apply_track(); self.sync(); self.sync_fx(); self.status.set("Rendering mono mix...")
        def worker():
            try: self.engine.play(self.song); self.after(0,lambda:self.status.set("Playing — MONO"))
            except Exception as ex: self.after(0,lambda:messagebox.showerror("BloomTunes",str(ex)))
        threading.Thread(target=worker,daemon=True).start()

    def song_dict(self):
        self.apply_track(); self.sync(); self.sync_fx(); return asdict(self.song)

    def save(self):
        p=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("BloomTunes song","*.json")])
        if not p:return
        Path(p).write_text(json.dumps(self.song_dict(),indent=2)); self.status.set(f"Saved {Path(p).name}")

    def load(self):
        p=filedialog.askopenfilename(filetypes=[("BloomTunes song","*.json")])
        if not p:return
        try:
            d=json.loads(Path(p).read_text()); tracks=[]
            for td in d.get("tracks",[]):
                notes=[Note(**n) for n in td.pop("notes",[])]; tr=Track(**td); tr.notes=notes; tracks.append(tr)
            while len(tracks)<8: tracks.append(Track(name=f"T{len(tracks)+1}"))
            self.song=Song(bpm=d.get("bpm",90),bars=d.get("bars",1),tracks=tracks[:8],fx=MasterFX(**d.get("fx",{})))
            self.bpm.set(self.song.bpm); self.track_index=0
            f=self.song.fx
            vals={"MASTER":f.master,"LOW":f.low,"MID":f.mid,"HIGH":f.high,"DRIVE":f.drive,"PWM RATE":f.pwm_rate,"PWM DEPTH":f.pwm_depth,"PHASER RATE":f.phaser_rate,"PHASER DEPTH":f.phaser_depth,"ECHO ms":f.echo_ms,"ECHO MIX":f.echo_mix,"LP":f.lowpass,"HP":f.highpass}
            for k,v in vals.items(): self.fxvars[k].set(v)
            self.select_track(0); self.status.set(f"Loaded {Path(p).name}")
        except Exception as ex: messagebox.showerror("BloomTunes",str(ex))

    def close(self): self.engine.stop(); self.destroy()

if __name__ == "__main__": Studio().mainloop()
