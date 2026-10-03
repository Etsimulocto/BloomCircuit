#!/usr/bin/env python3
"""BloomFace 0.1.0: a weird, procedural robot face with a USB rotary remote."""
import argparse
import colorsys
from collections import deque
from datetime import datetime
import json
import math
import os
from pathlib import Path
import queue
import random
import threading
import time
import tkinter as tk
from tkinter import ttk
from model import FaceState, MOODS, CONTROLS

VERSION="0.1.0"


def instance_lock():
    if os.name!="posix":return None
    import fcntl
    directory=Path.home()/".cache"/"bloomface";directory.mkdir(parents=True,exist_ok=True)
    lock=open(directory/"app.lock","a")
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close();raise RuntimeError("BloomFace is already open")
    return lock


class USB:
    def __init__(self):
        self.port=None; self.thread=None; self.stop=threading.Event();self.events=queue.Queue(maxsize=200)

    def connect(self, name):
        import serial
        self.close()
        self.port=serial.Serial(name,115200,timeout=0.15,write_timeout=0.2)
        self.stop=threading.Event()
        self.thread=threading.Thread(target=self.read,args=(self.port,self.stop),daemon=True)
        self.thread.start()

    def read(self, port, stop):
        buffer=b""
        try:
            while not stop.is_set():
                buffer+=port.read(port.in_waiting or 1)
                if len(buffer)>16384: buffer=b""
                while b"\n" in buffer:
                    line,buffer=buffer.split(b"\n",1)
                    try:
                        record=json.loads(line)
                        if isinstance(record,dict):self.events.put_nowait(record)
                    except (ValueError,UnicodeError,queue.Full):pass
        except Exception as exc:
            if not stop.is_set():
                try:self.events.put_nowait({"type":"error","message":str(exc)})
                except queue.Full:pass

    def send(self, text):
        if self.port:self.port.write((text+"\n").encode("ascii"))

    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=0.4)
        if self.port:self.port.close()
        self.port=None
        while not self.events.empty():
            try:self.events.get_nowait()
            except queue.Empty:break


class App:
    def __init__(self, root, demo=False):
        self.root=root;self.demo=demo;self.face=FaceState();self.usb=USB()
        self.ready=False;self.last_rx=0;self.connect_at=0;self.last_keep=0
        self.started=time.monotonic();self.blink_at=0;self.next_blink=2.5
        self.burst_at=-100;self.last_surprise=0;self.fullscreen=False;self.logs=deque(maxlen=100)
        root.title(f"BloomFace {VERSION}"+(" — DEMO" if demo else ""))
        root.geometry("1100x780");root.minsize(750,560);root.configure(bg="#060b15")
        style=ttk.Style();style.theme_use("clam")
        style.configure("TFrame",background="#0d1727")
        style.configure("TLabel",background="#0d1727",foreground="#c7d3e9")
        style.configure("TButton",padding=7)
        top=ttk.Frame(root,padding=12);top.pack(fill="x")
        ttk.Label(top,text="BLOOMFACE",font=("Sans",19,"bold")).pack(side="left",padx=(0,15))
        self.port=ttk.Combobox(top,width=18);self.port.pack(side="left")
        ttk.Button(top,text="Refresh",command=self.refresh).pack(side="left",padx=4)
        ttk.Button(top,text="Connect",command=self.connect).pack(side="left")
        ttk.Button(top,text="Disconnect",command=self.disconnect).pack(side="left",padx=4)
        ttk.Button(top,text="Fullscreen [F]",command=self.toggle_fullscreen).pack(side="right")
        self.status=tk.StringVar(value="DEMO · keyboard/mouse control" if demo else "Plug in the rotary board and Connect")
        ttk.Label(root,textvariable=self.status,padding=(12,7)).pack(fill="x")
        self.canvas=tk.Canvas(root,bg="#060b15",highlightthickness=0)
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Button-1>",lambda _:self.tap())
        self.canvas.bind("<MouseWheel>",lambda e:self.turn(1 if e.delta>0 else -1))
        self.canvas.bind("<Button-4>",lambda _:self.turn(1))
        self.canvas.bind("<Button-5>",lambda _:self.turn(-1))
        panel=ttk.Frame(root,padding=12);panel.pack(fill="x")
        self.control=tk.StringVar();ttk.Label(panel,textvariable=self.control,font=("Sans",13,"bold")).pack(side="left")
        ttk.Button(panel,text="←",command=lambda:self.turn(-1)).pack(side="left",padx=(14,4))
        ttk.Button(panel,text="→",command=lambda:self.turn(1)).pack(side="left")
        ttk.Button(panel,text="Click / next control",command=self.tap).pack(side="left",padx=5)
        ttk.Button(panel,text="WEIRD BURST",command=self.weird).pack(side="left")
        ttk.Button(panel,text="Copy debug",command=self.copy_log).pack(side="right")
        row=ttk.Frame(root,padding=(12,0,12,10));row.pack(fill="x")
        ttk.Label(row,text="Turn: change selected control  •  Click: next control  •  Hold 0.7 s: weird burst").pack(side="left")
        self.reverse=tk.BooleanVar(value=False)
        ttk.Checkbutton(row,text="Reverse knob",variable=self.reverse,command=self.settings).pack(side="right")
        self.detent=tk.StringVar(value="4")
        det=ttk.Combobox(row,textvariable=self.detent,values=("4","2"),state="readonly",width=3)
        det.pack(side="right",padx=6);det.bind("<<ComboboxSelected>>",lambda _:self.settings())
        ttk.Label(row,text="Edges/click:").pack(side="right")
        root.bind("<Left>",lambda _:self.turn(-1));root.bind("<Right>",lambda _:self.turn(1))
        root.bind("<space>",lambda _:self.tap());root.bind("<Return>",lambda _:self.weird())
        root.bind("f",lambda _:self.toggle_fullscreen());root.bind("<Escape>",lambda _:self.leave_fullscreen())
        root.protocol("WM_DELETE_WINDOW",self.close)
        self.refresh();self.log("Session started"+(" DEMO" if demo else ""));self.frame()

    def log(self,text):self.logs.append(datetime.now().astimezone().isoformat(timespec="seconds")+"  "+text)

    def copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(f"BloomFace {VERSION} DEMO={self.demo} port={self.port.get()}\n"+"\n".join(self.logs))
        self.status.set("Debug copied — paste into chat")

    def refresh(self):
        try:
            from serial.tools import list_ports
            ps=list(list_ports.comports());self.port["values"]=[p.device for p in ps]
            if not self.port.get() and ps:self.port.set(next((p.device for p in ps if p.vid==0x303A),ps[0].device))
        except ImportError:
            if not self.demo:self.status.set("Install python3-serial / pyserial first")

    def settings(self):
        self.face.reverse=self.reverse.get();self.face.detent=int(self.detent.get());self.face.remainder=0

    def connect(self):
        if self.demo:return
        self.disconnect()
        try:
            if not self.port.get():raise ValueError("Choose a port")
            self.usb.connect(self.port.get());self.connect_at=time.monotonic();self.last_keep=0
            self.status.set("Waiting for BloomFace firmware…");self.log("Connecting "+self.port.get())
        except Exception as exc:self.status.set(str(exc));self.log("Connect error: "+str(exc))

    def disconnect(self):
        self.usb.close();self.ready=False;self.face.baseline=None
        self.status.set("Disconnected · face still works with keyboard/mouse")

    def turn(self,n):self.face.turn(n);self.log(f"turn {n} → {MOODS[self.face.mood]} / {CONTROLS[self.face.control]}")
    def tap(self):self.face.tap();self.log("control → "+CONTROLS[self.face.control])
    def weird(self):self.face.weird();self.log("WEIRD BURST → "+MOODS[self.face.mood])
    def toggle_fullscreen(self):self.fullscreen=not self.fullscreen;self.root.attributes("-fullscreen",self.fullscreen)
    def leave_fullscreen(self):self.fullscreen=False;self.root.attributes("-fullscreen",False)

    def poll(self, now):
        for _ in range(100):
            try:d=self.usb.events.get_nowait()
            except queue.Empty:break
            if d.get("type")=="error":
                self.disconnect();self.status.set("USB error: "+d.get("message","?"));self.log(self.status.get());break
            if d.get("type") not in ("hello","input"):continue
            if d.get("device")!="BloomFace" or d.get("protocol")!=1:
                self.disconnect();self.status.set("This board is not running BloomFace firmware");break
            try:
                events=self.face.ingest(d)
                for event in events:self.log(event+" → "+MOODS[self.face.mood]+" / "+CONTROLS[self.face.control])
                self.last_rx=now
                if d["type"]=="hello":
                    self.ready=True;self.status.set("USB connected · BloomFace firmware "+str(d.get("version","?")))
                    self.log("Handshake accepted")
            except (ValueError,KeyError,TypeError):self.log("Malformed encoder packet ignored")
        if self.usb.port and now-self.last_keep>0.5:
            self.last_keep=now
            try:
                self.usb.send("KEEP" if self.ready else "HELLO")
                if (self.ready and now-self.last_rx>5) or (not self.ready and now-self.connect_at>8):
                    self.disconnect();self.status.set("No response — reconnect or flash BloomFace")
            except Exception as exc:
                self.disconnect();self.status.set(str(exc));self.log("USB error: "+str(exc))

    def draw(self,t):
        c=self.canvas;c.delete("all")
        w,h=max(1,c.winfo_width()),max(1,c.winfo_height())
        scale=min(w/1200,h/680);ox=(w-1200*scale)/2;oy=(h-680*scale)/2
        f=self.face;name=MOODS[f.mood]
        rgb=colorsys.hls_to_rgb(f.hue,0.65,0.85);accent="#"+"".join(f"{int(v*255):02x}" for v in rgb)
        dark="#13243a";bright="#d7fff6"
        def line(*pts,**kw):return c.create_line(*pts,tags="face",**kw)
        def oval(*pts,**kw):return c.create_oval(*pts,tags="face",**kw)
        def rect(*pts,**kw):return c.create_rectangle(*pts,tags="face",**kw)
        def text(x,y,s,**kw):return c.create_text(x,y,text=s,tags="face",**kw)
        # Subtle CRT grid and moving scan line.
        for x in range(60,1200,60):line(x,35,x,640,fill="#0e192a")
        for y in range(40,660,40):line(45,y,1155,y,fill="#0e192a")
        sy=50+(t*28)%570;line(60,sy,1140,sy,fill="#14263b",width=2)
        for x,y,sx,sy2 in ((45,45,1,1),(1155,45,-1,1),(45,635,1,-1),(1155,635,-1,-1)):
            line(x+sx*55,y,x,y,x,y+sy2*45,fill=accent,width=3)
        text(600,73,"B L O O M  /  F A C E",fill="#5f789b",font=("Monospace",13,"bold"))
        # Ambient motion is procedural; no AI/image assets or external services.
        bob=math.sin(t*(1+f.energy*3))*7*f.energy
        blink=1.0
        elapsed=t-self.blink_at
        if 0<=elapsed<0.22:blink=max(0.04,abs(elapsed-0.11)/0.11)
        gx=f.gaze*48+math.sin(t*0.7)*9;gy=math.sin(t*0.9)*5
        if name=="SIDE EYE":gx=45
        if name=="SUSPICIOUS":gx=-35
        if name=="DISCO":gx=math.sin(t*7)*38;gy=math.cos(t*7)*24
        ey=295+bob
        for idx,cx in enumerate((390,810)):
            eh=88;ew=145
            if name=="PANIC":eh=120;ew=128
            if name=="VOID":eh=105;ew=155
            if name in ("SIDE EYE","SUSPICIOUS"):eh=42
            if name=="SLEEPY":eh=18
            if name=="MELTING":eh=80+math.sin(t*3+idx)*25
            if name=="CURIOUS" and idx==1:eh=105
            eh*=blink
            for k in (12,6):oval(cx-ew-k,ey-eh-k,cx+ew+k,ey+eh+k,outline=dark,width=5)
            oval(cx-ew,ey-eh,cx+ew,ey+eh,fill=accent,outline=accent,width=2)
            if name=="JOY":
                line(cx-85,ey+10,cx-45,ey-30,cx,ey-45,cx+45,ey-30,cx+85,ey+10,fill="#071220",width=17,smooth=True)
            elif name=="LOVESTRUCK":
                points=[]
                for k in range(41):
                    a=k*math.tau/40
                    points.extend((cx+4*(16*math.sin(a)**3),ey-4*(13*math.cos(a)-5*math.cos(2*a)-2*math.cos(3*a)-math.cos(4*a))))
                c.create_polygon(*points,fill="#071220",outline="",tags="face")
            elif name=="VOID":
                oval(cx-105,ey-eh+9,cx+105,ey+eh-9,fill="#060b15",outline="")
                oval(cx-7+gx,ey-6,cx+7+gx,ey+6,fill=bright,outline="")
            elif name=="DISCO":
                line(cx-55+gx,ey-40+gy,cx+55+gx,ey+40+gy,fill="#071220",width=18)
                line(cx-55+gx,ey+40+gy,cx+55+gx,ey-40+gy,fill="#071220",width=18)
            else:
                ph=min(54,eh*0.76)
                oval(cx-38+gx,ey-ph+gy*blink,cx+38+gx,ey+ph+gy*blink,fill="#071220",outline="")
                if eh>28:oval(cx-18+gx,ey-ph+12,cx-4+gx,ey-ph+26,fill=bright,outline="")
            if name in ("STUBBORN","GREMLIN","SUSPICIOUS"):
                slope=35 if idx==0 else -35
                line(cx-140,ey-eh-30-slope,cx+140,ey-eh-30+slope,fill=accent,width=13)
            if name=="MELTING":
                for j in range(3):
                    xx=cx-70+j*70;length=30+25*(1+math.sin(t*2+j+idx))
                    line(xx,ey+eh-8,xx,ey+eh+length,fill=accent,width=15,capstyle=tk.ROUND)
        my=478+bob
        if name=="PANIC":oval(557,my-35,643,my+55,outline=accent,width=10)
        elif name=="SLEEPY":
            line(510,my,690,my,fill=accent,width=8,capstyle=tk.ROUND)
            text(1000,175,"z"*(1+int(t)%3),fill=accent,font=("Monospace",25))
        elif name=="VOID":line(576,my,624,my,fill=accent,width=3)
        elif name=="GREMLIN":
            line(485,my-10,530,my+25,575,my-5,620,my+25,665,my-5,710,my+20,fill=accent,width=9)
        elif name=="STUBBORN":rect(495,my-8,705,my+12,outline=accent,width=5)
        elif name=="MELTING":
            line(500,my-10,540,my+20,600,my-10,660,my+25,705,my,fill=accent,width=8,smooth=True)
        else:
            depth=60 if name in ("JOY","LOVESTRUCK","DISCO") else 18
            line(490,my-10,535,my+depth,600,my+depth+6,665,my+depth,710,my-10,fill=accent,width=9,smooth=True,capstyle=tk.ROUND)
        if name in ("JOY","LOVESTRUCK"):
            for cx in (250,950):line(cx-22,415,cx+22,415,fill="#e992b8",width=8,capstyle=tk.ROUND)
        # Long press creates an expanding orbit of little sparks.
        burst=t-self.burst_at
        if 0<=burst<1.3:
            for k in range(18):
                a=k*math.tau/18+burst*1.7;r=100+burst*240
                xx=600+math.cos(a)*r;yy=340+math.sin(a)*r*0.7
                line(xx-7,yy,xx+7,yy,fill=accent,width=3)
                line(xx,yy-7,xx,yy+7,fill=accent,width=3)
        text(600,598,name,fill=accent,font=("Monospace",21,"bold"))
        text(600,632,f"ENERGY {int(f.energy*100):02d}%   /   CONTROL: {CONTROLS[f.control]}",fill="#6a83a6",font=("Monospace",12))
        c.scale("face",0,0,scale,scale);c.move("face",ox,oy)
        # Canvas scale does not scale font glyphs; set proportional font sizes.
        for item in c.find_withtag("face"):
            if c.type(item)=="text":
                current=c.itemcget(item,"font").split()
                if len(current)>=2:
                    try:c.itemconfigure(item,font=(current[0],max(7,int(float(current[1])*scale)),*current[2:]))
                    except ValueError:pass

    def frame(self):
        now=time.monotonic();t=now-self.started;self.poll(now)
        if t>self.next_blink:
            self.blink_at=t;self.next_blink=t+random.uniform(2,5)
        if self.face.surprise!=self.last_surprise:
            self.last_surprise=self.face.surprise;self.burst_at=t
        self.control.set("KNOB → "+CONTROLS[self.face.control])
        self.draw(t);self.root.after(33,self.frame)

    def close(self):self.usb.close();self.root.destroy()


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--demo",action="store_true");parser.add_argument("--port")
    args=parser.parse_args()
    try:desktop_lock=instance_lock()
    except RuntimeError as exc:print(exc);raise SystemExit(0)
    root=tk.Tk();app=App(root,args.demo)
    if args.port and not args.demo:app.port.set(args.port);root.after(500,app.connect)
    root.mainloop()
