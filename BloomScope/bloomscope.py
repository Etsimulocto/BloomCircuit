#!/usr/bin/env python3
"""BloomScope 0.1.0 — local USB bench instrument, no browser required."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

VERSION = "0.1.1"
MODES = ("METER", "PWM", "SCOPE", "LOGIC")


def instance_lock():
    """One desktop window on Linux; watcher uses the same advisory lock."""
    if os.name != "posix":
        return None
    import fcntl
    directory = Path.home() / ".cache" / "bloomscope"
    directory.mkdir(parents=True, exist_ok=True)
    lock = open(directory / "app.lock", "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError("BloomScope is already open")
    return lock


def decode(line):
    data = json.loads(line)
    if not isinstance(data, dict) or not isinstance(data.get("type"), str):
        raise ValueError("Invalid protocol record")
    if data["type"] == "capture":
        ts, vs = data.get("t_us"), data.get("values")
        if not isinstance(ts, list) or not isinstance(vs, list) or not 2 <= len(ts) == len(vs) <= 4096:
            raise ValueError("Invalid capture length")
        if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in ts + vs):
            raise ValueError("Invalid capture value")
        if any(b <= a for a, b in zip(ts, ts[1:])):
            raise ValueError("Nonmonotonic timestamps")
    return data


def voltage(mv, gain=1.0):
    return mv * 2.0 * gain / 1000.0  # Fixed equal-resistor divider.


class Link:
    def __init__(self):
        self.events = queue.Queue(maxsize=200)
        self.serial = None
        self.stop = threading.Event()
        self.thread = None
        self.lock = threading.Lock()

    def connect(self, port):
        import serial
        self.close()
        self.serial = serial.Serial(port, 115200, timeout=0.2, write_timeout=0.3)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.read, args=(self.serial, self.stop), daemon=True)
        self.thread.start()

    def post(self, value):
        try:
            self.events.put_nowait(value)
        except queue.Full:
            pass  # Bounded memory; captures may be dropped if UI cannot keep up.

    def read(self, connection, stop):
        buffer = b""
        try:
            while not stop.is_set():
                buffer += connection.read(connection.in_waiting or 1)
                if len(buffer) > 65536:
                    buffer = b""
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        self.post(decode(line.decode("utf-8")))
                    except (ValueError, UnicodeError):
                        pass
        except Exception as exc:
            if not stop.is_set():
                self.post({"type": "disconnected", "message": str(exc)})

    def send(self, command):
        with self.lock:
            if self.serial and self.serial.is_open:
                self.serial.write((command + "\n").encode("ascii"))

    def close(self):
        self.stop.set()
        if self.serial:
            try:
                self.send("STOP")
            except Exception:
                pass
        if self.thread:
            self.thread.join(timeout=0.5)
        if self.serial:
            self.serial.close()
        self.serial = None
        while not self.events.empty():
            try:
                self.events.get_nowait()
            except queue.Empty:
                break


class App:
    def __init__(self, root, demo=False):
        self.root, self.demo = root, demo
        self.link = Link()
        self.ready = False
        self.mode = "METER"
        self.running = False
        self.capture = None
        self.last_rx = self.connected_at = 0
        root.title(f"BloomScope {VERSION}" + (" — DEMO / simulated signals" if demo else ""))
        root.geometry("1000x720")
        root.minsize(820, 620)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#14202e")
        style.configure("TLabel", background="#14202e", foreground="#ecf4fa")
        style.configure("TButton", padding=8)
        root.configure(bg="#14202e")
        box = ttk.Frame(root, padding=18)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="BloomScope", font=("Sans", 24, "bold")).pack(anchor="w")
        ttk.Label(box, text="USB bench doctor · ESP32-S3 · 0–5 V voltage / 3.3 V logic").pack(anchor="w", pady=(0, 12))
        row = ttk.Frame(box); row.pack(fill="x")
        self.port = ttk.Combobox(row, width=30)
        self.port.pack(side="left")
        ttk.Button(row, text="Refresh ports", command=self.ports).pack(side="left", padx=5)
        ttk.Button(row, text="Connect", command=self.connect).pack(side="left")
        ttk.Button(row, text="Disconnect", command=self.disconnect).pack(side="left", padx=5)
        self.status = tk.StringVar(value="DEMO — simulated data" if demo else "Disconnected")
        ttk.Label(box, textvariable=self.status).pack(anchor="w", pady=10)
        row = ttk.Frame(box); row.pack(fill="x")
        for mode in MODES:
            ttk.Button(row, text=mode, command=lambda m=mode: self.select(m)).pack(side="left", padx=(0, 5))
        ttk.Button(row, text="Arm continuity", command=self.arm).pack(side="left")
        row = ttk.Frame(box); row.pack(fill="x", pady=8)
        ttk.Button(row, text="Start", command=self.start).pack(side="left")
        ttk.Button(row, text="STOP / disarm", command=self.pause).pack(side="left", padx=5)
        ttk.Button(row, text="Mute / unmute piezo", command=lambda: self.send("MUTE")).pack(side="left")
        ttk.Button(row, text="Save capture CSV", command=self.save).pack(side="left", padx=5)
        row = ttk.Frame(box); row.pack(fill="x")
        ttk.Button(row, text="Enable + calibrate touch", command=lambda: self.send("TOUCH ON")).pack(side="left")
        ttk.Button(row, text="Disable touch", command=lambda: self.send("TOUCH OFF")).pack(side="left", padx=5)
        ttk.Label(row, text="Voltage calibration gain:").pack(side="left", padx=8)
        self.gain = tk.StringVar(value="1.0000")
        ttk.Entry(row, textvariable=self.gain, width=9).pack(side="left")
        self.readout = tk.StringVar(value="Connect, select a mode, then Start")
        ttk.Label(box, textvariable=self.readout, font=("Monospace", 20, "bold")).pack(anchor="w", pady=18)
        self.canvas = tk.Canvas(box, bg="#09131e", highlightthickness=0, height=300)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _: self.draw())
        ttk.Label(box, text="Touch: GPIO4 mode · GPIO5 start/stop · GPIO6 mute. Continuity must be armed in the app.").pack(anchor="w", pady=(10, 0))
        ttk.Label(box, text="Continuity: UNPOWERED circuits only. Use protected inputs from README. Battery socket stays unused.").pack(anchor="w")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.ports()
        if demo:
            self.ready = True
        self.tick()

    def gain_value(self):
        try:
            n = float(self.gain.get())
            return n if math.isfinite(n) and 0.1 <= n <= 10 else 1.0
        except ValueError:
            return 1.0

    def ports(self):
        try:
            from serial.tools import list_ports
            ps = [p.device for p in list_ports.comports()]
            self.port["values"] = ps
            if ps and self.port.get() not in ps:
                self.port.set(ps[0])
        except ImportError:
            if not self.demo:
                self.status.set("Install pyserial: python3 -m pip install pyserial")

    def connect(self):
        if self.demo:
            return
        self.disconnect()
        try:
            if not self.port.get():
                raise ValueError("Choose a serial port first")
            self.link.connect(self.port.get())
            self.connected_at = time.monotonic()
            self.status.set("Waiting for BloomScope firmware…")
        except Exception as exc:
            self.status.set(str(exc))

    def disconnect(self):
        self.link.close()
        self.ready = self.demo
        self.running = False
        self.connected_at = 0
        self.status.set("DEMO — simulated data" if self.demo else "Disconnected")
        self.readout.set("Stopped — readings are stale")

    def send(self, command):
        if self.demo:
            return
        if not self.ready:
            self.status.set("Connect to BloomScope firmware first")
            return
        try:
            self.link.send(command)
        except Exception as exc:
            self.disconnect()
            self.status.set(str(exc))

    def select(self, mode):
        self.mode = mode
        self.capture = None
        self.draw()
        self.readout.set(mode + " — waiting for samples")
        self.send("MODE " + mode)

    def start(self):
        if self.mode == "CONT":
            self.arm()
        else:
            self.send("START")
            if self.demo:
                self.running = True

    def pause(self):
        self.send("STOP")
        self.running = False
        self.readout.set("Stopped / disarmed — readings are stale")

    def arm(self):
        if not self.ready:
            self.status.set("Connect first")
            return
        if messagebox.askokcancel("Continuity sends test current", "Disconnect the target's USB, battery and all other power. Discharge capacitors.\n\nUse only the dedicated continuity probe and GND.\n\nArm continuity now?"):
            self.send("ARM CONT")
            if self.demo:
                self.mode = "CONT"
                self.running = True

    def record(self, d):
        kind = d["type"]
        if kind == "hello":
            if d.get("device") != "BloomScope" or d.get("protocol") != 1:
                self.disconnect()
                self.status.set("Unsupported device / protocol")
                return
            self.ready = True
            self.status.set("Connected · firmware " + d.get("version", "?"))
        elif kind == "state":
            self.mode = d["mode"]
            self.running = d["running"]
            self.status.set(f"{self.mode} · {'running' if self.running else 'stopped'} · piezo {'muted' if d['muted'] else 'enabled'}" + (" · DEMO" if self.demo else ""))
            if not self.running:
                self.readout.set("Stopped / disarmed — readings are stale")
        elif kind == "meter":
            self.readout.set(f"{voltage(d['adc_mv'], self.gain_value()):.3f} V" + ("  [ADC overrange]" if d['adc_mv'] >= 3050 else ""))
        elif kind == "continuity":
            self.readout.set("CONTINUITY — " + ("BEEP / CLOSED" if d["closed"] else "OPEN") + " (approximate)")
        elif kind == "pwm":
            if d["valid"] and d["period_us"] > 0:
                self.readout.set(f"{1e6/d['period_us']:.1f} Hz   {100*d['high_us']/d['period_us']:.1f}%   HIGH {d['high_us']} µs")
            else:
                self.readout.set(f"No recent pulses · GPIO7 = {d['state']}")
        elif kind == "capture":
            self.capture = d
            duration = d["t_us"][-1] - d["t_us"][0]
            self.readout.set(f"{d['mode']} · {len(d['values'])} points · {duration/1000:.1f} ms · {(len(d['values'])-1)*1e6/duration:.0f} samples/s")
            self.draw()
        elif kind == "disconnected":
            self.disconnect()
            self.status.set("USB disconnected: " + d.get("message", ""))
        elif kind == "error":
            self.status.set(d.get("message", "Device error"))

    def draw(self):
        c = self.canvas; c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        for i in range(1, 10):
            c.create_line(w*i/10, 0, w*i/10, h, fill="#203449")
        for i in range(1, 6):
            c.create_line(0, h*i/6, w, h*i/6, fill="#203449")
        if not self.capture:
            c.create_text(w/2, h/2, text="Scope / logic capture appears here", fill="#8199af")
            return
        d = self.capture; ts, vs = d["t_us"], d["values"]
        xs = [65+(w-85)*(t-ts[0])/(ts[-1]-ts[0]) for t in ts]
        if d["mode"] == "SCOPE":
            points = [p for x, v in zip(xs, vs) for p in (x, h-25-(h-50)*min(6.2, voltage(v, self.gain_value()))/6.2)]
            c.create_line(*points, fill="#51e5bc", width=2)
            c.create_text(35, 15, text="6.2 V", fill="#aec4d8")
            c.create_text(35, h-20, text="0 V", fill="#aec4d8")
        else:
            for j, color in enumerate(("#51e5bc", "#f8c75e", "#a69cff", "#f284b6")):
                low = (j+1)*h/5
                points = []
                previous_y = None
                for x, v in zip(xs, vs):
                    y = low - ((int(v)>>j)&1)*h/10
                    if previous_y is not None:
                        points.extend((x, previous_y))
                    points.extend((x, y)); previous_y = y
                c.create_line(*points, fill=color, width=2)
                c.create_text(30, low-h/20, text=f"CH{j+1}", fill=color)

    def save(self):
        if not self.capture:
            messagebox.showinfo("No capture", "Start Scope or Logic first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            d = self.capture
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["demo", "mode", "time_us", "adc_mv", "probe_volts", "ch1", "ch2", "ch3", "ch4"])
                for t, v in zip(d["t_us"], d["values"]):
                    writer.writerow([self.demo, d["mode"], t, v if d["mode"] == "SCOPE" else "", voltage(v, self.gain_value()) if d["mode"] == "SCOPE" else "", *([(int(v)>>j)&1 for j in range(4)] if d["mode"] == "LOGIC" else [""]*4)])
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))

    def tick(self):
        now = time.monotonic()
        try:
            for _ in range(100):
                d = self.link.events.get_nowait()
                self.last_rx = now
                try:
                    self.record(d)
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    self.status.set("Malformed device record ignored")
        except queue.Empty:
            pass
        if not self.demo and self.link.serial:
            try:
                if self.ready:
                    self.link.send("KEEP")
                    if now-self.last_rx > 4:
                        self.link.send("HELLO")
                    if now-self.last_rx > 8:
                        self.disconnect()
                        self.status.set("Firmware stopped responding — reconnect")
                elif now-self.connected_at > 8:
                    self.disconnect()
                    self.status.set("No BloomScope handshake — flash firmware first")
                else:
                    self.link.send("HELLO")
            except Exception as exc:
                self.disconnect()
                self.status.set(str(exc))
        if self.demo and self.running:
            if self.mode in ("SCOPE", "LOGIC"):
                ts = [i*1000 for i in range(128)]
                vs = [int(825+800*math.sin(i*0.15+now)) if self.mode=="SCOPE" else sum(((i//(5+j*3))%2)<<j for j in range(4)) for i in range(128)]
                self.record({"type":"capture", "mode":self.mode, "t_us":ts, "values":vs})
            elif self.mode=="METER":
                self.record({"type":"meter", "adc_mv":1650})
            elif self.mode=="PWM":
                self.record({"type":"pwm", "valid":True, "period_us":1000, "high_us":500})
            else:
                self.record({"type":"continuity", "closed":int(now)%2==0})
        self.root.after(500, self.tick)

    def close(self):
        self.link.close()
        self.root.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Simulated signals; no hardware")
    parser.add_argument("--port", help="Connect this port when the window opens")
    args = parser.parse_args()
    try:
        desktop_lock = instance_lock()
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(0)
    root = tk.Tk()
    app = App(root, args.demo)
    if args.port and not args.demo:
        app.port.set(args.port)
        root.after(500, app.connect)
    root.mainloop()
