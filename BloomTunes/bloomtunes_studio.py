#!/usr/bin/env python3
"""BloomTunes Studio v0.4

Dark-mode, Pi-first, sample-free mono synth workstation for HAPPY JARZ.
Eight procedural synth tracks -> forced mono master bus -> FX -> mono WAV.
Stores up to 256 bars. The editor/playback view is four bars (64 sixteenth steps)
at a time so editing stays responsive on Raspberry Pi.
No third-party Python packages required.
"""
from __future__ import annotations

import json, math, os, random, shutil, struct, subprocess, tempfile, threading, wave
from dataclasses import dataclass, asdict, field
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

SR = 44100
STEPS_PER_BAR = 16
VIEW_BARS = 4
VIEW_STEPS = STEPS_PER_BAR * VIEW_BARS
MAX_BARS = 256
MIDI_LOW = 21      # A0
MIDI_HIGH = 108    # C8
ROWS = MIDI_HIGH - MIDI_LOW + 1

BG="#0e1015"; PANEL="#171a21"; PANEL2="#202530"; GRID="#303644"; TEXT="#edf0f6"; MUTED="#8e97aa"
ACCENT="#76d7ff"; PLAY="#ffd166"; TRACK_COLORS=["#76d7ff","#ff74a8","#ffd166","#7ee6a8","#b794ff","#ff9d66","#78e7ef","#f0a7ff"]


def clamp(x, lo=-1.0, hi=1.0): return lo if x < lo else hi if x > hi else x

def midi_hz(n): return 440.0 * (2.0 ** ((n-69)/12.0))
def midi_name(n):
    names=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
    return f"{names[n%12]}{n//12-1}"

@dataclass
class Note:
    step:int
    midi:int
    length:int=1
    velocity:float=.82

@dataclass
class Track:
    name:str="Track"
    waveform:str="SINE"
    volume:float=65.0
    pulse_width:float=50.0
    attack:float=.01
    release:float=.18
    detune:float=0.0
    harmonics:int=1
    mute:bool=False
    notes:list[Note]=field(default_factory=list)

@dataclass
class MasterFX:
    master:float=45.0
    drive:float=0.0
    # parametric-ish EQ bands
    eq1_freq:float=120.0; eq1_q:float=.8; eq1_gain:float=0.0
    eq2_freq:float=900.0; eq2_q:float=1.0; eq2_gain:float=0.0
    eq3_freq:float=5000.0; eq3_q:float=.8; eq3_gain:float=0.0
    # dynamics
    comp_threshold:float=-12.0; comp_ratio:float=2.0; comp_attack:float=.015; comp_release:float=.18; comp_makeup:float=0.0
    # modulation
    trem_rate:float=0.0; trem_depth:float=0.0
    pwm_rate:float=0.0; pwm_depth:float=0.0
    phaser_rate:float=0.0; phaser_depth:float=0.0
    # delay/filter
    echo_ms:float=0.0; echo_mix:float=0.0
    lowpass_hz:float=18000.0; highpass_hz:float=20.0

@dataclass
class Song:
    bpm:float=90.0
    bars:int=4
    tracks:list[Track]=field(default_factory=list)
    fx:MasterFX=field(default_factory=MasterFX)


def default_song():
    waves=["SINE","SQUARE","TRIANGLE","SAW","SINE","TRIANGLE","SQUARE","SINE"]
    return Song(tracks=[Track(name=f"T{i+1}",waveform=waves[i]) for i in range(8)])

INSTRUMENT_PATCHES={
    "Pure Sine":dict(waveform="SINE",volume=62,pulse_width=50,attack=.01,release=.22,detune=0,harmonics=1),
    "Soft Bell":dict(waveform="SINE",volume=58,pulse_width=50,attack=.003,release=.65,detune=0,harmonics=3),
    "Warm Pad":dict(waveform="TRIANGLE",volume=52,pulse_width=50,attack=.35,release=.8,detune=-4,harmonics=3),
    "PWM Pluck":dict(waveform="SQUARE",volume=52,pulse_width=31,attack=.002,release=.16,detune=0,harmonics=1),
    "Glass":dict(waveform="TRIANGLE",volume=48,pulse_width=50,attack=.002,release=.38,detune=7,harmonics=4),
    "Bass":dict(waveform="SAW",volume=50,pulse_width=50,attack=.01,release=.15,detune=0,harmonics=2),
    "Noise Hit":dict(waveform="NOISE",volume=36,pulse_width=50,attack=.001,release=.09,detune=0,harmonics=1),
}

FX_PATCHES={
    "Clean":MasterFX(),
    "Soft Glow":MasterFX(master=46,eq1_gain=2,eq2_gain=-1,eq3_gain=2,comp_threshold=-16,comp_ratio=2.2,comp_makeup=1.5,lowpass_hz=14500),
    "Dream Phaser":MasterFX(master=42,eq1_gain=-1,eq2_gain=1.5,eq3_gain=2,phaser_rate=.22,phaser_depth=45,echo_ms=210,echo_mix=16),
    "Rain Wash":MasterFX(master=40,eq1_gain=-4,eq2_freq=1800,eq2_gain=2,eq3_gain=1,trem_rate=.12,trem_depth=12,echo_ms=95,echo_mix=9,highpass_hz=180,lowpass_hz=12500),
    "Deep Calm":MasterFX(master=44,eq1_freq=90,eq1_gain=4,eq2_freq=700,eq2_gain=-2,eq3_gain=-3,comp_threshold=-18,comp_ratio=2.6,lowpass_hz=8500),
    "Sparkle":MasterFX(master=42,eq1_gain=-3,eq2_freq=2200,eq2_gain=2,eq3_freq=7200,eq3_gain=4,phaser_rate=.55,phaser_depth=24,echo_ms=145,echo_mix=13),
    "Tremolo Pulse":MasterFX(master=42,trem_rate=4.0,trem_depth=58,comp_threshold=-14,comp_ratio=3),
    "Crunch":MasterFX(master=34,drive=34,eq1_gain=2,eq2_gain=3,eq3_gain=-2,comp_threshold=-18,comp_ratio=4,comp_makeup=2),
}

class Engine:
    def __init__(self): self.process=None; self.path=None; self.lock=threading.Lock()
    @staticmethod
    def osc(kind,phase,pw):
        p=phase%1.0
        if kind=="SINE": return math.sin(2*math.pi*p)
        if kind=="SQUARE": return 1.0 if p<pw/100.0 else -1.0
        if kind=="TRIANGLE": return 4*abs(p-.5)-1
        if kind=="SAW": return 2*p-1
        return random.uniform(-1,1)
    def note(self,tr,freq,seconds,vel):
        n=max(1,int(seconds*SR)); out=[0.0]*n; phase=0.0
        freq*=2**(tr.detune/1200.0); a=max(.001,min(tr.attack,seconds*.4)); r=max(.001,min(tr.release,seconds*.8))
        for i in range(n):
            t=i/SR; phase+=freq/SR; env=min(1,t/a)*min(1,(seconds-t)/r)
            s=0.0; w=1.0; tw=0.0
            for h in range(1,max(1,tr.harmonics)+1):
                s+=self.osc(tr.waveform,phase*h,tr.pulse_width)*w; tw+=w; w*=.55
            out[i]=(s/max(tw,.001))*env*vel
        return out
    @staticmethod
    def add(dst,src,start,gain=1.0):
        for i,x in enumerate(src):
            j=start+i
            if j>=len(dst): break
            if j>=0: dst[j]+=x*gain
    @staticmethod
    def onepole_low(samples,cut):
        cut=max(20,min(cut,20000)); dt=1/SR; rc=1/(2*math.pi*cut); a=dt/(rc+dt); y=0.0; out=[]
        for x in samples: y+=a*(x-y); out.append(y)
        return out
    @staticmethod
    def onepole_high(samples,cut):
        if not samples:return []
        cut=max(5,min(cut,18000)); dt=1/SR; rc=1/(2*math.pi*cut); a=rc/(rc+dt); px=samples[0]; py=0; out=[]
        for x in samples:
            y=a*(py+x-px); out.append(y); px=x; py=y
        return out
    def peq(self,samples,freq,q,gain_db):
        if abs(gain_db)<.05:return samples
        # lightweight peaking EQ biquad
        A=10**(gain_db/40); w0=2*math.pi*max(20,min(freq,20000))/SR; alpha=math.sin(w0)/(2*max(.15,q)); c=math.cos(w0)
        b0=1+alpha*A; b1=-2*c; b2=1-alpha*A; a0=1+alpha/A; a1=-2*c; a2=1-alpha/A
        b0/=a0; b1/=a0; b2/=a0; a1/=a0; a2/=a0
        x1=x2=y1=y2=0.0; out=[]
        for x in samples:
            y=b0*x+b1*x1+b2*x2-a1*y1-a2*y2; out.append(y); x2=x1; x1=x; y2=y1; y1=y
        return out
    def compressor(self,samples,fx):
        if fx.comp_ratio<=1.01:return samples
        th=10**(fx.comp_threshold/20); ratio=max(1,fx.comp_ratio); atk=math.exp(-1/(SR*max(.001,fx.comp_attack))); rel=math.exp(-1/(SR*max(.01,fx.comp_release))); env=0.0; out=[]; makeup=10**(fx.comp_makeup/20)
        for x in samples:
            a=abs(x); coeff=atk if a>env else rel; env=coeff*env+(1-coeff)*a
            if env>th and env>0:
                target=th*((env/th)**(1/ratio)); g=target/env
            else:g=1.0
            out.append(x*g*makeup)
        return out
    def effects(self,out,fx):
        out=self.peq(out,fx.eq1_freq,fx.eq1_q,fx.eq1_gain); out=self.peq(out,fx.eq2_freq,fx.eq2_q,fx.eq2_gain); out=self.peq(out,fx.eq3_freq,fx.eq3_q,fx.eq3_gain)
        if fx.highpass_hz>20.1: out=self.onepole_high(out,fx.highpass_hz)
        if fx.lowpass_hz<17999: out=self.onepole_low(out,fx.lowpass_hz)
        if fx.drive>.1:
            g=1+fx.drive/8; norm=math.tanh(g); out=[math.tanh(x*g)/norm for x in out]
        if fx.trem_depth>.1 and fx.trem_rate>.01:
            d=fx.trem_depth/100
            for i,x in enumerate(out): out[i]=x*(1-d*(.5+.5*math.sin(2*math.pi*fx.trem_rate*i/SR)))
        if fx.pwm_depth>.1 and fx.pwm_rate>.01:
            d=fx.pwm_depth/100
            for i,x in enumerate(out): out[i]=x*(1.0 if (i/SR*fx.pwm_rate)%1<.5 else 1-d)
        if fx.phaser_depth>.1 and fx.phaser_rate>.01:
            dry=out[:]; dep=fx.phaser_depth/100; maxd=max(2,int(.004*SR))
            for i in range(len(out)):
                l=.5+.5*math.sin(2*math.pi*fx.phaser_rate*i/SR); d=1+int(l*maxd); wet=dry[i-d] if i>=d else 0
                out[i]=dry[i]*(1-.45*dep)+wet*(.45*dep)
        if fx.echo_mix>.1 and fx.echo_ms>1:
            delay=int(fx.echo_ms*SR/1000); mix=fx.echo_mix/100; dry=out[:]
            for i in range(delay,len(out)): out[i]+=dry[i-delay]*.55*mix
        out=self.compressor(out,fx)
        peak=max((abs(x) for x in out),default=1)
        if peak>1: out=[x/peak for x in out]
        g=fx.master/100
        return [clamp(x*g) for x in out]
    def render_view(self,song,start_bar):
        beat=60/max(30,song.bpm); step_sec=beat/4; start_step=start_bar*STEPS_PER_BAR; end_step=start_step+VIEW_STEPS; total=VIEW_STEPS*step_sec
        mono=[0.0]*int(total*SR)
        for tr in song.tracks:
            if tr.mute:continue
            for n in tr.notes:
                if n.step>=end_step or n.step+n.length<=start_step:continue
                local=n.step-start_step; dur=max(step_sec*.2,n.length*step_sec); src=self.note(tr,midi_hz(n.midi),dur,n.velocity)
                self.add(mono,src,int(local*step_sec*SR),tr.volume/100)
        return self.effects(mono,song.fx)
    @staticmethod
    def write_wav(mono,path):
        with wave.open(path,"wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); frames=bytearray()
            for x in mono:frames.extend(struct.pack("<h",int(clamp(x)*32767)))
            wf.writeframes(frames)
    def _player(self,path):
        candidates=[("aplay",["aplay","-q",path]),("paplay",["paplay",path]),("ffplay",["ffplay","-nodisp","-autoexit","-loglevel","quiet",path])]
        return next((c for e,c in candidates if shutil.which(e)),None)
    def stop(self):
        with self.lock:
            if self.process and self.process.poll() is None:self.process.terminate()
            self.process=None
            if self.path:
                try:os.unlink(self.path)
                except OSError:pass
                self.path=None
    def play_view(self,song,start_bar):
        self.stop(); mono=self.render_view(song,start_bar); fd,path=tempfile.mkstemp(prefix="bloomtunes_",suffix=".wav");os.close(fd);self.write_wav(mono,path);cmd=self._player(path)
        if not cmd:raise RuntimeError("No audio player found (aplay, paplay, ffplay)")
        with self.lock:self.path=path;self.process=subprocess.Popen(cmd)
    def preview(self,tr,midi):
        src=self.note(tr,midi_hz(midi),.24,.85); src=[clamp(x*tr.volume/100) for x in src]; fd,path=tempfile.mkstemp(prefix="bloom_note_",suffix=".wav");os.close(fd);self.write_wav(src,path);cmd=self._player(path)
        if cmd:
            p=subprocess.Popen(cmd)
            def clean(): p.wait(); os.path.exists(path) and os.unlink(path)
            threading.Thread(target=clean,daemon=True).start()

class Studio(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("BloomTunes Studio v0.4 — 8 Track Mono Workstation"); self.geometry("1500x930"); self.minsize(1180,760); self.configure(bg=BG)
        self.engine=Engine(); self.song=default_song(); self.track_index=0; self.note_len=1; self.view_bar=0; self.cell_w=22; self.cell_h=18; self.label_w=58
        self.status=tk.StringVar(value="Ready — 8 tracks → forced mono master"); self._style(); self._build(); self.load_track_ui(); self.redraw(); self.protocol("WM_DELETE_WINDOW",self.close)
    def _style(self):
        s=ttk.Style(self); s.theme_use("clam"); s.configure("TFrame",background=BG); s.configure("Panel.TFrame",background=PANEL); s.configure("TLabel",background=BG,foreground=TEXT); s.configure("Panel.TLabel",background=PANEL,foreground=TEXT); s.configure("Title.TLabel",background=BG,foreground=ACCENT,font=("TkDefaultFont",20,"bold")); s.configure("TButton",background=PANEL2,foreground=TEXT,padding=5); s.map("TButton",background=[("active","#343b4a")]); s.configure("TCombobox",fieldbackground=PANEL2,background=PANEL2,foreground=TEXT); s.configure("TCheckbutton",background=PANEL,foreground=TEXT)
    def _slider(self,parent,name,var,lo,hi,width=100):
        box=ttk.Frame(parent,style="Panel.TFrame"); box.pack(side="left",padx=3); ttk.Label(box,text=name,style="Panel.TLabel",font=("TkDefaultFont",8)).pack(); ttk.Scale(box,from_=lo,to=hi,variable=var,orient="horizontal",length=width).pack()
    def _build(self):
        head=ttk.Frame(self,padding=8);head.pack(fill="x");ttk.Label(head,text="BloomTunes Studio",style="Title.TLabel").pack(side="left");ttk.Label(head,text="88 keys • 8 tracks • 256 bars • MONO",foreground=MUTED).pack(side="left",padx=14)
        for txt,cmd in [("PLAY 4 BARS",self.play),("STOP",self.engine.stop),("SAVE SONG",self.save),("LOAD SONG",self.load)]:ttk.Button(head,text=txt,command=cmd).pack(side="right",padx=3)
        nav=ttk.Frame(self,style="Panel.TFrame",padding=7);nav.pack(fill="x",padx=8)
        self.bpm=tk.DoubleVar(value=90); self.bars=tk.IntVar(value=4); self.note_size=tk.StringVar(value="1/16"); self.bar_var=tk.IntVar(value=1)
        ttk.Label(nav,text="BPM",style="Panel.TLabel").pack(side="left");ttk.Spinbox(nav,from_=30,to=240,width=6,textvariable=self.bpm).pack(side="left",padx=(3,10));ttk.Label(nav,text="SONG BARS",style="Panel.TLabel").pack(side="left");ttk.Spinbox(nav,from_=4,to=256,width=5,textvariable=self.bars,command=self.sync_song).pack(side="left",padx=(3,10));ttk.Label(nav,text="NOTE",style="Panel.TLabel").pack(side="left");cb=ttk.Combobox(nav,width=7,state="readonly",textvariable=self.note_size,values=["1/64","1/32","1/16","1/8","3/16","1/4","1/2","1 BAR"]);cb.pack(side="left",padx=(3,10));cb.bind("<<ComboboxSelected>>",lambda e:self.set_len())
        ttk.Button(nav,text="◀ 4 BARS",command=lambda:self.move_view(-4)).pack(side="left");ttk.Label(nav,text="START BAR",style="Panel.TLabel").pack(side="left",padx=(8,2));sp=ttk.Spinbox(nav,from_=1,to=253,width=5,textvariable=self.bar_var,command=self.jump_view);sp.pack(side="left");ttk.Button(nav,text="4 BARS ▶",command=lambda:self.move_view(4)).pack(side="left",padx=3);ttk.Label(nav,textvariable=self.status,style="Panel.TLabel").pack(side="right")
        trbar=ttk.Frame(self,padding=(8,6));trbar.pack(fill="x");self.track_buttons=[]
        for i in range(8):
            b=tk.Button(trbar,text=f"T{i+1}",bg=TRACK_COLORS[i],fg="#0b0d10",relief="flat",padx=12,pady=5,command=lambda i=i:self.select_track(i));b.pack(side="left",padx=2);self.track_buttons.append(b)
        strip=ttk.Frame(self,style="Panel.TFrame",padding=7);strip.pack(fill="x",padx=8)
        self.wave=tk.StringVar();self.vol=tk.DoubleVar();self.pw=tk.DoubleVar();self.attack=tk.DoubleVar();self.release=tk.DoubleVar();self.detune=tk.DoubleVar();self.harm=tk.IntVar();self.mute=tk.BooleanVar()
        ttk.Label(strip,text="TRACK",style="Panel.TLabel").pack(side="left");ttk.Combobox(strip,width=9,state="readonly",values=["SINE","SQUARE","TRIANGLE","SAW","NOISE"],textvariable=self.wave).pack(side="left",padx=3)
        self._slider(strip,"VOL",self.vol,0,100,90);self._slider(strip,"PWM",self.pw,5,95,85);self._slider(strip,"ATT",self.attack,.001,1,80);self._slider(strip,"REL",self.release,.01,2,80);self._slider(strip,"DETUNE",self.detune,-50,50,80)
        ttk.Label(strip,text="HARM",style="Panel.TLabel").pack(side="left",padx=(5,1));ttk.Spinbox(strip,from_=1,to=8,width=3,textvariable=self.harm).pack(side="left");ttk.Checkbutton(strip,text="MUTE",variable=self.mute).pack(side="left",padx=5);ttk.Button(strip,text="APPLY",command=self.apply_track).pack(side="left");ttk.Button(strip,text="RESET TRACK",command=self.reset_track).pack(side="left",padx=3)
        self.patch_name=tk.StringVar(value="Pure Sine");ttk.Combobox(strip,width=13,state="readonly",values=list(INSTRUMENT_PATCHES),textvariable=self.patch_name).pack(side="left",padx=(8,2));ttk.Button(strip,text="LOAD PATCH",command=self.load_instrument_patch).pack(side="left");ttk.Button(strip,text="SAVE PATCH",command=self.save_instrument_patch).pack(side="left",padx=2)
        mid=ttk.Frame(self,padding=8);mid.pack(fill="both",expand=True);self.canvas=tk.Canvas(mid,bg="#0b0d11",highlightthickness=0);xs=ttk.Scrollbar(mid,orient="horizontal",command=self.canvas.xview);ys=ttk.Scrollbar(mid,orient="vertical",command=self.canvas.yview);self.canvas.configure(xscrollcommand=xs.set,yscrollcommand=ys.set);self.canvas.grid(row=0,column=0,sticky="nsew");ys.grid(row=0,column=1,sticky="ns");xs.grid(row=1,column=0,sticky="ew");mid.rowconfigure(0,weight=1);mid.columnconfigure(0,weight=1);self.canvas.bind("<Button-1>",self.grid_click)
        fxwrap=ttk.Frame(self,style="Panel.TFrame",padding=6);fxwrap.pack(fill="x",padx=8,pady=(0,8));self.fxvars={}
        rows=[[("MASTER",45,0,100),("DRIVE",0,0,100),("EQ1 F",120,30,500),("EQ1 Q",.8,.2,8),("EQ1 G",0,-18,18),("EQ2 F",900,120,5000),("EQ2 Q",1,.2,8),("EQ2 G",0,-18,18),("EQ3 F",5000,1000,16000),("EQ3 Q",.8,.2,8),("EQ3 G",0,-18,18)],[("COMP TH",-12,-48,0),("COMP R",2,1,12),("COMP A",.015,.001,.2),("COMP REL",.18,.02,1.2),("MAKEUP",0,0,12),("TREM RATE",0,0,20),("TREM DEP",0,0,100),("PWM RATE",0,0,20),("PWM DEP",0,0,100),("PHASE RATE",0,0,8),("PHASE DEP",0,0,100),("ECHO ms",0,0,800),("ECHO MIX",0,0,70),("HP Hz",20,20,3000),("LP Hz",18000,500,18000)]]
        for ri,specs in enumerate(rows):
            fr=ttk.Frame(fxwrap,style="Panel.TFrame");fr.pack(fill="x")
            for name,val,lo,hi in specs:v=tk.DoubleVar(value=val);self.fxvars[name]=v;self._slider(fr,name,v,lo,hi,75)
        banks=ttk.Frame(fxwrap,style="Panel.TFrame");banks.pack(fill="x",pady=(5,0));self.fx_patch_name=tk.StringVar(value="Clean");ttk.Combobox(banks,width=15,state="readonly",values=list(FX_PATCHES),textvariable=self.fx_patch_name).pack(side="left");ttk.Button(banks,text="LOAD FX",command=self.load_fx_patch).pack(side="left",padx=2);ttk.Button(banks,text="SAVE FX",command=self.save_fx_patch).pack(side="left");ttk.Button(banks,text="RESET EQ",command=self.reset_eq).pack(side="left",padx=(12,2));ttk.Button(banks,text="RESET DYNAMICS",command=self.reset_dyn).pack(side="left",padx=2);ttk.Button(banks,text="RESET MOD",command=self.reset_mod).pack(side="left",padx=2);ttk.Button(banks,text="RESET DELAY/FILTER",command=self.reset_delay).pack(side="left",padx=2);ttk.Button(banks,text="RESET ALL FX",command=self.reset_fx).pack(side="left",padx=2);ttk.Button(banks,text="CLEAR TRACK NOTES",command=self.clear_track).pack(side="right",padx=2)
    def set_len(self): self.note_len={"1/64":1,"1/32":1,"1/16":1,"1/8":2,"3/16":3,"1/4":4,"1/2":8,"1 BAR":16}[self.note_size.get()]
    def sync_song(self): self.song.bpm=float(self.bpm.get());self.song.bars=max(4,min(MAX_BARS,int(self.bars.get())))
    def move_view(self,d): self.sync_song();self.view_bar=max(0,min(max(0,self.song.bars-VIEW_BARS),self.view_bar+d));self.bar_var.set(self.view_bar+1);self.redraw()
    def jump_view(self): self.sync_song();self.view_bar=max(0,min(max(0,self.song.bars-VIEW_BARS),int(self.bar_var.get())-1));self.bar_var.set(self.view_bar+1);self.redraw()
    def load_track_ui(self):
        tr=self.song.tracks[self.track_index];self.wave.set(tr.waveform);self.vol.set(tr.volume);self.pw.set(tr.pulse_width);self.attack.set(tr.attack);self.release.set(tr.release);self.detune.set(tr.detune);self.harm.set(tr.harmonics);self.mute.set(tr.mute)
    def select_track(self,i): self.apply_track();self.track_index=i;self.load_track_ui();self.redraw()
    def apply_track(self):
        tr=self.song.tracks[self.track_index];tr.waveform=self.wave.get();tr.volume=float(self.vol.get());tr.pulse_width=float(self.pw.get());tr.attack=float(self.attack.get());tr.release=float(self.release.get());tr.detune=float(self.detune.get());tr.harmonics=max(1,int(self.harm.get()));tr.mute=bool(self.mute.get())
    def reset_track(self):
        keep=self.song.tracks[self.track_index].notes;name=self.song.tracks[self.track_index].name;self.song.tracks[self.track_index]=Track(name=name,notes=keep);self.load_track_ui()
    def load_instrument_patch(self):
        p=INSTRUMENT_PATCHES[self.patch_name.get()];tr=self.song.tracks[self.track_index]
        for k,v in p.items():setattr(tr,k,v)
        self.load_track_ui();self.status.set(f"Loaded sound: {self.patch_name.get()}")
    def save_instrument_patch(self):
        self.apply_track();name=simpledialog.askstring("BloomTunes","Patch name?")
        if not name:return
        tr=self.song.tracks[self.track_index];d={k:getattr(tr,k) for k in ["waveform","volume","pulse_width","attack","release","detune","harmonics"]};p=filedialog.asksaveasfilename(defaultextension=".json",initialfile=name.replace(" ","_")+".instrument.json")
        if p:Path(p).write_text(json.dumps(d,indent=2));self.status.set(f"Saved sound patch {name}")
    def sync_fx(self):
        f=self.song.fx;m=self.fxvars
        mapping={"MASTER":"master","DRIVE":"drive","EQ1 F":"eq1_freq","EQ1 Q":"eq1_q","EQ1 G":"eq1_gain","EQ2 F":"eq2_freq","EQ2 Q":"eq2_q","EQ2 G":"eq2_gain","EQ3 F":"eq3_freq","EQ3 Q":"eq3_q","EQ3 G":"eq3_gain","COMP TH":"comp_threshold","COMP R":"comp_ratio","COMP A":"comp_attack","COMP REL":"comp_release","MAKEUP":"comp_makeup","TREM RATE":"trem_rate","TREM DEP":"trem_depth","PWM RATE":"pwm_rate","PWM DEP":"pwm_depth","PHASE RATE":"phaser_rate","PHASE DEP":"phaser_depth","ECHO ms":"echo_ms","ECHO MIX":"echo_mix","HP Hz":"highpass_hz","LP Hz":"lowpass_hz"}
        for k,a in mapping.items():setattr(f,a,float(m[k].get()))
    def load_fx_to_ui(self):
        f=self.song.fx;mapping={"MASTER":"master","DRIVE":"drive","EQ1 F":"eq1_freq","EQ1 Q":"eq1_q","EQ1 G":"eq1_gain","EQ2 F":"eq2_freq","EQ2 Q":"eq2_q","EQ2 G":"eq2_gain","EQ3 F":"eq3_freq","EQ3 Q":"eq3_q","EQ3 G":"eq3_gain","COMP TH":"comp_threshold","COMP R":"comp_ratio","COMP A":"comp_attack","COMP REL":"comp_release","MAKEUP":"comp_makeup","TREM RATE":"trem_rate","TREM DEP":"trem_depth","PWM RATE":"pwm_rate","PWM DEP":"pwm_depth","PHASE RATE":"phaser_rate","PHASE DEP":"phaser_depth","ECHO ms":"echo_ms","ECHO MIX":"echo_mix","HP Hz":"highpass_hz","LP Hz":"lowpass_hz"}
        for k,a in mapping.items():self.fxvars[k].set(getattr(f,a))
    def load_fx_patch(self): self.song.fx=MasterFX(**asdict(FX_PATCHES[self.fx_patch_name.get()]));self.load_fx_to_ui();self.status.set(f"Loaded FX: {self.fx_patch_name.get()}")
    def save_fx_patch(self):
        self.sync_fx();name=simpledialog.askstring("BloomTunes","FX patch name?")
        if not name:return
        p=filedialog.asksaveasfilename(defaultextension=".json",initialfile=name.replace(" ","_")+".fx.json")
        if p:Path(p).write_text(json.dumps(asdict(self.song.fx),indent=2));self.status.set(f"Saved FX patch {name}")
    def reset_eq(self):
        for k,v in {"EQ1 F":120,"EQ1 Q":.8,"EQ1 G":0,"EQ2 F":900,"EQ2 Q":1,"EQ2 G":0,"EQ3 F":5000,"EQ3 Q":.8,"EQ3 G":0}.items():self.fxvars[k].set(v)
    def reset_dyn(self):
        for k,v in {"COMP TH":-12,"COMP R":2,"COMP A":.015,"COMP REL":.18,"MAKEUP":0}.items():self.fxvars[k].set(v)
    def reset_mod(self):
        for k in ["TREM RATE","TREM DEP","PWM RATE","PWM DEP","PHASE RATE","PHASE DEP"]:self.fxvars[k].set(0)
    def reset_delay(self):
        for k,v in {"ECHO ms":0,"ECHO MIX":0,"HP Hz":20,"LP Hz":18000}.items():self.fxvars[k].set(v)
    def reset_fx(self): self.song.fx=MasterFX();self.load_fx_to_ui()
    def redraw(self):
        c=self.canvas;c.delete("all");W=self.label_w+VIEW_STEPS*self.cell_w;H=ROWS*self.cell_h;c.configure(scrollregion=(0,0,W,H));tr=self.song.tracks[self.track_index];start=self.view_bar*STEPS_PER_BAR
        for r in range(ROWS):
            midi=MIDI_HIGH-r;y=r*self.cell_h;black=midi%12 in {1,3,6,8,10};bg="#10141c" if black else "#181d27";c.create_rectangle(0,y,W,y+self.cell_h,fill=bg,outline=GRID);c.create_text(self.label_w-5,y+self.cell_h/2,text=midi_name(midi),fill=MUTED,anchor="e",font=("TkDefaultFont",7))
        for s in range(VIEW_STEPS+1):
            x=self.label_w+s*self.cell_w;absolute=start+s;barline=absolute%16==0;beat=absolute%4==0;col="#7b879e" if barline else "#50586b" if beat else GRID;c.create_line(x,0,x,H,fill=col,width=2 if barline else 1)
            if s<VIEW_STEPS and s%16==0:c.create_text(x+3,9,text=f"BAR {absolute//16+1}",fill=ACCENT,anchor="nw",font=("TkDefaultFont",7,"bold"))
        color=TRACK_COLORS[self.track_index]
        for n in tr.notes:
            if n.step>=start+VIEW_STEPS or n.step+n.length<=start:continue
            local=n.step-start;r=MIDI_HIGH-n.midi;x=self.label_w+local*self.cell_w+1;y=r*self.cell_h+1;w=max(1,n.length)*self.cell_w-2;c.create_rectangle(x,y,x+w,y+self.cell_h-2,fill=color,outline="")
        # start around middle C first time
        if not hasattr(self,"_centered"):
            self.update_idletasks();fraction=max(0,min(1,(MIDI_HIGH-60)*self.cell_h/max(1,H)));self.canvas.yview_moveto(fraction);self._centered=True
    def grid_click(self,e):
        x=self.canvas.canvasx(e.x);y=self.canvas.canvasy(e.y)
        if x<self.label_w:return
        local=int((x-self.label_w)//self.cell_w);row=int(y//self.cell_h)
        if not(0<=local<VIEW_STEPS and 0<=row<ROWS):return
        step=self.view_bar*16+local;midi=MIDI_HIGH-row;tr=self.song.tracks[self.track_index];hit=next((n for n in tr.notes if n.midi==midi and n.step<=step<n.step+n.length),None)
        if hit:tr.notes.remove(hit)
        else:
            max_steps=self.song.bars*16;tr.notes.append(Note(step=step,midi=midi,length=min(self.note_len,max_steps-step)));self.engine.preview(tr,midi)
        self.redraw()
    def clear_track(self):self.song.tracks[self.track_index].notes.clear();self.redraw()
    def play(self):
        self.apply_track();self.sync_song();self.sync_fx();self.status.set(f"Rendering bars {self.view_bar+1}-{self.view_bar+4} in MONO...")
        def worker():
            try:self.engine.play_view(self.song,self.view_bar);self.after(0,lambda:self.status.set(f"Playing bars {self.view_bar+1}-{self.view_bar+4} — MONO"))
            except Exception as ex:self.after(0,lambda:messagebox.showerror("BloomTunes",str(ex)))
        threading.Thread(target=worker,daemon=True).start()
    def song_dict(self):self.apply_track();self.sync_song();self.sync_fx();return asdict(self.song)
    def save(self):
        p=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("BloomTunes song","*.json")]);
        if p:Path(p).write_text(json.dumps(self.song_dict(),indent=2));self.status.set(f"Saved {Path(p).name}")
    def load(self):
        p=filedialog.askopenfilename(filetypes=[("BloomTunes song","*.json")]);
        if not p:return
        try:
            d=json.loads(Path(p).read_text());tracks=[]
            for td0 in d.get("tracks",[]):
                td=dict(td0);notes=[Note(**n) for n in td.pop("notes",[])];tr=Track(**td);tr.notes=notes;tracks.append(tr)
            while len(tracks)<8:tracks.append(Track(name=f"T{len(tracks)+1}"))
            self.song=Song(bpm=d.get("bpm",90),bars=max(4,min(256,d.get("bars",4))),tracks=tracks[:8],fx=MasterFX(**d.get("fx",{})));self.bpm.set(self.song.bpm);self.bars.set(self.song.bars);self.track_index=0;self.view_bar=0;self.bar_var.set(1);self.load_track_ui();self.load_fx_to_ui();self.redraw();self.status.set(f"Loaded {Path(p).name}")
        except Exception as ex:messagebox.showerror("BloomTunes",str(ex))
    def close(self):self.engine.stop();self.destroy()

if __name__=="__main__":Studio().mainloop()
