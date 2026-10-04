#!/usr/bin/env python3
import re, json, time, threading, subprocess
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
FW_DIR = BASE / "firmware"
RESULTS_DIR = BASE / "results"
RESULTS_DIR.mkdir(exist_ok=True)
FQBN = "esp32:esp32:esp32s3:CDCOnBoot=cdc"
BAUD = 115200

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BloomBoard Tester")
        self.geometry("860x680")
        self.minsize(700, 560)
        self.running = False
        self.last_records = []
        self._build_ui()
        self.after(300, self.refresh_ports)

    def _build_ui(self):
        top = ttk.Frame(self, padding=14)
        top.pack(fill="x")
        ttk.Label(top, text="BloomBoard Tester", font=("TkDefaultFont", 18, "bold")).pack(anchor="w")
        ttk.Label(top, text="Blank ESP32-S3 SuperMini incoming / post-solder QA").pack(anchor="w", pady=(2,10))

        row = ttk.Frame(top); row.pack(fill="x")
        ttk.Label(row, text="Board port:").pack(side="left")
        self.port = tk.StringVar()
        self.port_combo = ttk.Combobox(row, textvariable=self.port, width=24, state="readonly")
        self.port_combo.pack(side="left", padx=(8,8))
        ttk.Button(row, text="Refresh", command=self.refresh_ports).pack(side="left")
        self.test_btn = ttk.Button(row, text="TEST BOARD", command=self.start_test)
        self.test_btn.pack(side="right")

        status = ttk.Frame(self, padding=(14,4,14,4)); status.pack(fill="x")
        self.result_var = tk.StringVar(value="READY")
        self.result_lbl = ttk.Label(status, textvariable=self.result_var, font=("TkDefaultFont", 20, "bold"))
        self.result_lbl.pack(side="left")
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=180)
        self.progress.pack(side="right")

        body = ttk.Panedwindow(self, orient="vertical")
        body.pack(fill="both", expand=True, padx=14, pady=8)

        upper = ttk.Frame(body); body.add(upper, weight=3)
        self.tree = ttk.Treeview(upper, columns=("status","detail"), show="headings", height=14)
        self.tree.heading("status", text="Status"); self.tree.heading("detail", text="Detail")
        self.tree.column("status", width=110, anchor="center"); self.tree.column("detail", width=650)
        self.tree.pack(fill="both", expand=True)

        lower = ttk.Frame(body); body.add(lower, weight=2)
        self.log = tk.Text(lower, height=12, wrap="word")
        self.log.pack(fill="both", expand=True)

        bottom = ttk.Frame(self, padding=14); bottom.pack(fill="x")
        self.thermal = tk.BooleanVar(value=False)
        ttk.Checkbutton(bottom, text="FLIR check: no abnormal hotspot", variable=self.thermal).pack(side="left")
        ttk.Button(bottom, text="Open Results Folder", command=self.open_results).pack(side="right")

    def logline(self, s):
        self.log.insert("end", s.rstrip()+"\n")
        self.log.see("end")

    def refresh_ports(self):
        ports=[]
        if serial:
            ports=[p.device for p in serial.tools.list_ports.comports() if "ttyACM" in p.device or "ttyUSB" in p.device]
        if not ports:
            ports=sorted(str(p) for p in Path('/dev').glob('ttyACM*')) + sorted(str(p) for p in Path('/dev').glob('ttyUSB*'))
        self.port_combo['values']=ports
        if ports and self.port.get() not in ports: self.port.set(ports[0])

    def set_busy(self, yes):
        self.running=yes
        self.test_btn.configure(state="disabled" if yes else "normal")
        if yes: self.progress.start(10)
        else: self.progress.stop()

    def start_test(self):
        if self.running: return
        port=self.port.get().strip()
        if not port:
            messagebox.showerror("No board", "Plug in the blank ESP32-S3 and choose its serial port.")
            return
        if serial is None:
            messagebox.showerror("Missing pyserial", "Install with: sudo apt install python3-serial")
            return
        self.tree.delete(*self.tree.get_children()); self.log.delete('1.0','end')
        self.result_var.set("TESTING")
        self.set_busy(True)
        threading.Thread(target=self.worker,args=(port,),daemon=True).start()

    def worker(self, port):
        try:
            self.ui_log("Compiling diagnostic firmware...")
            self.run_cmd(["arduino-cli","compile","--fqbn",FQBN,str(FW_DIR)])
            self.ui_log("Uploading to board...")
            self.run_cmd(["arduino-cli","upload","-p",port,"--fqbn",FQBN,str(FW_DIR)])
            time.sleep(1.2)
            self.ui_log("Reading board diagnostics...")
            records=self.read_report(port)
            self.last_records=records
            self.save_report(port, records)
            result=next((r['status'] for r in records if r['kind']=='RESULT'), 'SUSPECT')
            self.after(0, lambda: self.finish(result, records))
        except Exception as e:
            self.after(0, lambda: self.fail(str(e)))

    def run_cmd(self, cmd):
        p=subprocess.run(cmd, capture_output=True, text=True)
        if p.stdout: self.ui_log(p.stdout)
        if p.stderr: self.ui_log(p.stderr)
        if p.returncode!=0: raise RuntimeError("Command failed: " + " ".join(cmd))

    def read_report(self, port):
        ser=serial.Serial(port, BAUD, timeout=0.5)
        time.sleep(0.5)
        ser.reset_input_buffer(); ser.write(b'R\n')
        records=[]; started=False; deadline=time.time()+12
        while time.time()<deadline:
            raw=ser.readline().decode(errors='replace').strip()
            if not raw: continue
            self.ui_log(raw)
            if raw.startswith('BBT|BEGIN'): started=True; continue
            if not started: continue
            if raw=='BBT|END': break
            if not raw.startswith('BBT|'): continue
            parts=raw.split('|')
            kind=parts[1] if len(parts)>1 else 'INFO'
            status=parts[2] if len(parts)>2 else ''
            detail=' | '.join(parts[3:])
            records.append({'kind':kind,'status':status,'detail':detail,'raw':raw})
        ser.close()
        if not records: raise RuntimeError("No diagnostic report received from board.")
        return records

    def save_report(self, port, records):
        stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
        out={
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'port': port,
            'thermal_no_hotspot': bool(self.thermal.get()),
            'records': records,
        }
        path=RESULTS_DIR/f"board_{stamp}.json"
        path.write_text(json.dumps(out, indent=2))
        self.ui_log(f"Saved: {path}")

    def finish(self, result, records):
        for r in records:
            if r['kind']=='RESULT': continue
            label=r['kind']
            if 'pin=' in r['detail']:
                m=re.search(r'pin=(\d+)', r['detail'])
                if m: label += f" GPIO{m.group(1)}"
            self.tree.insert('', 'end', values=(r['status'], f"{label}: {r['detail']}"))
        if self.thermal.get():
            self.tree.insert('', 'end', values=('PASS','FLIR: no abnormal hotspot observed'))
        else:
            self.tree.insert('', 'end', values=('MANUAL','FLIR: not marked complete'))
        self.result_var.set(result)
        self.set_busy(False)

    def fail(self, msg):
        self.result_var.set('ERROR')
        self.logline(msg)
        self.set_busy(False)
        messagebox.showerror('BloomBoard Tester', msg)

    def ui_log(self, s): self.after(0, lambda x=s: self.logline(x))

    def open_results(self):
        subprocess.Popen(["xdg-open", str(RESULTS_DIR)])

if __name__=='__main__':
    App().mainloop()
