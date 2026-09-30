#!/usr/bin/env python3
"""
HAPPY JARZ Controller v0.2.0
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
APP_VERSION = "0.2.0"
BAUD = 115200
SCAN_SECONDS = 1.0
HANDSHAKE_TIMEOUT = 0.45
LOG_DIR = Path.home() / ".happyjarz"
LOG_FILE = LOG_DIR / "controller.log"

BG = "#0b1020"
PANEL = "#121a2d"
PANEL_2 = "#172238"
BORDER = "#25324a"
TEXT = "#eef3ff"
MUTED = "#8fa2c6"
ACCENT = "#8b5cf6"
ACCENT_2 = "#22d3ee"
GOOD = "#34d399"
WARN = "#f59e0b"
DANGER = "#fb7185"


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
        self.geometry("980x760")
        self.minsize(900, 690)
        self.configure(bg=BG)

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
        self.led_swatches = {}
        self._brightness_after = None

        self._configure_style()
        self._build_ui()
        self.after(80, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._log(f"{APP_NAME} v{APP_VERSION} started")

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL_2,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                        font=("TkDefaultFont", 10))
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Panel2.TFrame", background=PANEL_2)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Title.TLabel", background=BG, foreground=TEXT,
                        font=("TkDefaultFont", 24, "bold"))
        style.configure("Section.TLabel", background=PANEL, foreground=TEXT,
                        font=("TkDefaultFont", 11, "bold"))
        style.configure("Value.TLabel", background=PANEL, foreground=ACCENT_2,
                        font=("TkFixedFont", 12, "bold"))
        style.configure("TouchValue.TLabel", background=PANEL_2, foreground=TEXT,
                        font=("TkFixedFont", 15, "bold"))
        style.configure("TButton", background=PANEL_2, foreground=TEXT,
                        borderwidth=0, padding=(12, 8))
        style.map("TButton", background=[("active", "#24324d")], foreground=[("active", "#ffffff")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                        borderwidth=0, padding=(12, 9), font=("TkDefaultFont", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#a78bfa")])
        style.configure("Danger.TButton", background="#3a1e2a", foreground="#ffd5df",
                        borderwidth=0, padding=(12, 8))
        style.map("Danger.TButton", background=[("active", "#5a2438")])
        style.configure("TScale", background=PANEL, troughcolor="#26334c")
        style.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2,
                        foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER, padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_2)],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", PANEL_2)])
        style.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=PANEL,
                        bordercolor=PANEL, arrowcolor=MUTED)

    @staticmethod
    def _card(parent, padding=14):
        outer = tk.Frame(parent, bg=BORDER, bd=0)
        inner = ttk.Frame(outer, style="Panel.TFrame", padding=padding)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return outer, inner

    def _build_ui(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 14))

        left = ttk.Frame(header)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="HAPPY JARZ", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="LIGHT + TOUCH CONTROL CONSOLE  •  BLOOMCORE",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

        self.status_pill = tk.Label(
            header, textvariable=self.connection_var, bg="#2a2417", fg="#ffd77a",
            padx=14, pady=8, font=("TkDefaultFont", 10, "bold"), bd=0
        )
        self.status_pill.pack(side="right", padx=(12, 0))

        device_outer, device = self._card(root, 12)
        device_outer.pack(fill="x", pady=(0, 12))
        ttk.Label(device, text="DEVICE", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 18))
        for col, (label, key) in enumerate((("SERIAL", "serial"), ("HARDWARE", "hw"), ("FIRMWARE", "fw")), start=1):
            box = ttk.Frame(device, style="Panel.TFrame")
            box.grid(row=0, column=col, sticky="ew", padx=8)
            ttk.Label(box, text=label, style="PanelMuted.TLabel", font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
            ttk.Label(box, textvariable=self.identity_vars[key], style="Value.TLabel").pack(anchor="w")
            device.columnconfigure(col, weight=1)

        lights = ttk.Frame(root)
        lights.pack(fill="x", pady=(0, 12))
        lights.columnconfigure(0, weight=1)
        lights.columnconfigure(1, weight=1)

        for led in (1, 2):
            outer, box = self._card(lights, 14)
            outer.grid(row=0, column=led - 1, sticky="nsew", padx=(0, 6) if led == 1 else (6, 0))

            top = ttk.Frame(box, style="Panel.TFrame")
            top.pack(fill="x")
            ttk.Label(top, text=f"LIGHT {led}", style="Section.TLabel").pack(side="left")
            swatch = tk.Label(top, text="     ", bg="#%02x%02x%02x" % self.led_colors[led],
                              relief="flat", bd=0, padx=4, pady=5)
            swatch.pack(side="right")
            self.led_swatches[led] = swatch

            ttk.Label(box, text="Independent APA106 output", style="PanelMuted.TLabel").pack(anchor="w", pady=(2, 12))
            ttk.Button(box, text="Choose color", style="Accent.TButton",
                       command=lambda n=led: self._choose_color(n)).pack(fill="x")

            row = ttk.Frame(box, style="Panel.TFrame")
            row.pack(fill="x", pady=(8, 0))
            ttk.Button(row, text="White test", command=lambda n=led: self._set_led(n, 255, 255, 255)).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Off", style="Danger.TButton",
                       command=lambda n=led: self._set_led(n, 0, 0, 0)).pack(side="left", fill="x", expand=True, padx=(8, 0))

        settings_outer, settings = self._card(root, 14)
        settings_outer.pack(fill="x", pady=(0, 12))
        ttk.Label(settings, text="SCENE CONTROL", style="Section.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(settings, text="Brightness", style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(12, 0))

        self.brightness_label = ttk.Label(settings, text="75%", style="Value.TLabel", width=5)
        self.brightness_label.grid(row=1, column=2, sticky="e", pady=(12, 0))
        scale = ttk.Scale(settings, from_=0, to=100, orient="horizontal", command=self._brightness_changed)
        scale.grid(row=1, column=1, sticky="ew", padx=10, pady=(12, 0))
        scale.set(self.brightness_var.get())

        ttk.Label(settings, text="Pattern", style="PanelMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(12, 0))
        patterns = ttk.Combobox(settings, state="readonly", textvariable=self.pattern_var,
                                values=("OFF", "SOLID", "FADE", "RAINBOW", "PULSE"))
        patterns.grid(row=2, column=1, sticky="ew", padx=10, pady=(12, 0))
        patterns.bind("<<ComboboxSelected>>", lambda _e: self.link.send(f"SET PATTERN {self.pattern_var.get()}"))
        ttk.Button(settings, text="Save to Jar", style="Accent.TButton",
                   command=lambda: self.link.send("SAVE")).grid(row=2, column=2, sticky="e", pady=(12, 0))
        settings.columnconfigure(1, weight=1)

        touch_outer, touch = self._card(root, 12)
        touch_outer.pack(fill="x", pady=(0, 12))
        ttk.Label(touch, text="LIVE CAPACITIVE TOUCH", style="Section.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        labels = (("COLOR 1", "c1"), ("COLOR 2", "c2"), ("CYCLE UP", "up"), ("CYCLE DOWN", "down"))
        for col, (name, key) in enumerate(labels):
            tile = ttk.Frame(touch, style="Panel2.TFrame", padding=10)
            tile.grid(row=1, column=col, sticky="nsew", padx=(0 if col == 0 else 5, 0 if col == 3 else 5))
            ttk.Label(tile, text=name, background=PANEL_2, foreground=MUTED,
                      font=("TkDefaultFont", 8, "bold")).pack()
            ttk.Label(tile, textvariable=self.touch_vars[key], style="TouchValue.TLabel").pack(pady=(3, 0))
            touch.columnconfigure(col, weight=1)

        bottom = ttk.Frame(root)
        bottom.pack(fill="both", expand=True)
        bottom.columnconfigure(0, weight=0)
        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(0, weight=1)

        diag_outer, diag = self._card(bottom, 12)
        diag_outer.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        ttk.Label(diag, text="DIAGNOSTICS", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Button(diag, text="RGB test", command=lambda: self.link.send("TEST RGB")).pack(fill="x")
        ttk.Button(diag, text="Touch test", command=lambda: self.link.send("TEST TOUCH")).pack(fill="x", pady=6)
        ttk.Button(diag, text="Get status", command=lambda: self.link.send("GET STATUS")).pack(fill="x")
        ttk.Button(diag, text="Ping", command=lambda: self.link.send("PING")).pack(fill="x", pady=(6, 0))

        log_outer, logs = self._card(bottom, 8)
        log_outer.grid(row=0, column=1, sticky="nsew")
        ttk.Label(logs, text="SESSION LOG", style="Section.TLabel").pack(anchor="w", padx=4, pady=(2, 6))
        log_body = ttk.Frame(logs, style="Panel.TFrame")
        log_body.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_body, height=9, wrap="word", state="disabled",
                                bg="#080d18", fg="#b9c7df", insertbackground=TEXT,
                                selectbackground="#3b4d70", relief="flat", bd=0,
                                padx=10, pady=8, font=("TkFixedFont", 9))
        scroll = ttk.Scrollbar(log_body, orient="vertical", command=self.log_text.yview)
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
        if led in self.led_swatches:
            self.led_swatches[led].configure(bg=f"#{r:02x}{g:02x}{b:02x}")
        self.link.send(f"SET LED{led} COLOR {r} {g} {b}")

    def _brightness_changed(self, value):
        n = max(0, min(100, int(float(value))))
        self.brightness_var.set(n)
        self.brightness_label.configure(text=f"{n}%")
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
                    self.connection_var.set(f"CONNECTED  •  {payload['port']}")
                    self.status_pill.configure(bg="#163429", fg="#8df0c7")
                    self._log(f"Connected on {payload['port']}")
                    self._handle_line(payload["identity"])
                elif kind == "disconnected":
                    self.connection_var.set("WAITING FOR JAR")
                    self.status_pill.configure(bg="#2a2417", fg="#ffd77a")
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
