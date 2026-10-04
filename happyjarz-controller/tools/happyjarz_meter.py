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
LOG_PATH = os.path.expanduser("~/happyjarz_linein_log.csv")


class LineInApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HAPPY JARZ / CLUB BOX Line-In Bench")
        self.root.geometry("900x800")

        self.q = queue.Queue()
        self.running = True
        self.ser = None
        self.serial_lock = threading.Lock()
        self.max_p2p = 0
        self.samples_seen = 0

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")
        self.status = tk.StringVar(value="Connecting...")
        ttk.Label(top, textvariable=self.status).pack(side="left")
        ttk.Button(top, text="Clear Peak", command=self.clear_peak).pack(side="right")

        meter = ttk.LabelFrame(root, text="GPIO9 Line-In", padding=10)
        meter.pack(fill="x", padx=10, pady=(0, 8))

        self.center_var = tk.StringVar(value="CENTER 0")
        self.range_var = tk.StringVar(value="MIN 0   MAX 0")
        self.p2p_var = tk.StringVar(value="P2P 0   PEAK 0")
        self.headroom_var = tk.StringVar(value="LOW HR 0   HIGH HR 0")
        self.clip_var = tk.StringVar(value="CLIP: no")
        self.test_var = tk.StringVar(value="Waiting for samples...")

        ttk.Label(meter, textvariable=self.center_var, font=("TkDefaultFont", 20, "bold")).pack(anchor="w")
        ttk.Label(meter, textvariable=self.range_var, font=("TkDefaultFont", 13)).pack(anchor="w")
        ttk.Label(meter, textvariable=self.p2p_var, font=("TkDefaultFont", 13)).pack(anchor="w")
        ttk.Label(meter, textvariable=self.headroom_var, font=("TkDefaultFont", 12)).pack(anchor="w")
        ttk.Label(meter, textvariable=self.clip_var, font=("TkDefaultFont", 13, "bold")).pack(anchor="w", pady=(3, 3))
        ttk.Label(meter, textvariable=self.test_var, font=("TkDefaultFont", 11)).pack(anchor="w", pady=(0, 6))

        self.bar = ttk.Progressbar(meter, orient="horizontal", mode="determinate", maximum=4095)
        self.bar.pack(fill="x")

        tests = ttk.LabelFrame(root, text="Bench Tests", padding=10)
        tests.pack(fill="x", padx=10, pady=(0, 8))

        row1 = ttk.Frame(tests)
        row1.pack(fill="x", pady=3)
        ttk.Button(row1, text="Read Once", command=lambda: self.write_line("GET")).pack(side="left")
        ttk.Button(row1, text="RGB Test", command=lambda: self.write_line("TEST RGB")).pack(side="left", padx=6)
        ttk.Button(row1, text="16-Pixel Chase", command=lambda: self.write_line("TEST CHASE")).pack(side="left", padx=6)
        ttk.Button(row1, text="All 16 On", command=lambda: self.write_line("TEST ALL")).pack(side="left", padx=6)
        ttk.Button(row1, text="LEDs Off", command=lambda: self.write_line("TEST OFF")).pack(side="left", padx=6)

        row2 = ttk.Frame(tests)
        row2.pack(fill="x", pady=(8, 2))
        ttk.Label(row2, text="LED brightness").pack(side="left")
        self.bright_var = tk.DoubleVar(value=48)
        self.bright_scale = tk.Scale(row2, from_=4, to=128, resolution=1,
                                     orient="horizontal", variable=self.bright_var,
                                     length=440, command=self.schedule_brightness)
        self.bright_scale.pack(side="left", padx=8, fill="x", expand=True)

        notes = ttk.LabelFrame(root, text="What We Want", padding=10)
        notes.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(notes, text=(
            "No audio: CENTER should be stable roughly around the middle of the ADC range. "
            "Music playing: P2P should rise clearly into the hundreds. "
            "A few dozen counts is too small for useful FFT/EQ. "
            "If CLIP becomes YES or either headroom falls near zero, turn the source down."
        ), wraplength=840).pack(anchor="w")

        ttk.Label(root, text=f"CSV log: {LOG_PATH}", padding=(10, 0, 10, 4)).pack(anchor="w")

        self.log = tk.Text(root, height=18, wrap="none")
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log.configure(state="disabled")

        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w", newline="") as f:
                csv.writer(f).writerow([
                    "timestamp", "center", "minimum", "maximum", "p2p",
                    "low_headroom", "high_headroom", "clip", "brightness", "led_count"
                ])

        threading.Thread(target=self.reader_thread, daemon=True).start()
        self.root.after(50, self.process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def clear_peak(self):
        self.max_p2p = 0
        self.p2p_var.set("P2P 0   PEAK 0")

    def schedule_brightness(self, _value=None):
        if getattr(self, "_bright_after", None):
            self.root.after_cancel(self._bright_after)
        self._bright_after = self.root.after(120, self.send_brightness)

    def send_brightness(self):
        self.write_line(f"SET BRIGHT {int(self.bright_var.get())}")

    def write_line(self, text):
        with self.serial_lock:
            if self.ser and self.ser.is_open:
                self.ser.write((text.strip() + "\n").encode("ascii"))
                self.ser.flush()

    @staticmethod
    def parse_kv(line):
        vals = {}
        for part in line.strip().split("|")[2:]:
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

                self.q.put(("status", f"Connected: {PORT} @ {BAUD} (DTR/RTS OFF)"))
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

                    if line.startswith("HJ|LINE|"):
                        vals = self.parse_kv(line)
                        try:
                            self.q.put((
                                "line",
                                int(vals["CENTER"]),
                                int(vals["MIN"]),
                                int(vals["MAX"]),
                                int(vals["P2P"]),
                                int(vals.get("LOWHR", vals["MIN"])),
                                int(vals.get("HIGHHR", 4095 - int(vals["MAX"]))),
                                int(vals["CLIP"]),
                                int(vals.get("BRIGHT", 48)),
                                int(vals.get("LEDS", 16)),
                            ))
                        except (KeyError, ValueError):
                            pass
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
                elif item[0] == "line":
                    self.update_line(*item[1:])
                elif item[0] == "ack":
                    self.append_log(item[1])
        except queue.Empty:
            pass

        if self.running:
            self.root.after(50, self.process_queue)

    def evaluate(self, center, p2p, low_hr, high_hr, clip):
        if clip:
            return "CLIPPING: turn source volume down."
        if center < 1200 or center > 2900:
            return "CHECK BIAS: center is too far from mid-range."
        if min(low_hr, high_hr) < 250:
            return "HOT: getting close to an ADC rail."
        if p2p < 20:
            return "QUIET: mostly bias/noise, little audio detected."
        if p2p < 100:
            return "TOO SMALL FOR FFT: audio is present, but swing is weak."
        if p2p < 500:
            return "GOOD: usable line-in swing for testing."
        if p2p < 1800:
            return "VERY GOOD: strong signal with useful FFT headroom."
        return "HOT BUT CLEAN: strong signal; keep an eye on headroom."

    def update_line(self, center, minimum, maximum, p2p, low_hr, high_hr, clip, bright, leds):
        self.samples_seen += 1
        self.max_p2p = max(self.max_p2p, p2p)

        self.center_var.set(f"CENTER {center}")
        self.range_var.set(f"MIN {minimum}   MAX {maximum}")
        self.p2p_var.set(f"P2P {p2p}   PEAK {self.max_p2p}")
        self.headroom_var.set(f"LOW HR {low_hr}   HIGH HR {high_hr}")
        self.clip_var.set("CLIP: YES — TURN SOURCE DOWN" if clip else "CLIP: no")
        self.test_var.set(self.evaluate(center, p2p, low_hr, high_hr, clip))
        self.bar["value"] = min(p2p, 4095)

        if int(self.bright_var.get()) != bright:
            self.bright_var.set(bright)

        stamp = time.strftime("%H:%M:%S")
        self.append_log(
            f"{stamp} CENTER={center:4d} MIN={minimum:4d} MAX={maximum:4d} "
            f"P2P={p2p:4d} LHR={low_hr:4d} HHR={high_hr:4d} CLIP={clip} LEDS={leds}"
        )

        with open(LOG_PATH, "a", newline="") as f:
            csv.writer(f).writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"), center, minimum, maximum,
                p2p, low_hr, high_hr, clip, bright, leds
            ])

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        if int(self.log.index("end-1c").split(".")[0]) > 500:
            self.log.delete("1.0", "100.0")
        self.log.configure(state="disabled")

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
    LineInApp(root)
    root.mainloop()
