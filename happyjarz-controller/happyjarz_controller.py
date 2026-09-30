#!/usr/bin/env python3
"""
HAPPY JARZ Controller v0.1
BloomCore-style bench/service UI for Windows, Raspberry Pi, and Linux.

Failure boundary:
- This program owns USB discovery, UI, logging, and protocol commands.
- It does NOT own APA106 pulse timing.
- If local ESP32 LED diagnostics pass but this app fails, debug this layer first.
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import colorchooser, ttk

import serial
from serial.tools import list_ports

APP_NAME = "HAPPY JARZ Controller"
APP_VERSION = "0.1"
BAUD = 115200
SCAN_SECONDS = 1.0
HANDSHAKE_TIMEOUT = 0.45
LOG_DIR = Path.home() / ".happyjarz"
LOG_FILE = LOG_DIR / "controller.log"


class JarSerial:
    def __init__(self, events: queue.Queue):
        self.events = events
        self.ser: serial.Serial | None = None
        self.port_name: str | None = None
        self.running = True
        self.lock = threading.Lock()
        self.reader_thread: threading.Thread | None = None
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()

    def _emit(self, kind: str, payload=None):
        self.events.put((kind, payload))

    def _scan_loop(self):
        while self.running:
            if self.ser is None or not self.ser.is_open:
                self._try_ports()
            time.sleep(SCAN_SECONDS)

    def _try_ports(self):
        for port in list_ports.comports():
            if not self.running or self.ser is not None:
                return
            try:
                probe = serial.Serial(port.device, BAUD, timeout=HANDSHAKE_TIMEOUT, write_timeout=0.5)
                time.sleep(0.12)
                probe.reset_input_buffer()
                probe.write(b"HELLO\n")
                probe.flush()
                deadline = time.time() + HANDSHAKE_TIMEOUT
                identity = None
                while time.time() < deadline:
                    line = probe.readline().decode("utf-8", errors="replace").strip()
                    if line.startswith("HJ|IDENTITY|"):
                        identity = line
                        break
                if identity:
                    self.ser = probe
                    self.port_name = port.device
                    self._emit("connected", {"port": port.device, "identity": identity})
                    self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
                    self.reader_thread.start()
                    self.send("STREAM TOUCH ON")
                    self.send("GET STATUS")
                    return
                probe.close()
            except (serial.SerialException, OSError):
                continue

    def _reader_loop(self):
        while self.running and self.ser is not None and self.ser.is_open:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self._emit("line", line)
            except (serial.SerialException, OSError) as exc:
                self._emit("log", f"Serial connection lost: {exc}")
                break
        self._disconnect_internal()

    def send(self, command: str):
        with self.lock:
            if not self.ser or not self.ser.is_open:
                self._emit("log", f"Not connected; command skipped: {command}")
                return False
            try:
                self.ser.write((command.strip() + "\n").encode("utf-8"))
                self.ser.flush()
                self._emit("tx", command.strip())
                return True
            except (serial.SerialException, OSError) as exc:
                self._emit("log", f"Write failed: {exc}")
                self._disconnect_internal()
                return False

    def _disconnect_internal(self):
        old_port = self.port_name
        with self.lock:
            if self.ser is not None:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None
            self.port_name = None
        if old_port:
            self._emit("disconnected", old_port)

    def close(self):
        self.running = False
        self._disconnect_internal()


class HappyJarzApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("830x650")
        self.minsize(760, 590)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.events: queue.Queue = queue.Queue()
        self.link = JarSerial(self.events)

        self.identity_vars = {
            "serial": tk.StringVar(value="—"),
            "hw": tk.StringVar(value="—"),
            "fw": tk.StringVar(value="—"),
        }
        self.connection_var = tk.StringVar(value="WAITING FOR JAR")
        self.touch_vars = {
            "c1": tk.StringVar(value="—"),
            "c2": tk.StringVar(value="—"),
            "up": tk.StringVar(value="—"),
            "down": tk.StringVar(value="—"),
        }
        self.brightness_var = tk.IntVar(value=75)
        self.pattern_var = tk.StringVar(value="SOLID")
        self.led_colors = {1: (255, 80, 120), 2: (80, 120, 255)}

        self._build_ui()
        self.after(80, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._log(f"{APP_NAME} v{APP_VERSION} started")

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text="HAPPY JARZ CONTROLLER", font=("TkDefaultFont", 18, "bold")).pack(side="left")
        self.status_label = ttk.Label(header, textvariable=self.connection_var, font=("TkDefaultFont", 11, "bold"))
        self.status_label.pack(side="right")

        identity = ttk.LabelFrame(root, text="Device", padding=10)
        identity.pack(fill="x", pady=(12, 8))
        for col, (label, key) in enumerate((("Serial", "serial"), ("Hardware", "hw"), ("Firmware", "fw"))):
            ttk.Label(identity, text=f"{label}:").grid(row=0, column=col * 2, sticky="e", padx=(4, 3))
            ttk.Label(identity, textvariable=self.identity_vars[key]).grid(row=0, column=col * 2 + 1, sticky="w", padx=(0, 18))

        control_row = ttk.Frame(root)
        control_row.pack(fill="x", pady=4)
        control_row.columnconfigure(0, weight=1)
        control_row.columnconfigure(1, weight=1)

        for led in (1, 2):
            box = ttk.LabelFrame(control_row, text=f"Light {led}", padding=12)
            box.grid(row=0, column=led - 1, sticky="nsew", padx=(0, 6) if led == 1 else (6, 0))
            ttk.Button(box, text="Choose color…", command=lambda n=led: self._choose_color(n)).pack(fill="x")
            ttk.Button(box, text="Off", command=lambda n=led: self._set_led(n, 0, 0, 0)).pack(fill="x", pady=(6, 0))
            ttk.Button(box, text="White test", command=lambda n=led: self._set_led(n, 255, 255, 255)).pack(fill="x", pady=(6, 0))

        settings = ttk.LabelFrame(root, text="Shared controls", padding=10)
        settings.pack(fill="x", pady=8)
        ttk.Label(settings, text="Brightness").grid(row=0, column=0, sticky="w")
        scale = ttk.Scale(settings, from_=0, to=100, orient="horizontal", command=self._brightness_changed)
        scale.set(self.brightness_var.get())
        scale.grid(row=0, column=1, sticky="ew", padx=8)
        self.brightness_label = ttk.Label(settings, text="75%", width=5)
        self.brightness_label.grid(row=0, column=2)
        ttk.Label(settings, text="Pattern").grid(row=1, column=0, sticky="w", pady=(8, 0))
        patterns = ttk.Combobox(settings, state="readonly", textvariable=self.pattern_var,
                                values=("OFF", "SOLID", "FADE", "RAINBOW", "PULSE"))
        patterns.grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        patterns.bind("<<ComboboxSelected>>", lambda _e: self.link.send(f"SET PATTERN {self.pattern_var.get()}"))
        ttk.Button(settings, text="Save to Jar", command=lambda: self.link.send("SAVE")).grid(row=1, column=2, pady=(8, 0))
        settings.columnconfigure(1, weight=1)

        touch = ttk.LabelFrame(root, text="Live capacitive touch", padding=10)
        touch.pack(fill="x", pady=8)
        labels = (("COLOR 1", "c1"), ("COLOR 2", "c2"), ("CYCLE UP", "up"), ("CYCLE DOWN", "down"))
        for col, (name, key) in enumerate(labels):
            ttk.Label(touch, text=name, font=("TkDefaultFont", 9, "bold")).grid(row=0, column=col, padx=12)
            ttk.Label(touch, textvariable=self.touch_vars[key], font=("TkFixedFont", 12)).grid(row=1, column=col, padx=12, pady=(2, 0))
            touch.columnconfigure(col, weight=1)

        diag = ttk.LabelFrame(root, text="Diagnostics", padding=10)
        diag.pack(fill="x", pady=8)
        ttk.Button(diag, text="RGB test", command=lambda: self.link.send("TEST RGB")).pack(side="left")
        ttk.Button(diag, text="Touch test", command=lambda: self.link.send("TEST TOUCH")).pack(side="left", padx=8)
        ttk.Button(diag, text="Get status", command=lambda: self.link.send("GET STATUS")).pack(side="left")
        ttk.Button(diag, text="Ping", command=lambda: self.link.send("PING")).pack(side="left", padx=8)

        logs = ttk.LabelFrame(root, text="Session log", padding=6)
        logs.pack(fill="both", expand=True, pady=(8, 0))
        self.log_text = tk.Text(logs, height=10, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(logs, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _choose_color(self, led: int):
        initial = "#%02x%02x%02x" % self.led_colors[led]
        _rgb, hex_color = colorchooser.askcolor(color=initial, title=f"Light {led} color")
        if not hex_color:
            return
        rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        self.led_colors[led] = rgb
        self._set_led(led, *rgb)

    def _set_led(self, led: int, r: int, g: int, b: int):
        self.led_colors[led] = (r, g, b)
        self.link.send(f"SET LED{led} COLOR {r} {g} {b}")

    def _brightness_changed(self, value):
        n = max(0, min(100, int(float(value))))
        self.brightness_var.set(n)
        self.brightness_label.configure(text=f"{n}%")
        if not hasattr(self, "_brightness_after"):
            self._brightness_after = None
        if self._brightness_after:
            self.after_cancel(self._brightness_after)
        self._brightness_after = self.after(120, lambda: self.link.send(f"SET BRIGHTNESS {n}"))

    @staticmethod
    def _parse_fields(line: str):
        fields = {}
        for part in line.split("|")[2:]:
            if "=" in part:
                key, value = part.split("=", 1)
                fields[key.strip()] = value.strip()
        return fields

    def _handle_line(self, line: str):
        self._log(f"RX  {line}")
        if line.startswith("HJ|IDENTITY|"):
            fields = self._parse_fields(line)
            for key in ("serial", "hw", "fw"):
                if key in fields:
                    self.identity_vars[key].set(fields[key])
        elif line.startswith("HJ|TOUCH|"):
            fields = self._parse_fields(line)
            for key in self.touch_vars:
                if key in fields:
                    self.touch_vars[key].set(fields[key])
        elif line.startswith("HJ|STATUS|"):
            fields = self._parse_fields(line)
            if "brightness" in fields:
                try:
                    n = int(fields["brightness"])
                    self.brightness_var.set(n)
                    self.brightness_label.configure(text=f"{n}%")
                except ValueError:
                    pass
            if "pattern" in fields:
                self.pattern_var.set(fields["pattern"])

    def _drain_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "connected":
                    self.connection_var.set(f"CONNECTED • {payload['port']}")
                    self._log(f"Connected on {payload['port']}")
                    self._handle_line(payload["identity"])
                elif kind == "disconnected":
                    self.connection_var.set("WAITING FOR JAR")
                    self._log(f"Disconnected from {payload}; scanning continues")
                    for var in self.touch_vars.values():
                        var.set("—")
                elif kind == "line":
                    self._handle_line(payload)
                elif kind == "tx":
                    self._log(f"TX  {payload}")
                elif kind == "log":
                    self._log(payload)
        except queue.Empty:
            pass
        self.after(80, self._drain_events)

    def _log(self, message: str):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{stamp}  {message}\n"
        try:
            with LOG_FILE.open("a", encoding="utf-8") as fp:
                fp.write(line)
        except OSError:
            pass
        if hasattr(self, "log_text"):
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

    def _on_close(self):
        self.link.close()
        self.destroy()


if __name__ == "__main__":
    HappyJarzApp().mainloop()
