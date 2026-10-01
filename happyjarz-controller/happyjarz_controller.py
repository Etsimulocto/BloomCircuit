#!/usr/bin/env python3
"""HAPPY JARZ Controller v0.3.0 — BloomCore setup, control, and service UI.

Known-good v0.2 light/touch commands are preserved. New Wi-Fi/time/alarm/timer/
display controls are forward-compatible with the planned firmware protocol in
APP_PROTOCOL_V0_3.md. Unsupported commands may return HJ|ERR on older firmware.
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
APP_VERSION = "0.3.0"
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
GOOD_BG = "#163429"
GOOD_FG = "#8df0c7"
WAIT_BG = "#2a2417"
WAIT_FG = "#ffd77a"


class JarSerial:
    def __init__(self, events: queue.Queue):
        self.events = events
        self.ser: serial.Serial | None = None
        self.port_name: str | None = None
        self.running = True
        self.lock = threading.Lock()
        self.reader_thread: threading.Thread | None = None
        threading.Thread(target=self._scan_loop, daemon=True).start()

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

    @staticmethod
    def _safe_log_command(command: str) -> str:
        upper = command.upper()
        if upper.startswith("SET WIFI PASSWORD "):
            return "SET WIFI PASSWORD ********"
        return command

    def send(self, command: str):
        command = command.strip()
        with self.lock:
            if not self.ser or not self.ser.is_open:
                self._emit("log", f"Not connected; command skipped: {self._safe_log_command(command)}")
                return False
            try:
                self.ser.write((command + "\n").encode("utf-8"))
                self.ser.flush()
                self._emit("tx", self._safe_log_command(command))
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
        self.geometry("1080x760")
        self.minsize(900, 650)
        self.configure(bg=BG)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.events: queue.Queue = queue.Queue()
        self.link = JarSerial(self.events)

        self.identity_vars = {k: tk.StringVar(value="—") for k in ("serial", "hw", "fw")}
        self.connection_var = tk.StringVar(value="WAITING FOR JAR")
        self.touch_vars = {k: tk.StringVar(value="—") for k in ("up", "down", "left", "right", "a", "b")}
        self.brightness_var = tk.IntVar(value=75)
        self.pattern_var = tk.StringVar(value="SOLID")
        self.led_colors = {1: (255, 80, 120), 2: (80, 120, 255)}
        self.led_swatches = {}
        self._brightness_after = None

        self.wifi_ssid = tk.StringVar()
        self.wifi_password = tk.StringVar()
        self.wifi_state = tk.StringVar(value="UNKNOWN")
        self.timezone_var = tk.StringVar(value="America/Chicago")
        self.time_state = tk.StringVar(value="NOT SYNCED")
        self.alarm_time = tk.StringVar(value="07:30")
        self.alarm_enabled = tk.BooleanVar(value=False)
        self.timer_minutes = tk.StringVar(value="60")
        self.timer_enabled = tk.BooleanVar(value=False)
        self.display_brightness = tk.IntVar(value=80)
        self.screensaver_var = tk.StringVar(value="CLOCK")
        self.screensaver_delay = tk.StringVar(value="5")

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
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("TkDefaultFont", 21, "bold"))
        style.configure("Section.TLabel", background=PANEL, foreground=TEXT, font=("TkDefaultFont", 10, "bold"))
        style.configure("Value.TLabel", background=PANEL, foreground=ACCENT_2, font=("TkFixedFont", 11, "bold"))
        style.configure("TouchValue.TLabel", background=PANEL_2, foreground=TEXT, font=("TkFixedFont", 13, "bold"))
        style.configure("TButton", background=PANEL_2, foreground=TEXT, borderwidth=0, padding=(10, 6))
        style.map("TButton", background=[("active", "#24324d")], foreground=[("active", "#ffffff")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", borderwidth=0,
                        padding=(10, 7), font=("TkDefaultFont", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#a78bfa")])
        style.configure("Danger.TButton", background="#3a1e2a", foreground="#ffd5df", borderwidth=0, padding=(10, 6))
        style.map("Danger.TButton", background=[("active", "#5a2438")])
        style.configure("TScale", background=PANEL, troughcolor="#26334c")
        style.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT,
                        arrowcolor=TEXT, bordercolor=BORDER, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_2)], foreground=[("readonly", TEXT)])
        style.configure("TEntry", fieldbackground=PANEL_2, foreground=TEXT, bordercolor=BORDER, padding=6)
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_2, foreground=MUTED, padding=(12, 7))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "#ffffff")])
        style.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=PANEL, bordercolor=PANEL, arrowcolor=MUTED)

    @staticmethod
    def _card(parent, padding=10):
        outer = tk.Frame(parent, bg=BORDER, bd=0)
        inner = ttk.Frame(outer, style="Panel.TFrame", padding=padding)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return outer, inner

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        self._build_header(root)

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        control = ttk.Frame(notebook, padding=8)
        setup = ttk.Frame(notebook, padding=8)
        display = ttk.Frame(notebook, padding=8)
        service = ttk.Frame(notebook, padding=8)
        notebook.add(control, text="LIGHTS + CONTROL")
        notebook.add(setup, text="WIFI + CLOCK")
        notebook.add(display, text="DISPLAY + INPUT")
        notebook.add(service, text="SERVICE")

        self._build_control_tab(control)
        self._build_setup_tab(setup)
        self._build_display_tab(display)
        self._build_service_tab(service)

    def _build_header(self, root):
        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 8))
        left = ttk.Frame(header)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="HAPPY JARZ", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="SETUP • CONTROL • SERVICE  /  BLOOMCORE", style="Muted.TLabel").pack(anchor="w")
        self.status_pill = tk.Label(header, textvariable=self.connection_var, bg=WAIT_BG, fg=WAIT_FG,
                                    padx=12, pady=6, font=("TkDefaultFont", 9, "bold"), bd=0)
        self.status_pill.pack(side="right", padx=(10, 0))

        outer, device = self._card(root, 8)
        outer.pack(fill="x", pady=(0, 8))
        ttk.Label(device, text="DEVICE", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 14))
        for col, (label, key) in enumerate((("SERIAL", "serial"), ("HARDWARE", "hw"), ("FIRMWARE", "fw")), start=1):
            box = ttk.Frame(device, style="Panel.TFrame")
            box.grid(row=0, column=col, sticky="ew", padx=6)
            ttk.Label(box, text=label, style="PanelMuted.TLabel", font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
            ttk.Label(box, textvariable=self.identity_vars[key], style="Value.TLabel").pack(anchor="w")
            device.columnconfigure(col, weight=1)

    def _build_control_tab(self, root):
        lights = ttk.Frame(root)
        lights.pack(fill="x", pady=(0, 8))
        lights.columnconfigure(0, weight=1)
        lights.columnconfigure(1, weight=1)
        for led in (1, 2):
            outer, box = self._card(lights, 10)
            outer.grid(row=0, column=led - 1, sticky="nsew", padx=(0, 4) if led == 1 else (4, 0))
            top = ttk.Frame(box, style="Panel.TFrame")
            top.pack(fill="x")
            ttk.Label(top, text=f"LIGHT {led}", style="Section.TLabel").pack(side="left")
            swatch = tk.Label(top, text="    ", bg="#%02x%02x%02x" % self.led_colors[led], padx=3, pady=3, bd=0)
            swatch.pack(side="right")
            self.led_swatches[led] = swatch
            row = ttk.Frame(box, style="Panel.TFrame")
            row.pack(fill="x", pady=(8, 0))
            ttk.Button(row, text="Choose color", style="Accent.TButton", command=lambda n=led: self._choose_color(n)).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="White", command=lambda n=led: self._set_led(n, 255, 255, 255)).pack(side="left", padx=(6, 0))
            ttk.Button(row, text="Off", style="Danger.TButton", command=lambda n=led: self._set_led(n, 0, 0, 0)).pack(side="left", padx=(6, 0))

        outer, settings = self._card(root, 10)
        outer.pack(fill="x", pady=(0, 8))
        ttk.Label(settings, text="SCENE CONTROL", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(settings, text="Brightness", style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(7, 0))
        self.brightness_label = ttk.Label(settings, text="75%", style="Value.TLabel", width=5)
        self.brightness_label.grid(row=1, column=2, sticky="e", pady=(7, 0))
        scale = ttk.Scale(settings, from_=0, to=100, orient="horizontal", command=self._brightness_changed)
        scale.grid(row=1, column=1, sticky="ew", padx=8, pady=(7, 0))
        scale.set(self.brightness_var.get())
        ttk.Label(settings, text="Pattern", style="PanelMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(7, 0))
        patterns = ttk.Combobox(settings, state="readonly", textvariable=self.pattern_var,
                                values=("OFF", "SOLID", "FADE", "RAINBOW", "PULSE", "RANDOM"))
        patterns.grid(row=2, column=1, sticky="ew", padx=8, pady=(7, 0))
        patterns.bind("<<ComboboxSelected>>", lambda _e: self.link.send(f"SET PATTERN {self.pattern_var.get()}"))
        ttk.Button(settings, text="Save to Jar", style="Accent.TButton", command=lambda: self.link.send("SAVE")).grid(row=2, column=2, sticky="e", pady=(7, 0))
        settings.columnconfigure(1, weight=1)

        outer, inputbox = self._card(root, 8)
        outer.pack(fill="x")
        ttk.Label(inputbox, text="6-BUTTON INPUT  •  D-PAD + A/B", style="Section.TLabel").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 5))
        for col, (name, key) in enumerate((("↑ UP", "up"), ("↓ DOWN", "down"), ("← LEFT", "left"), ("→ RIGHT", "right"), ("A", "a"), ("B / ESC", "b"))):
            tile = ttk.Frame(inputbox, style="Panel2.TFrame", padding=6)
            tile.grid(row=1, column=col, sticky="nsew", padx=3)
            ttk.Label(tile, text=name, background=PANEL_2, foreground=MUTED, font=("TkDefaultFont", 8, "bold")).pack()
            ttk.Label(tile, textvariable=self.touch_vars[key], style="TouchValue.TLabel").pack()
            inputbox.columnconfigure(col, weight=1)

    def _build_setup_tab(self, root):
        top = ttk.Frame(root)
        top.pack(fill="both", expand=True)
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        outer, wifi = self._card(top, 12)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 8))
        ttk.Label(wifi, text="WI-FI SETUP", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(wifi, text="Status", style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(wifi, textvariable=self.wifi_state, style="Value.TLabel").grid(row=1, column=1, sticky="w", pady=(10, 0))
        ttk.Label(wifi, text="Network / SSID", style="PanelMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(wifi, textvariable=self.wifi_ssid).grid(row=2, column=1, sticky="ew", pady=(8, 0))
        ttk.Label(wifi, text="Password", style="PanelMuted.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(wifi, textvariable=self.wifi_password, show="•").grid(row=3, column=1, sticky="ew", pady=(8, 0))
        buttons = ttk.Frame(wifi, style="Panel.TFrame")
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Send Wi-Fi", style="Accent.TButton", command=self._send_wifi).pack(side="left")
        ttk.Button(buttons, text="Connect / Test", command=lambda: self.link.send("WIFI CONNECT")).pack(side="left", padx=6)
        ttk.Button(buttons, text="Get Status", command=lambda: self.link.send("GET WIFI STATUS")).pack(side="left")
        ttk.Button(buttons, text="Clear Saved Wi-Fi", style="Danger.TButton", command=lambda: self.link.send("SET WIFI CLEAR")).pack(side="right")
        wifi.columnconfigure(1, weight=1)

        outer, clock = self._card(top, 12)
        outer.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 8))
        ttk.Label(clock, text="CLOCK + INTERNET TIME", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(clock, text="State", style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(clock, textvariable=self.time_state, style="Value.TLabel").grid(row=1, column=1, sticky="w", pady=(10, 0))
        ttk.Label(clock, text="Timezone", style="PanelMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(clock, textvariable=self.timezone_var).grid(row=2, column=1, sticky="ew", pady=(8, 0))
        row = ttk.Frame(clock, style="Panel.TFrame")
        row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(row, text="Set Timezone", style="Accent.TButton", command=lambda: self.link.send(f"SET TIMEZONE {self.timezone_var.get().strip()}")).pack(side="left")
        ttk.Button(row, text="Sync NTP", command=lambda: self.link.send("TIME SYNC")).pack(side="left", padx=6)
        ttk.Button(row, text="Get Time", command=lambda: self.link.send("GET TIME STATUS")).pack(side="left")
        clock.columnconfigure(1, weight=1)

        outer, schedule = self._card(top, 12)
        outer.grid(row=1, column=0, columnspan=2, sticky="ew")
        ttk.Label(schedule, text="ALARM + AUTO-OFF", style="Section.TLabel").grid(row=0, column=0, columnspan=6, sticky="w")
        ttk.Label(schedule, text="Alarm time", style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(schedule, textvariable=self.alarm_time, width=9).grid(row=1, column=1, sticky="w", pady=(10, 0))
        ttk.Checkbutton(schedule, text="Enabled", variable=self.alarm_enabled, command=self._send_alarm_enabled).grid(row=1, column=2, sticky="w", padx=10, pady=(10, 0))
        ttk.Button(schedule, text="Set Alarm", command=lambda: self.link.send(f"SET ALARM {self.alarm_time.get().strip()}")).grid(row=1, column=3, sticky="w", pady=(10, 0))
        ttk.Button(schedule, text="Get Alarm", command=lambda: self.link.send("GET ALARM")).grid(row=1, column=4, sticky="w", padx=6, pady=(10, 0))

        ttk.Label(schedule, text="Auto-off minutes", style="PanelMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(schedule, textvariable=self.timer_minutes, width=9).grid(row=2, column=1, sticky="w", pady=(10, 0))
        ttk.Checkbutton(schedule, text="Enabled", variable=self.timer_enabled, command=self._send_timer_enabled).grid(row=2, column=2, sticky="w", padx=10, pady=(10, 0))
        ttk.Button(schedule, text="Set Timer", command=self._send_timer).grid(row=2, column=3, sticky="w", pady=(10, 0))
        ttk.Button(schedule, text="Get Timer", command=lambda: self.link.send("GET TIMER")).grid(row=2, column=4, sticky="w", padx=6, pady=(10, 0))
        ttk.Button(schedule, text="SAVE ALL", style="Accent.TButton", command=lambda: self.link.send("SAVE")).grid(row=1, column=5, rowspan=2, sticky="e", padx=(18, 0))
        schedule.columnconfigure(5, weight=1)

    def _build_display_tab(self, root):
        outer, display = self._card(root, 12)
        outer.pack(fill="x", pady=(0, 8))
        ttk.Label(display, text="OLED + SCREENSAVER", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(display, text="Display brightness", style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        scale = ttk.Scale(display, from_=0, to=100, orient="horizontal", command=self._display_brightness_changed)
        scale.grid(row=1, column=1, sticky="ew", padx=8, pady=(10, 0))
        scale.set(self.display_brightness.get())
        self.display_brightness_label = ttk.Label(display, text="80%", style="Value.TLabel", width=5)
        self.display_brightness_label.grid(row=1, column=2, sticky="e", pady=(10, 0))
        ttk.Label(display, text="Screensaver", style="PanelMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ss = ttk.Combobox(display, state="readonly", textvariable=self.screensaver_var,
                          values=("OFF", "CLOCK", "PLASMA", "STARS", "BOUNCE"))
        ss.grid(row=2, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(display, text="Apply", command=lambda: self.link.send(f"SET SCREENSAVER {self.screensaver_var.get()}")).grid(row=2, column=2, sticky="e", pady=(8, 0))
        ttk.Label(display, text="Idle delay (min)", style="PanelMuted.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(display, textvariable=self.screensaver_delay, width=10).grid(row=3, column=1, sticky="w", padx=8, pady=(8, 0))
        ttk.Button(display, text="Set Delay", command=lambda: self.link.send(f"SET SCREENSAVER DELAY {self.screensaver_delay.get().strip()}")).grid(row=3, column=2, sticky="e", pady=(8, 0))
        display.columnconfigure(1, weight=1)

        outer, mapping = self._card(root, 12)
        outer.pack(fill="x")
        ttk.Label(mapping, text="CONTROL MAP", style="Section.TLabel").pack(anchor="w")
        ttk.Label(mapping, text="Physical layout: D-pad + A/B.  A = Select / Action.  B = Back / ESC.  Hold B = HOME.", style="PanelMuted.TLabel").pack(anchor="w", pady=(7, 10))
        row = ttk.Frame(mapping, style="Panel.TFrame")
        row.pack(fill="x")
        for label, command in (("JAR MODE", "SET INPUT MODE JAR"), ("MENU MODE", "SET INPUT MODE MENU"), ("GAME MODE", "SET INPUT MODE GAME"), ("TEST INPUT", "TEST INPUT"), ("GET INPUT", "GET INPUT")):
            ttk.Button(row, text=label, command=lambda c=command: self.link.send(c)).pack(side="left", padx=(0, 6))

    def _build_service_tab(self, root):
        top = ttk.Frame(root)
        top.pack(fill="both", expand=True)
        top.columnconfigure(1, weight=1)
        top.rowconfigure(0, weight=1)

        outer, diag = self._card(top, 8)
        outer.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        ttk.Label(diag, text="DIAGNOSTICS", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        for text, command in (("RGB test", "TEST RGB"), ("Touch test", "TEST TOUCH"), ("Input test", "TEST INPUT"),
                              ("Get status", "GET STATUS"), ("Get Wi-Fi", "GET WIFI STATUS"), ("Get time", "GET TIME STATUS"),
                              ("Get display", "GET DISPLAY"), ("Ping", "PING")):
            ttk.Button(diag, text=text, command=lambda c=command: self.link.send(c)).pack(fill="x", pady=2)
        ttk.Button(diag, text="Save to Jar", style="Accent.TButton", command=lambda: self.link.send("SAVE")).pack(fill="x", pady=(8, 2))

        outer, logs = self._card(top, 6)
        outer.grid(row=0, column=1, sticky="nsew")
        ttk.Label(logs, text="SESSION LOG  •  passwords redacted", style="Section.TLabel").pack(anchor="w", padx=4, pady=(1, 4))
        body = ttk.Frame(logs, style="Panel.TFrame")
        body.pack(fill="both", expand=True)
        self.log_text = tk.Text(body, height=12, wrap="word", state="disabled", bg="#080d18", fg="#b9c7df",
                                insertbackground=TEXT, selectbackground="#3b4d70", relief="flat", bd=0,
                                padx=8, pady=6, font=("TkFixedFont", 9))
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _choose_color(self, led: int):
        initial = "#%02x%02x%02x" % self.led_colors[led]
        _rgb, hex_color = colorchooser.askcolor(color=initial, title=f"Light {led} color")
        if not hex_color:
            return
        rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
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

    def _display_brightness_changed(self, value):
        n = max(0, min(100, int(float(value))))
        self.display_brightness.set(n)
        self.display_brightness_label.configure(text=f"{n}%")

    def _send_wifi(self):
        ssid = self.wifi_ssid.get().strip()
        password = self.wifi_password.get()
        if ssid:
            self.link.send(f"SET WIFI SSID {ssid}")
        if password:
            self.link.send(f"SET WIFI PASSWORD {password}")
        self.link.send("WIFI CONNECT")

    def _send_alarm_enabled(self):
        self.link.send("SET ALARM ON" if self.alarm_enabled.get() else "SET ALARM OFF")

    def _send_timer_enabled(self):
        if self.timer_enabled.get():
            self._send_timer()
        else:
            self.link.send("SET TIMER OFF")

    def _send_timer(self):
        minutes = self.timer_minutes.get().strip()
        if minutes:
            self.link.send(f"SET TIMER MINUTES {minutes}")

    @staticmethod
    def _parse_fields(line: str):
        fields = {}
        for part in line.split("|")[2:]:
            if "=" in part:
                key, value = part.split("=", 1)
                fields[key.strip()] = value.strip()
        return fields

    def _handle_line(self, line: str):
        if line.startswith("HJ|TOUCH|") or line.startswith("HJ|INPUT|"):
            fields = self._parse_fields(line)
            aliases = {"c1": "a", "c2": "b", "up": "up", "down": "down", "left": "left", "right": "right", "a": "a", "b": "b"}
            for source, dest in aliases.items():
                if source in fields and dest in self.touch_vars:
                    self.touch_vars[dest].set(fields[source])
            return

        self._log(f"RX  {line}")
        fields = self._parse_fields(line)
        if line.startswith("HJ|IDENTITY|"):
            for key in ("serial", "hw", "fw"):
                if key in fields:
                    self.identity_vars[key].set(fields[key])
        elif line.startswith("HJ|STATUS|"):
            if "brightness" in fields:
                try:
                    n = int(fields["brightness"])
                    self.brightness_var.set(n)
                    self.brightness_label.configure(text=f"{n}%")
                except ValueError:
                    pass
            if "pattern" in fields:
                self.pattern_var.set(fields["pattern"])
        elif line.startswith("HJ|WIFI|"):
            self.wifi_state.set(fields.get("state", "UNKNOWN"))
            if fields.get("ssid"):
                self.wifi_ssid.set(fields["ssid"])
        elif line.startswith("HJ|TIME|"):
            synced = fields.get("synced", "0")
            self.time_state.set("SYNCED" if synced in ("1", "true", "TRUE") else "NOT SYNCED")
            if fields.get("timezone"):
                self.timezone_var.set(fields["timezone"])
        elif line.startswith("HJ|ALARM|"):
            if fields.get("time"):
                self.alarm_time.set(fields["time"])
            if "enabled" in fields:
                self.alarm_enabled.set(fields["enabled"] in ("1", "true", "TRUE", "ON"))
        elif line.startswith("HJ|TIMER|"):
            if fields.get("minutes"):
                self.timer_minutes.set(fields["minutes"])
            if "enabled" in fields:
                self.timer_enabled.set(fields["enabled"] in ("1", "true", "TRUE", "ON"))
        elif line.startswith("HJ|DISPLAY|"):
            if fields.get("screensaver"):
                self.screensaver_var.set(fields["screensaver"])

    def _drain_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "connected":
                    self.connection_var.set(f"CONNECTED  •  {payload['port']}")
                    self.status_pill.configure(bg=GOOD_BG, fg=GOOD_FG)
                    self._log(f"Connected on {payload['port']}")
                    self._handle_line(payload["identity"])
                elif kind == "disconnected":
                    self.connection_var.set("WAITING FOR JAR")
                    self.status_pill.configure(bg=WAIT_BG, fg=WAIT_FG)
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
