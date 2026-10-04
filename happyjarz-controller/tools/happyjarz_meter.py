#!/usr/bin/env python3
import csv
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

try:
    import serial
except ImportError:
    serial = None

PORT = "/dev/ttyACM0"
BAUD = 115200
LOG_PATH = os.path.expanduser("~/happyjarz_meter_log.csv")

class MeterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HAPPY JARZ Meter")
        self.root.geometry("620x520")

        self.q = queue.Queue()
        self.running = True
        self.max_raw = 0
        self.ser = None

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")

        self.status = tk.StringVar(value="Connecting...")
        ttk.Label(top, textvariable=self.status).pack(side="left")
        ttk.Button(top, text="Clear Max", command=self.clear_max).pack(side="right")

        meter = ttk.Frame(root, padding=(10, 0, 10, 10))
        meter.pack(fill="x")

        self.raw_var = tk.StringVar(value="RAW 0")
        self.max_var = tk.StringVar(value="MAX 0")
        self.band_var = tk.StringVar(value="TARGET 0   DISPLAY 0")

        ttk.Label(meter, textvariable=self.raw_var, font=("TkDefaultFont", 22, "bold")).pack(anchor="w")
        ttk.Label(meter, textvariable=self.max_var, font=("TkDefaultFont", 14)).pack(anchor="w")
        ttk.Label(meter, textvariable=self.band_var, font=("TkDefaultFont", 14)).pack(anchor="w", pady=(0, 8))

        self.bar = ttk.Progressbar(meter, orient="horizontal", mode="determinate", maximum=100)
        self.bar.pack(fill="x")

        ttk.Label(root, text=f"CSV log: {LOG_PATH}", padding=(10, 0, 10, 4)).pack(anchor="w")

        self.log = tk.Text(root, height=18, wrap="none")
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log.configure(state="disabled")

        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w", newline="") as f:
                csv.writer(f).writerow(["timestamp", "raw", "target_band", "display_band"])

        threading.Thread(target=self.reader_thread, daemon=True).start()
        self.root.after(50, self.process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def clear_max(self):
        self.max_raw = 0
        self.max_var.set("MAX 0")

    def parse_line(self, line):
        if not line.startswith("HJ|METER|"):
            return None
        parts = line.strip().split("|")
        vals = {}
        for part in parts[2:]:
            if "=" in part:
                k, v = part.split("=", 1)
                vals[k] = v
        try:
            return int(float(vals["RAW"])), int(vals["TARGET"]), int(vals["BAND"])
        except (KeyError, ValueError):
            return None

    def reader_thread(self):
        if serial is None:
            self.q.put(("status", "python3-serial is not installed"))
            return

        while self.running:
            try:
                self.ser = serial.Serial()
                self.ser.port = PORT
                self.ser.baudrate = BAUD
                self.ser.timeout = 0.5
                self.ser.dtr = False
                self.ser.rts = False
                self.ser.open()
                # Explicitly keep both modem-control lines low after opening.
                self.ser.dtr = False
                self.ser.rts = False
                self.q.put(("status", f"Connected: {PORT} @ {BAUD}  (DTR/RTS OFF)"))

                while self.running and self.ser.is_open:
                    raw = self.ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    parsed = self.parse_line(line)
                    if parsed:
                        self.q.put(("meter", *parsed))
            except Exception as e:
                self.q.put(("status", f"Disconnected: {e}  — retrying..."))
                try:
                    if self.ser:
                        self.ser.close()
                except Exception:
                    pass
                time.sleep(1.0)

    def process_queue(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "status":
                    self.status.set(item[1])
                elif item[0] == "meter":
                    _, raw, target, band = item
                    self.update_meter(raw, target, band)
        except queue.Empty:
            pass
        if self.running:
            self.root.after(50, self.process_queue)

    def update_meter(self, raw, target, band):
        self.max_raw = max(self.max_raw, raw)
        self.raw_var.set(f"RAW {raw}")
        self.max_var.set(f"MAX {self.max_raw}")
        self.band_var.set(f"TARGET {target}   DISPLAY {band}")
        self.bar["value"] = min(raw, 100)

        stamp = time.strftime("%H:%M:%S")
        row = f"{stamp}   RAW={raw:4d}   TARGET={target}   DISPLAY={band}\n"
        self.log.configure(state="normal")
        self.log.insert("end", row)
        self.log.see("end")
        # keep the on-screen log compact
        if int(self.log.index("end-1c").split(".")[0]) > 500:
            self.log.delete("1.0", "100.0")
        self.log.configure(state="disabled")

        with open(LOG_PATH, "a", newline="") as f:
            csv.writer(f).writerow([time.strftime("%Y-%m-%d %H:%M:%S"), raw, target, band])

    def close(self):
        self.running = False
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    MeterApp(root)
    root.mainloop()
