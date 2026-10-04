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
        self.root.title("HAPPY JARZ Live Trim")
        self.root.geometry("760x690")

        self.q = queue.Queue()
        self.running = True
        self.max_raw = 0
        self.ser = None
        self.serial_lock = threading.Lock()
        self.ignore_slider_events = False

        self.floor_var = tk.DoubleVar(value=6)
        self.peak_var = tk.DoubleVar(value=30)
        self.hold_var = tk.DoubleVar(value=240)
        self.bright_var = tk.DoubleVar(value=72)

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")

        self.status = tk.StringVar(value="Connecting...")
        ttk.Label(top, textvariable=self.status).pack(side="left")
        ttk.Button(top, text="Clear Max", command=self.clear_max).pack(side="right")

        meter = ttk.LabelFrame(root, text="Live Meter", padding=10)
        meter.pack(fill="x", padx=10, pady=(0, 8))

        self.raw_var = tk.StringVar(value="RAW 0")
        self.max_var = tk.StringVar(value="MAX 0")
        self.band_var = tk.StringVar(value="TARGET 0   DISPLAY 0")

        ttk.Label(meter, textvariable=self.raw_var, font=("TkDefaultFont", 22, "bold")).pack(anchor="w")
        ttk.Label(meter, textvariable=self.max_var, font=("TkDefaultFont", 14)).pack(anchor="w")
        ttk.Label(meter, textvariable=self.band_var, font=("TkDefaultFont", 14)).pack(anchor="w", pady=(0, 8))

        self.bar = ttk.Progressbar(meter, orient="horizontal", mode="determinate", maximum=100)
        self.bar.pack(fill="x")

        trim = ttk.LabelFrame(root, text="Live Trim", padding=10)
        trim.pack(fill="x", padx=10, pady=(0, 8))

        self.make_slider(trim, "Floor / noise gate", self.floor_var, 0, 50, 1, self.send_floor,
                         "Raise this until fans/room noise stay on root blue.")
        self.make_slider(trim, "Peak / red point", self.peak_var, 8, 100, 1, self.send_peak,
                         "Lower this if normal loud sounds never reach red.")
        self.make_slider(trim, "Peak hold (ms)", self.hold_var, 0, 1000, 10, self.send_hold,
                         "How long a higher color is held before it can fall.")
        self.make_slider(trim, "Brightness", self.bright_var, 4, 255, 1, self.send_bright,
                         "LED output level only; does not change sensitivity.")

        buttons = ttk.Frame(trim)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Save to ESP32", command=self.save_settings).pack(side="left")
        ttk.Button(buttons, text="Reload from ESP32", command=self.get_settings).pack(side="left", padx=8)
        ttk.Button(buttons, text="Defaults", command=self.defaults).pack(side="left")

        ttk.Label(root, text=f"CSV log: {LOG_PATH}", padding=(10, 0, 10, 4)).pack(anchor="w")

        self.log = tk.Text(root, height=12, wrap="none")
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log.configure(state="disabled")

        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w", newline="") as f:
                csv.writer(f).writerow(["timestamp", "raw", "target_band", "display_band"])

        threading.Thread(target=self.reader_thread, daemon=True).start()
        self.root.after(50, self.process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def make_slider(self, parent, label, variable, lo, hi, step, callback, help_text):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)

        left = ttk.Frame(row, width=180)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        ttk.Label(left, text=label).pack(anchor="w")
        ttk.Label(left, text=help_text, wraplength=175, font=("TkDefaultFont", 8)).pack(anchor="w")

        scale = tk.Scale(
            row,
            from_=lo,
            to=hi,
            resolution=step,
            orient="horizontal",
            variable=variable,
            command=lambda _v: self.root.after_cancel(getattr(scale, "_after_id", ""))
            if getattr(scale, "_after_id", None) else None,
            length=430,
        )
        scale.pack(side="left", fill="x", expand=True)

        def schedule_send(_event=None):
            if self.ignore_slider_events:
                return
            if getattr(scale, "_send_after", None):
                self.root.after_cancel(scale._send_after)
            scale._send_after = self.root.after(120, callback)

        scale.configure(command=lambda _v: schedule_send())

    def clear_max(self):
        self.max_raw = 0
        self.max_var.set("MAX 0")

    def write_line(self, text):
        with self.serial_lock:
            if self.ser and self.ser.is_open:
                self.ser.write((text.strip() + "\n").encode("ascii"))
                self.ser.flush()

    def send_floor(self):
        floor = int(self.floor_var.get())
        peak = int(self.peak_var.get())
        if floor >= peak - 1:
            floor = max(0, peak - 2)
            self.floor_var.set(floor)
        self.write_line(f"SET FLOOR {floor}")

    def send_peak(self):
        floor = int(self.floor_var.get())
        peak = int(self.peak_var.get())
        if peak <= floor + 1:
            peak = floor + 2
            self.peak_var.set(peak)
        self.write_line(f"SET PEAK {peak}")

    def send_hold(self):
        self.write_line(f"SET HOLD {int(self.hold_var.get())}")

    def send_bright(self):
        self.write_line(f"SET BRIGHT {int(self.bright_var.get())}")

    def save_settings(self):
        self.write_line("SAVE")

    def get_settings(self):
        self.write_line("GET")

    def defaults(self):
        self.write_line("DEFAULTS")

    def parse_kv(self, line):
        parts = line.strip().split("|")
        vals = {}
        for part in parts[2:]:
            if "=" in part:
                k, v = part.split("=", 1)
                vals[k] = v
        return vals

    def reader_thread(self):
        if serial is None:
            self.q.put(("status", "python3-serial is not installed"))
            return

        while self.running:
            try:
                ser = serial.Serial()
                ser.port = PORT
                ser.baudrate = BAUD
                ser.timeout = 0.25
                ser.write_timeout = 0.25
                ser.dtr = False
                ser.rts = False
                ser.open()
                ser.dtr = False
                ser.rts = False
                self.ser = ser

                self.q.put(("status", f"Connected: {PORT} @ {BAUD}  (DTR/RTS OFF)"))
                time.sleep(0.15)
                self.write_line("STREAM 1")
                self.write_line("GET")

                while self.running and ser.is_open:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line.startswith("HJ|"):
                        continue

                    if line.startswith("HJ|METER|"):
                        vals = self.parse_kv(line)
                        try:
                            self.q.put(("meter", int(float(vals["RAW"])), int(vals["TARGET"]), int(vals["BAND"])))
                        except (KeyError, ValueError):
                            pass
                    elif line.startswith("HJ|CFG|"):
                        vals = self.parse_kv(line)
                        self.q.put(("config", vals))
                    elif line.startswith("HJ|ACK|"):
                        self.q.put(("ack", line))

            except Exception as e:
                self.q.put(("status", f"Disconnected: {e} — retrying..."))
                try:
                    if self.ser:
                        self.ser.close()
                except Exception:
                    pass
                self.ser = None
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
                elif item[0] == "config":
                    self.apply_config(item[1])
                elif item[0] == "ack":
                    self.append_log(item[1])
        except queue.Empty:
            pass

        if self.running:
            self.root.after(50, self.process_queue)

    def apply_config(self, vals):
        try:
            self.ignore_slider_events = True
            if "FLOOR" in vals:
                self.floor_var.set(float(vals["FLOOR"]))
            if "PEAK" in vals:
                self.peak_var.set(float(vals["PEAK"]))
            if "HOLD" in vals:
                self.hold_var.set(float(vals["HOLD"]))
            if "BRIGHT" in vals:
                self.bright_var.set(float(vals["BRIGHT"]))
        finally:
            self.ignore_slider_events = False

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        if int(self.log.index("end-1c").split(".")[0]) > 400:
            self.log.delete("1.0", "80.0")
        self.log.configure(state="disabled")

    def update_meter(self, raw, target, band):
        self.max_raw = max(self.max_raw, raw)
        self.raw_var.set(f"RAW {raw}")
        self.max_var.set(f"MAX {self.max_raw}")
        self.band_var.set(f"TARGET {target}   DISPLAY {band}")

        display_max = max(50, int(self.peak_var.get()) + 10)
        self.bar["maximum"] = display_max
        self.bar["value"] = min(raw, display_max)

        stamp = time.strftime("%H:%M:%S")
        self.append_log(f"{stamp}   RAW={raw:4d}   TARGET={target}   DISPLAY={band}")

        with open(LOG_PATH, "a", newline="") as f:
            csv.writer(f).writerow([time.strftime("%Y-%m-%d %H:%M:%S"), raw, target, band])

    def close(self):
        self.running = False
        try:
            self.write_line("STREAM 0")
            time.sleep(0.05)
        except Exception:
            pass
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
