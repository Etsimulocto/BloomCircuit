#!/usr/bin/env python3
import csv, os, queue, threading, time, tkinter as tk
from tkinter import ttk
try:
    import serial
except ImportError:
    serial = None

PORT='/dev/ttyACM0'; BAUD=115200
LOG_PATH=os.path.expanduser('~/happyjarz_eq_log.csv')
COLOR_PRESETS={
    'Red':(255,0,0),'Orange':(255,70,0),'Amber':(255,180,0),'Lime':(80,255,0),
    'Green':(0,255,90),'Cyan':(0,180,255),'Blue':(40,40,255),'Violet':(180,0,255),
    'White':(255,255,255),'Pink':(255,30,120)
}

class EqApp:
    def __init__(self,root):
        self.root=root; root.title('HAPPY JARZ / CLUB BOX EQ Tuner'); root.geometry('980x900')
        self.q=queue.Queue(); self.running=True; self.ser=None; self.lock=threading.Lock(); self.ignore=False
        self.gain=tk.DoubleVar(value=4.0); self.gate=tk.DoubleVar(value=8.0); self.bright=tk.DoubleVar(value=96)
        self.edges=[tk.DoubleVar(value=v) for v in (40,90,180,350,700,1200,2000,3000,3900)]
        names=list(COLOR_PRESETS.keys())
        defaults=['Red','Orange','Amber','Lime','Green','Cyan','Blue','Violet']
        self.colors=[tk.StringVar(value=defaults[i]) for i in range(8)]
        self.energy_vars=[tk.StringVar(value=f'B{i+1}: 0.0') for i in range(8)]
        self.status=tk.StringVar(value='Connecting...'); self.summary=tk.StringVar(value='Waiting for EQ data...')

        top=ttk.Frame(root,padding=10); top.pack(fill='x')
        ttk.Label(top,textvariable=self.status).pack(side='left'); ttk.Button(top,text='RGB Test',command=lambda:self.send('TEST RGB')).pack(side='right')

        meter=ttk.LabelFrame(root,text='Live EQ',padding=10); meter.pack(fill='x',padx=10,pady=(0,8))
        ttk.Label(meter,textvariable=self.summary,font=('TkDefaultFont',16,'bold')).pack(anchor='w')
        bars=ttk.Frame(meter); bars.pack(fill='x',pady=5)
        self.band_bars=[]
        for i in range(8):
            col=ttk.Frame(bars); col.pack(side='left',fill='both',expand=True,padx=2)
            ttk.Label(col,textvariable=self.energy_vars[i]).pack()
            pb=ttk.Progressbar(col,orient='vertical',length=120,maximum=100); pb.pack(); self.band_bars.append(pb)

        controls=ttk.LabelFrame(root,text='EQ Response',padding=10); controls.pack(fill='x',padx=10,pady=(0,8))
        self.add_slider(controls,'Gain',self.gain,0.1,30.0,0.1,lambda:self.send(f'SET GAIN {self.gain.get():.2f}'))
        self.add_slider(controls,'Noise gate',self.gate,0,100,1,lambda:self.send(f'SET GATE {self.gate.get():.1f}'))
        self.add_slider(controls,'Max brightness',self.bright,4,255,1,lambda:self.send(f'SET BRIGHT {int(self.bright.get())}'))

        eq=ttk.LabelFrame(root,text='Band edges + colors',padding=10); eq.pack(fill='x',padx=10,pady=(0,8))
        hdr=ttk.Frame(eq); hdr.pack(fill='x')
        for txt,w in [('Band',7),('Low Hz',10),('High Hz',10),('Color',12)]: ttk.Label(hdr,text=txt,width=w).pack(side='left')
        for i in range(8):
            row=ttk.Frame(eq); row.pack(fill='x',pady=2)
            ttk.Label(row,text=str(i+1),width=7).pack(side='left')
            low=ttk.Spinbox(row,from_=20,to=3950,textvariable=self.edges[i],width=10); low.pack(side='left')
            high=ttk.Spinbox(row,from_=20,to=3950,textvariable=self.edges[i+1],width=10); high.pack(side='left')
            cb=ttk.Combobox(row,textvariable=self.colors[i],values=list(COLOR_PRESETS.keys()),state='readonly',width=12); cb.pack(side='left')
            ttk.Button(row,text='Apply',command=lambda i=i:self.apply_band(i)).pack(side='left',padx=5)
        ttk.Button(eq,text='Apply all edges/colors',command=self.apply_all).pack(anchor='w',pady=(6,0))

        ttk.Label(root,text=f'CSV log: {LOG_PATH}',padding=(10,0,10,4)).pack(anchor='w')
        self.log=tk.Text(root,height=14,wrap='none'); self.log.pack(fill='both',expand=True,padx=10,pady=(0,10)); self.log.configure(state='disabled')
        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH,'w',newline='') as f: csv.writer(f).writerow(['timestamp','center','p2p','clip','dominant','energy']+[f'b{i+1}' for i in range(8)])
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
                self.ser.write((s+'\n').encode()); self.ser.flush()

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
        if serial is None: self.q.put(('status','python3-serial not installed')); return
        while self.running:
            try:
                s=serial.Serial(PORT,BAUD,timeout=.25,write_timeout=.25); s.dtr=False; s.rts=False; self.ser=s
                self.q.put(('status',f'Connected: {PORT} @ {BAUD}')); time.sleep(.15); self.send('STREAM 1'); self.send('GET')
                while self.running and s.is_open:
                    raw=s.readline()
                    if not raw: continue
                    line=raw.decode(errors='replace').strip()
                    if line.startswith('HJ|EQ|'): self.q.put(('eq',self.kv(line)))
                    elif line.startswith('HJ|EQCFG|'): self.q.put(('cfg',self.kv(line)))
                    elif line.startswith('HJ|ACK|'): self.q.put(('log',line))
            except Exception as e:
                self.q.put(('status',f'Disconnected: {e} — retrying...')); self.ser=None; time.sleep(1)

    def process(self):
        try:
            while True:
                t,*rest=self.q.get_nowait()
                if t=='status': self.status.set(rest[0])
                elif t=='eq': self.update_eq(rest[0])
                elif t=='cfg': self.apply_cfg(rest[0])
                elif t=='log': self.append(rest[0])
        except queue.Empty: pass
        if self.running:self.root.after(50,self.process)

    def update_eq(self,d):
        try:
            center=int(d['CENTER']); p2p=int(d['P2P']); clip=int(d['CLIP']); dom=int(d['DOM']); en=float(d['ENERGY']); vals=[float(d.get(f'B{i+1}',0)) for i in range(8)]
        except Exception:return
        self.summary.set(f'CENTER {center}   P2P {p2p}   DOMINANT BAND {dom}   ENERGY {en:.1f}   CLIP {clip}')
        peak=max(max(vals),1.0)
        for i,v in enumerate(vals): self.energy_vars[i].set(f'B{i+1}: {v:.1f}'); self.band_bars[i]['value']=min(100,100*v/peak)
        stamp=time.strftime('%H:%M:%S'); self.append(f'{stamp} DOM={dom} P2P={p2p} ENERGY={en:.1f}  '+' '.join(f'B{i+1}={vals[i]:.1f}' for i in range(8)))
        with open(LOG_PATH,'a',newline='') as f: csv.writer(f).writerow([time.strftime('%Y-%m-%d %H:%M:%S'),center,p2p,clip,dom,en,*vals])

    def apply_cfg(self,d):
        self.ignore=True
        try:
            if 'GAIN' in d:self.gain.set(float(d['GAIN']))
            if 'GATE' in d:self.gate.set(float(d['GATE']))
            if 'BRIGHT' in d:self.bright.set(float(d['BRIGHT']))
            for i in range(9):
                if f'E{i}' in d:self.edges[i].set(float(d[f'E{i}']))
        finally:self.ignore=False

    def append(self,s):
        self.log.configure(state='normal'); self.log.insert('end',s+'\n'); self.log.see('end'); self.log.configure(state='disabled')
    def close(self):
        self.running=False
        try:self.send('STREAM 0')
        except:pass
        try:
            if self.ser:self.ser.close()
        except:pass
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk(); EqApp(root); root.mainloop()
