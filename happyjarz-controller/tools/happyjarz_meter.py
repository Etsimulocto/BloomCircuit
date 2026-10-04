#!/usr/bin/env python3
import csv, os, queue, threading, time, tkinter as tk
from tkinter import ttk
try:
    import serial
except ImportError:
    serial = None

PORT='/dev/ttyACM0'; BAUD=115200
DISCONNECT_GRACE_SEC=3.0
LOG_PATH=os.path.expanduser('~/happyjarz_eq_log.csv')
DEFAULT_EDGES=(40,90,180,350,700,1200,2000,3000,3900)
DEFAULT_COLOR_NAMES=('Red','Orange','Amber','Lime','Green','Cyan','Blue','Violet')
COLOR_PRESETS={
    'Red':(255,0,0),'Orange':(255,70,0),'Amber':(255,180,0),'Lime':(80,255,0),
    'Green':(0,255,90),'Cyan':(0,180,255),'Blue':(40,40,255),'Violet':(180,0,255),
    'White':(255,255,255),'Pink':(255,30,120)
}

class EqApp:
    def __init__(self,root):
        self.root=root; root.title('BloomPulse — HAPPY JARZ EQ Tuner'); root.geometry('1040x980')
        self.q=queue.Queue(); self.running=True; self.ser=None; self.lock=threading.Lock(); self.ignore=False
        self.gain=tk.DoubleVar(value=4.0); self.bright=tk.DoubleVar(value=255); self.mode=tk.IntVar(value=1)
        self.edges=[tk.DoubleVar(value=v) for v in DEFAULT_EDGES]
        self.colors=[tk.StringVar(value=DEFAULT_COLOR_NAMES[i]) for i in range(8)]
        self.energy_vars=[tk.StringVar(value=f'B{i+1}: 0.0') for i in range(8)]
        self.status=tk.StringVar(value='Connecting...')
        self.summary=tk.StringVar(value='Waiting for EQ data...')
        self.knob_var=tk.StringVar(value='Noise knob: raw 0   0.0%   gate 0.0')
        self.last_vals=[0.0]*8
        self.last_gate=0.0

        top=ttk.Frame(root,padding=10); top.pack(fill='x')
        ttk.Label(top,textvariable=self.status).pack(side='left')
        ttk.Button(top,text='Reset',command=self.reset_all).pack(side='right',padx=(6,0))
        ttk.Button(top,text='RGB Test',command=lambda:self.send('TEST RGB')).pack(side='right')

        meter=ttk.LabelFrame(root,text='Live EQ',padding=10); meter.pack(fill='x',padx=10,pady=(0,8))
        ttk.Label(meter,textvariable=self.summary,font=('TkDefaultFont',16,'bold')).pack(anchor='w')
        ttk.Label(meter,textvariable=self.knob_var,font=('TkDefaultFont',13,'bold')).pack(anchor='w',pady=(2,6))
        ttk.Label(meter,text='Physical GPIO10 knob = the ONLY threshold / noise-floor control. Full turn = gate 0–500.',font=('TkDefaultFont',10)).pack(anchor='w',pady=(0,4))
        bars=ttk.Frame(meter); bars.pack(fill='x',pady=5)
        self.band_bars=[]
        for i in range(8):
            col=ttk.Frame(bars); col.pack(side='left',fill='both',expand=True,padx=2)
            ttk.Label(col,textvariable=self.energy_vars[i]).pack()
            pb=ttk.Progressbar(col,orient='vertical',length=105,maximum=100); pb.pack(); self.band_bars.append(pb)

        controls=ttk.LabelFrame(root,text='EQ Response',padding=10); controls.pack(fill='x',padx=10,pady=(0,8))
        self.add_slider(controls,'Gain',self.gain,0.1,30.0,0.1,lambda:self.send(f'SET GAIN {self.gain.get():.2f}'))
        self.add_slider(controls,'Max brightness',self.bright,4,255,1,lambda:self.send(f'SET BRIGHT {int(self.bright.get())}'))

        bulbs=ttk.LabelFrame(root,text='16 Bulbs',padding=10); bulbs.pack(fill='x',padx=10,pady=(0,8))
        modes=ttk.Frame(bulbs); modes.pack(fill='x',pady=(0,6))
        ttk.Radiobutton(modes,text='Single bulb bench',variable=self.mode,value=1,command=lambda:self.send('SET MODE 1')).pack(side='left')
        ttk.Radiobutton(modes,text='16 bulbs — 2 per EQ band',variable=self.mode,value=16,command=lambda:self.send('SET MODE 16')).pack(side='left',padx=10)
        ttk.Button(modes,text='Chase 16',command=lambda:self.send('TEST CHASE16')).pack(side='right')
        ttk.Button(modes,text='All 16',command=lambda:self.send('TEST ALL16')).pack(side='right',padx=6)

        preview=ttk.Frame(bulbs); preview.pack(fill='x')
        self.bulb_canvas=[]
        for i in range(16):
            cell=ttk.Frame(preview); cell.pack(side='left',expand=True,padx=2)
            cv=tk.Canvas(cell,width=42,height=42,highlightthickness=0)
            cv.pack(); oval=cv.create_oval(5,5,37,37,fill='#101010',outline='#777')
            ttk.Label(cell,text=f'{i+1}\nB{i//2+1}',justify='center').pack()
            self.bulb_canvas.append((cv,oval))
        ttk.Label(bulbs,text='In 16-bulb mode: bulbs 1–2 = Band 1, 3–4 = Band 2 ... 15–16 = Band 8. Preview follows live EQ energy.',wraplength=980).pack(anchor='w',pady=(6,0))

        eq=ttk.LabelFrame(root,text='Band edges + colors',padding=10); eq.pack(fill='x',padx=10,pady=(0,8))
        hdr=ttk.Frame(eq); hdr.pack(fill='x')
        for txt,w in [('Band',7),('Low Hz',10),('High Hz',10),('Color',12)]: ttk.Label(hdr,text=txt,width=w).pack(side='left')
        for i in range(8):
            row=ttk.Frame(eq); row.pack(fill='x',pady=2)
            ttk.Label(row,text=str(i+1),width=7).pack(side='left')
            ttk.Spinbox(row,from_=20,to=3950,textvariable=self.edges[i],width=10).pack(side='left')
            ttk.Spinbox(row,from_=20,to=3950,textvariable=self.edges[i+1],width=10).pack(side='left')
            ttk.Combobox(row,textvariable=self.colors[i],values=list(COLOR_PRESETS.keys()),state='readonly',width=12).pack(side='left')
            ttk.Button(row,text='Apply',command=lambda i=i:self.apply_band(i)).pack(side='left',padx=5)
        ttk.Button(eq,text='Apply all edges/colors',command=self.apply_all).pack(anchor='w',pady=(6,0))

        ttk.Label(root,text=f'CSV log: {LOG_PATH}',padding=(10,0,10,4)).pack(anchor='w')
        self.log=tk.Text(root,height=8,wrap='none'); self.log.pack(fill='both',expand=True,padx=10,pady=(0,10)); self.log.configure(state='disabled')
        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH,'w',newline='') as f:
                csv.writer(f).writerow(['timestamp','center','p2p','clip','dominant','energy','knob_raw','knob_percent','gate','mode']+[f'b{i+1}' for i in range(8)])
        threading.Thread(target=self.reader,daemon=True).start(); root.after(50,self.process); root.protocol('WM_DELETE_WINDOW',self.close)

    def add_slider(self,parent,label,var,lo,hi,res,cb):
        row=ttk.Frame(parent); row.pack(fill='x',pady=2); ttk.Label(row,text=label,width=16).pack(side='left')
        sc=tk.Scale(row,from_=lo,to=hi,resolution=res,orient='horizontal',variable=var,length=640); sc.pack(side='left',fill='x',expand=True)
        def sched(_=None):
            if self.ignore:return
            if getattr(sc,'aid',None): self.root.after_cancel(sc.aid)
            sc.aid=self.root.after(120,cb)
        sc.configure(command=sched)

    def send(self,s):
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.write((s+'\n').encode()); self.ser.flush()
                except Exception:
                    pass

    def reset_all(self):
        self.ignore=True
        try:
            self.gain.set(4.0); self.bright.set(255); self.mode.set(1)
            for i,v in enumerate(DEFAULT_EDGES): self.edges[i].set(v)
            for i,name in enumerate(DEFAULT_COLOR_NAMES): self.colors[i].set(name)
            self.last_vals=[0.0]*8; self.last_gate=0.0
            for i in range(8):
                self.energy_vars[i].set(f'B{i+1}: 0.0')
                self.band_bars[i]['value']=0
        finally:
            self.ignore=False
        self.update_bulbs(self.last_vals,self.last_gate)
        self.summary.set('Resetting to original EQ map...')
        self.send('RESET')
        self.root.after(120,lambda:self.send('STREAM 1'))
        self.root.after(180,lambda:self.send('GET'))

    def apply_band(self,i):
        self.send(f'SET EDGE {i} {self.edges[i].get():.0f}'); self.send(f'SET EDGE {i+1} {self.edges[i+1].get():.0f}')
        r,g,b=COLOR_PRESETS[self.colors[i].get()]; self.send(f'SET COLOR {i+1} {r},{g},{b}')

    def apply_all(self):
        for i,v in enumerate(self.edges): self.send(f'SET EDGE {i} {v.get():.0f}')
        for i in range(8):
            r,g,b=COLOR_PRESETS[self.colors[i].get()]; self.send(f'SET COLOR {i+1} {r},{g},{b}')

    @staticmethod
    def kv(line):
        d={}
        for p in line.split('|')[2:]:
            if '=' in p:
                k,v=p.split('=',1); d[k]=v
        return d

    def reader(self):
        if serial is None:
            self.q.put(('status','python3-serial not installed')); return

        missing_since=None
        while self.running:
            try:
                if not os.path.exists(PORT):
                    if missing_since is None: missing_since=time.monotonic()
                    elapsed=time.monotonic()-missing_since
                    if elapsed>=DISCONNECT_GRACE_SEC:
                        self.q.put(('device_gone',)); return
                    self.q.put(('status',f'Controller reconnecting… {DISCONNECT_GRACE_SEC-elapsed:.1f}s'))
                    time.sleep(.20)
                    continue

                missing_since=None
                s=serial.Serial()
                s.port=PORT; s.baudrate=BAUD; s.timeout=.25; s.write_timeout=.25; s.dtr=False; s.rts=False
                s.open(); s.dtr=False; s.rts=False; self.ser=s
                self.q.put(('status',f'Connected: {PORT} @ {BAUD}'))
                time.sleep(.15); self.send('STREAM 1'); self.send('GET')

                while self.running and s.is_open:
                    if not os.path.exists(PORT):
                        break
                    try:
                        raw=s.readline()
                    except Exception:
                        break
                    if not raw: continue
                    line=raw.decode(errors='replace').strip()
                    if line.startswith('HJ|EQ|'): self.q.put(('eq',self.kv(line)))
                    elif line.startswith('HJ|EQCFG|'): self.q.put(('cfg',self.kv(line)))
                    elif line.startswith('HJ|ACK|'): self.q.put(('log',line))

                try:s.close()
                except:pass
                self.ser=None
                missing_since=time.monotonic()
                self.q.put(('status','Controller reconnecting…'))
                time.sleep(.20)

            except Exception as e:
                try:
                    if self.ser:self.ser.close()
                except:pass
                self.ser=None
                if missing_since is None: missing_since=time.monotonic()
                if not os.path.exists(PORT) and time.monotonic()-missing_since>=DISCONNECT_GRACE_SEC:
                    self.q.put(('device_gone',)); return
                self.q.put(('status',f'Controller reconnecting… {e}'))
                time.sleep(.35)

    def process(self):
        try:
            while True:
                t,*rest=self.q.get_nowait()
                if t=='status': self.status.set(rest[0])
                elif t=='eq': self.update_eq(rest[0])
                elif t=='cfg': self.apply_cfg(rest[0])
                elif t=='log': self.append(rest[0])
                elif t=='device_gone':
                    self.status.set('Controller unplugged — closing...')
                    self.root.after(250,self.close)
                    return
        except queue.Empty: pass
        if self.running:self.root.after(50,self.process)

    def update_bulbs(self,vals,gate):
        peak=max(max(vals),gate+1.0,1.0)
        for i in range(16):
            band=i//2; e=vals[band]
            name=self.colors[band].get(); r,g,b=COLOR_PRESETS.get(name,(255,255,255))
            if e<=gate: level=0.0
            else: level=min(1.0,(e-gate)/max(1.0,peak-gate))
            level=level**0.5
            rr=int(r*level); gg=int(g*level); bb=int(b*level)
            self.bulb_canvas[i][0].itemconfigure(self.bulb_canvas[i][1],fill=f'#{rr:02x}{gg:02x}{bb:02x}')

    def update_eq(self,d):
        try:
            center=int(d['CENTER']); p2p=int(d['P2P']); clip=int(d['CLIP']); dom=int(d['DOM']); en=float(d['ENERGY'])
            knob=int(d.get('KNOB',0)); knobpct=float(d.get('KNOBPCT',0)); gate=float(d.get('GATE',0)); mode=int(d.get('MODE',1))
            vals=[float(d.get(f'B{i+1}',0)) for i in range(8)]
        except Exception:return
        self.mode.set(mode); self.last_vals=vals; self.last_gate=gate
        silent=int(d.get('SILENT',0)); act=float(d.get('ACT',0))
        self.summary.set(f'CENTER {center}   P2P {p2p}   ACT {act:.1f}   SILENT {silent}   DOM {dom}   ENERGY {en:.1f}   CLIP {clip}')
        self.knob_var.set(f'Noise knob: raw {knob}   {knobpct:.1f}%   gate {gate:.1f}')
        peak=max(max(vals),1.0)
        for i,v in enumerate(vals): self.energy_vars[i].set(f'B{i+1}: {v:.1f}'); self.band_bars[i]['value']=min(100,100*v/peak)
        self.update_bulbs(vals,gate)
        stamp=time.strftime('%H:%M:%S'); self.append(f'{stamp} MODE={mode} DOM={dom} P2P={p2p} ACT={act:.1f} SILENT={silent} ENERGY={en:.1f} KNOB={knob} ({knobpct:.1f}%) GATE={gate:.1f}')
        with open(LOG_PATH,'a',newline='') as f:
            csv.writer(f).writerow([time.strftime('%Y-%m-%d %H:%M:%S'),center,p2p,clip,dom,en,knob,knobpct,gate,mode,*vals])

    def apply_cfg(self,d):
        self.ignore=True
        try:
            if 'GAIN' in d:self.gain.set(float(d['GAIN']))
            if 'BRIGHT' in d:self.bright.set(float(d['BRIGHT']))
            if 'MODE' in d:self.mode.set(int(d['MODE']))
            for i in range(9):
                if f'E{i}' in d:self.edges[i].set(float(d[f'E{i}']))
            for i in range(8):
                key=f'C{i+1}'
                if key in d:
                    try:
                        rgb=tuple(int(x) for x in d[key].split(','))
                        matched=False
                        for name,val in COLOR_PRESETS.items():
                            if val==rgb:
                                self.colors[i].set(name); matched=True; break
                        if not matched:self.colors[i].set(DEFAULT_COLOR_NAMES[i])
                    except Exception:self.colors[i].set(DEFAULT_COLOR_NAMES[i])
        finally:self.ignore=False
        self.update_bulbs(self.last_vals,self.last_gate)

    def append(self,s):
        self.log.configure(state='normal'); self.log.insert('end',s+'\n'); self.log.see('end')
        if int(self.log.index('end-1c').split('.')[0])>300:self.log.delete('1.0','80.0')
        self.log.configure(state='disabled')

    def close(self):
        if not self.running:
            try:self.root.destroy()
            except:pass
            return
        self.running=False
        try:self.send('STREAM 0')
        except:pass
        try:
            if self.ser:self.ser.close()
        except:pass
        try:self.root.destroy()
        except:pass

if __name__=='__main__':
    root=tk.Tk(); EqApp(root); root.mainloop()
