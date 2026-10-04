#!/usr/bin/env python3
import json, re, time, threading, subprocess
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    import serial.tools.list_ports
except Exception:
    serial = None

BASE = Path(__file__).resolve().parent
FW_DIR = BASE / "firmware_v2"
RESULTS_DIR = BASE / "results"
RESULTS_DIR.mkdir(exist_ok=True)
FQBN = "esp32:esp32:esp32s3:CDCOnBoot=cdc"
BAUD = 115200

GPIO_ORDER = list(range(1,19)) + [21] + list(range(33,42)) + [43,44] + list(range(45,49))
TOUCH = set(range(1,15))
ADC = set(range(1,19))
STRAP = {3,9,10,11,12,13,14,33,34,35,36,37,39,40,41,45,46,47,48}

PINS = [
    {"physical":1,"label":"5V","kind":"power"},
    {"physical":2,"label":"GND","kind":"ground"},
    {"physical":3,"label":"3V3","kind":"power"},
    {"physical":4,"label":"TX / GPIO43","kind":"gpio","gpio":43,"touch":False,"adc":False,"strap":False},
    {"physical":5,"label":"RX / GPIO44","kind":"gpio","gpio":44,"touch":False,"adc":False,"strap":False},
]
physical = 6
for gpio in [g for g in GPIO_ORDER if g not in (43,44)]:
    PINS.append({
        "physical": physical,
        "label": f"GPIO{gpio}",
        "kind":"gpio",
        "gpio":gpio,
        "touch":gpio in TOUCH,
        "adc":gpio in ADC,
        "strap":gpio in STRAP,
    })
    physical += 1

def parse_record(raw):
    parts = raw.strip().split("|")
    if len(parts) < 3 or parts[0] != "BBT": return None
    d = {"kind":parts[1],"status":parts[2],"raw":raw.strip()}
    for part in parts[3:]:
        if "=" in part:
            k,v = part.split("=",1); d[k]=v
    return d

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BloomBoard Tester v2")
        self.geometry("1180x820")
        self.minsize(1000,700)
        self.running=False; self.flashed=False; self.selected=None
        self.pin_buttons={}; self.pin_status={}; self.records=[]
        self._build(); self.after(250,self.refresh_ports)

    def _build(self):
        top=ttk.Frame(self,padding=10); top.pack(fill="x")
        ttk.Label(top,text="BloomBoard Tester v2",font=("TkDefaultFont",18,"bold")).pack(side="left")
        self.result=tk.StringVar(value="READY")
        ttk.Label(top,textvariable=self.result,font=("TkDefaultFont",18,"bold")).pack(side="right")

        controls=ttk.Frame(self,padding=(10,0,10,8)); controls.pack(fill="x")
        ttk.Label(controls,text="Port").pack(side="left")
        self.port=tk.StringVar(); self.ports=ttk.Combobox(controls,textvariable=self.port,width=20,state="readonly")
        self.ports.pack(side="left",padx=6)
        ttk.Button(controls,text="Refresh",command=self.refresh_ports).pack(side="left")
        self.test_btn=ttk.Button(controls,text="FLASH + TEST ENTIRE BOARD",command=self.start_full); self.test_btn.pack(side="left",padx=12)
        self.bare=tk.BooleanVar(value=False)
        ttk.Checkbutton(controls,text="BARE BOARD: nothing connected except USB",variable=self.bare,command=self.update_drive_lock).pack(side="left",padx=8)
        self.progress=ttk.Progressbar(controls,mode="indeterminate",length=150); self.progress.pack(side="right")

        outer=ttk.Panedwindow(self,orient="horizontal"); outer.pack(fill="both",expand=True,padx=10,pady=4)
        board=ttk.LabelFrame(outer,text="ESP32-S3 SuperMini — 37 exposed pins / 34 GPIO-capable",padding=10); outer.add(board,weight=3)
        details=ttk.Frame(outer,padding=8); outer.add(details,weight=2)

        power=ttk.LabelFrame(board,text="Power / fixed pins",padding=6); power.pack(fill="x",pady=(0,8))
        for i,(name,desc) in enumerate([
            ("5V","USB/VBUS rail — exact voltage needs external meter"),
            ("3V3","Regulator rail — exact voltage needs external meter"),
            ("GND","Ground reference — verify externally with meter/continuity"),
            ("TX/RX","GPIO43/GPIO44 — included in signal-pin tests"),
        ]):
            ttk.Label(power,text=name,width=7).grid(row=i,column=0,sticky="w"); ttk.Label(power,text=desc).grid(row=i,column=1,sticky="w")
        meas=ttk.Frame(power); meas.grid(row=0,column=2,rowspan=4,padx=12,sticky="n")
        ttk.Label(meas,text="Manual meter record").grid(row=0,column=0,columnspan=2)
        ttk.Label(meas,text="5V:").grid(row=1,column=0); self.v5=tk.StringVar(); ttk.Entry(meas,textvariable=self.v5,width=8).grid(row=1,column=1)
        ttk.Label(meas,text="3V3:").grid(row=2,column=0); self.v33=tk.StringVar(); ttk.Entry(meas,textvariable=self.v33,width=8).grid(row=2,column=1)
        self.thermal=tk.BooleanVar(value=False); ttk.Checkbutton(meas,text="FLIR: no hotspot",variable=self.thermal).grid(row=3,column=0,columnspan=2,sticky="w")

        pinarea=ttk.Frame(board); pinarea.pack(fill="both",expand=True)
        left=ttk.Frame(pinarea); left.pack(side="left",fill="both",expand=True,padx=(0,8))
        center=ttk.Label(pinarea,text="USB-C\n\nESP32-S3\nSUPER MINI\n\nCLICK A PIN\nFOR MANUAL TEST",anchor="center",relief="groove",padding=20); center.pack(side="left",fill="y",padx=8)
        right=ttk.Frame(pinarea); right.pack(side="left",fill="both",expand=True,padx=(8,0))
        gpio_pins=[p for p in PINS if p["kind"]=="gpio"]; split=(len(gpio_pins)+1)//2
        for idx,p in enumerate(gpio_pins):
            parent=left if idx<split else right; row=idx if idx<split else idx-split
            cap=[]
            if p["adc"]: cap.append("ADC")
            if p["touch"]: cap.append("TOUCH")
            if p["strap"]: cap.append("STRAP")
            text=f"P{p['physical']:02d}  {p['label']}\n" + (" ".join(cap) if cap else "DIGITAL")
            b=tk.Button(parent,text=text,width=18,height=2,command=lambda pin=p:self.select_pin(pin)); b.grid(row=row,column=0,sticky="ew",pady=2)
            status=ttk.Label(parent,text="NOT TESTED",width=12); status.grid(row=row,column=1,padx=4)
            self.pin_buttons[p["gpio"]]=b; self.pin_status[p["gpio"]]=status; parent.columnconfigure(0,weight=1)

        sel=ttk.LabelFrame(details,text="Selected pin",padding=10); sel.pack(fill="x")
        self.sel_title=tk.StringVar(value="Select a GPIO"); ttk.Label(sel,textvariable=self.sel_title,font=("TkDefaultFont",15,"bold")).pack(anchor="w")
        self.sel_caps=tk.StringVar(value=""); ttk.Label(sel,textvariable=self.sel_caps).pack(anchor="w",pady=(2,8))
        self.sel_result=tk.StringVar(value=""); ttk.Label(sel,textvariable=self.sel_result,wraplength=380).pack(anchor="w",pady=(0,8))
        actions=ttk.Frame(sel); actions.pack(fill="x"); self.action_buttons={}
        for text,cmd in [("TEST PIN","T"),("READ","I"),("PULL UP","U"),("PULL DOWN","D"),("ADC READ","A"),("TOUCH READ","C"),("DRIVE HIGH","H"),("DRIVE LOW","L"),("RELEASE","Z")]:
            b=ttk.Button(actions,text=text,command=lambda c=cmd:self.manual(c)); b.pack(side="left",padx=2,pady=2); self.action_buttons[cmd]=b
        self.update_drive_lock()

        notes=ttk.LabelFrame(details,text="What the test means",padding=8); notes.pack(fill="x",pady=8)
        ttk.Label(notes,wraplength=400,justify="left",text="AUTO SWEEP is non-destructive: pull-up/pull-down/input checks only. DRIVE HIGH/LOW outputs 3.3 V logic and unlocks only after BARE BOARD is confirmed. Firmware cannot independently verify physical pad voltage; the future pogo fixture will.").pack(anchor="w")
        logf=ttk.LabelFrame(details,text="Log",padding=4); logf.pack(fill="both",expand=True)
        self.log=tk.Text(logf,height=18,wrap="word"); self.log.pack(fill="both",expand=True)
        bottom=ttk.Frame(details); bottom.pack(fill="x",pady=6); ttk.Button(bottom,text="Open Results",command=self.open_results).pack(side="right")

    def update_drive_lock(self):
        allow=self.bare.get() and self.selected is not None
        for c in ("H","L"):
            if c in self.action_buttons: self.action_buttons[c].configure(state="normal" if allow else "disabled")

    def refresh_ports(self):
        ports=[]
        if serial: ports=[p.device for p in serial.tools.list_ports.comports() if "ttyACM" in p.device or "ttyUSB" in p.device]
        if not ports: ports=sorted(str(p) for p in Path("/dev").glob("ttyACM*"))+sorted(str(p) for p in Path("/dev").glob("ttyUSB*"))
        self.ports["values"]=ports
        if ports and self.port.get() not in ports: self.port.set(ports[0])

    def select_pin(self,p):
        self.selected=p; caps=["DIGITAL"]
        if p["adc"]: caps.append("ADC")
        if p["touch"]: caps.append("TOUCH")
        if p["strap"]: caps.append("STRAPPING PIN")
        self.sel_title.set(f"Physical P{p['physical']} — {p['label']}"); self.sel_caps.set(" • ".join(caps)); self.sel_result.set("Choose a manual test.")
        self.action_buttons["A"].configure(state="normal" if p["adc"] else "disabled")
        self.action_buttons["C"].configure(state="normal" if p["touch"] else "disabled"); self.update_drive_lock()

    def set_busy(self,b):
        self.running=b; self.test_btn.configure(state="disabled" if b else "normal")
        if b:self.progress.start(10)
        else:self.progress.stop()

    def start_full(self):
        if self.running:return
        if serial is None: messagebox.showerror("Missing pyserial","Install with: sudo apt install python3-serial"); return
        if not self.port.get(): messagebox.showerror("No board","Plug in the board and select its serial port."); return
        self.set_busy(True); self.result.set("TESTING"); self.log.delete("1.0","end"); threading.Thread(target=self.full_worker,daemon=True).start()

    def full_worker(self):
        try:
            self.ui_log("Compiling diagnostic firmware..."); self.run_cmd(["arduino-cli","compile","--fqbn",FQBN,str(FW_DIR)])
            self.ui_log("Uploading..."); self.run_cmd(["arduino-cli","upload","-p",self.port.get(),"--fqbn",FQBN,str(FW_DIR)])
            self.flashed=True; time.sleep(1.1); records=self.read_report("R",end_marker=True,timeout=18); self.records=records; self.save_report(records); self.after(0,lambda:self.apply_records(records))
        except Exception as e: self.after(0,lambda:self.fail(str(e)))

    def run_cmd(self,cmd):
        p=subprocess.run(cmd,capture_output=True,text=True)
        if p.stdout:self.ui_log(p.stdout)
        if p.stderr:self.ui_log(p.stderr)
        if p.returncode: raise RuntimeError("Command failed: "+" ".join(cmd))

    def read_report(self,command,end_marker=False,timeout=5):
        s=serial.Serial(self.port.get(),BAUD,timeout=.35); time.sleep(.35); s.reset_input_buffer(); s.write((command+"\n").encode())
        out=[]; deadline=time.time()+timeout; started=not end_marker
        while time.time()<deadline:
            raw=s.readline().decode(errors="replace").strip()
            if not raw: continue
            self.ui_log(raw)
            if end_marker and raw.startswith("BBT|BEGIN"): started=True; continue
            if end_marker and raw=="BBT|END": break
            if not started or not raw.startswith("BBT|"): continue
            r=parse_record(raw)
            if r: out.append(r)
            if not end_marker and r: break
        s.close()
        if not out: raise RuntimeError("No diagnostic response from board.")
        return out

    def apply_records(self,records):
        final="SUSPECT"
        for r in records:
            if r["kind"]=="GPIO" and "pin" in r:
                pin=int(r["pin"]); status=r["status"]; lab=self.pin_status.get(pin)
                if lab: lab.configure(text=status)
                b=self.pin_buttons.get(pin)
                if b:
                    if status=="FAIL": b.configure(bg="#ffb3b3")
                    elif status=="SUSPECT": b.configure(bg="#ffe6a6")
                    elif status=="PASS": b.configure(bg="#bfe8bf")
            if r["kind"]=="RESULT": final=r["status"]
        self.result.set(final); self.set_busy(False)

    def manual(self,cmd):
        if not self.selected:return
        if serial is None: messagebox.showerror("Missing pyserial","Install with: sudo apt install python3-serial"); return
        if cmd in ("H","L") and not self.bare.get(): messagebox.showwarning("Drive locked","Confirm BARE BOARD first."); return
        gpio=self.selected["gpio"]
        try:
            r=self.read_report(f"{cmd} {gpio}",False,4)[-1]; self.sel_result.set(r["raw"])
            if r["kind"]=="GPIO":
                lab=self.pin_status.get(gpio)
                if lab: lab.configure(text=r["status"])
        except Exception as e: messagebox.showerror("Manual test",str(e))

    def save_report(self,records):
        stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
        data={"timestamp":datetime.now().isoformat(timespec="seconds"),"port":self.port.get(),"thermal_no_hotspot":bool(self.thermal.get()),"meter_5v":self.v5.get().strip(),"meter_3v3":self.v33.get().strip(),"records":records}
        path=RESULTS_DIR/f"board_{stamp}.json"; path.write_text(json.dumps(data,indent=2)); self.ui_log(f"Saved {path}")

    def ui_log(self,s): self.after(0,lambda x=s:self._log(x))
    def _log(self,s): self.log.insert("end",s.rstrip()+"\n"); self.log.see("end")
    def fail(self,msg): self.result.set("ERROR"); self.set_busy(False); self._log(msg); messagebox.showerror("BloomBoard Tester",msg)
    def open_results(self): subprocess.Popen(["xdg-open",str(RESULTS_DIR)])

if __name__=="__main__": App().mainloop()
