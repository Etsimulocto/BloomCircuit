#!/usr/bin/env python3
"""HAPPY JARZ Controller v0.3.0 — BloomCore setup, control, and service UI.

Known-good v0.2 light/touch commands are preserved. New Wi-Fi/time/alarm/timer/
display controls are forward-compatible with the planned firmware protocol in
APP_PROTOCOL_V0_3.md. Unsupported commands may return HJ|ERR on older firmware.
"""

from __future__ import annotations

import array
import base64
import glob
import os
import struct
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import colorchooser, ttk

try:
    import fcntl
except ImportError:  # Windows host: Linux joystick ioctl path unavailable.
    fcntl = None

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
                    self.send("GET CAPS")
                    self.send("STREAM OLED ON")
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
        self.geometry("1080x900")
        self.minsize(900, 760)
        self.configure(bg=BG)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.events: queue.Queue = queue.Queue()
        self.link = JarSerial(self.events)

        self.identity_vars = {k: tk.StringVar(value="—") for k in ("serial", "hw", "fw")}
        self.connection_var = tk.StringVar(value="WAITING FOR JAR")
        self.input_names = ("up", "down", "left", "right", "a", "b", "x", "y", "l", "r", "start", "select")
        self.simple_inputs = {"up", "down", "left", "right", "a", "b"}
        self.touch_vars = {k: tk.StringVar(value="—") for k in self.input_names}
        self.input_tiles = {}
        self.input_name_labels = {}
        self.input_value_labels = {}
        self.device_capabilities = set(self.simple_inputs)
        self.mini_buttons = {}
        self.oled_image = None
        self.oled_scaled_image = None
        self.oled_mirror_label = None
        self.oled_mirror_labels = []
        self.oled_mirror_status = tk.StringVar(value="WAITING FOR OLED")
        self.gamepad_status = tk.StringVar(value="GAMEPAD: SEARCHING")
        self.oled_last_seq = 0
        self.gamepad_running = True

        self.brightness_var = tk.IntVar(value=75)
        self.pattern_var = tk.StringVar(value="SOLID")
        self.led_colors = {
            1: (255, 80, 120),
            2: (80, 120, 255),
            3: (255, 80, 120),
            4: (80, 120, 255),
        }
        self.live_led_colors = {1: None, 2: None, 3: None, 4: None}
        self.led_swatches = {}
        self.led_base_swatches = {}
        self._brightness_after = None

        # App chrome follows the four saved/base lamp colors only.
        # Live pattern frames never feed this theme, so animations cannot flash
        # or recolor the desktop UI.
        self._theme_roles = {
            "bg": BG,
            "panel": PANEL,
            "border": BORDER,
            "text": TEXT,
        }

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
        threading.Thread(target=self._gamepad_worker, daemon=True).start()
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
        for led in (1, 2, 3, 4):
            grid_row = (led - 1) // 2
            grid_col = (led - 1) % 2
            outer, box = self._card(lights, 10)
            outer.grid(
                row=grid_row,
                column=grid_col,
                sticky="nsew",
                padx=(0, 4) if grid_col == 0 else (4, 0),
                pady=(0, 4) if grid_row == 0 else (4, 0),
            )
            top = ttk.Frame(box, style="Panel.TFrame")
            top.pack(fill="x")
            ttk.Label(top, text=f"LIGHT {led}", style="Section.TLabel").pack(side="left")

            live_group = ttk.Frame(top, style="Panel.TFrame")
            live_group.pack(side="right")

            ttk.Label(live_group, text="BASE", style="PanelMuted.TLabel",
                      font=("TkDefaultFont", 7, "bold")).pack(side="left", padx=(0, 3))
            base_swatch = tk.Label(
                live_group, text="   ",
                bg="#%02x%02x%02x" % self.led_colors[led],
                padx=3, pady=3, bd=0,
            )
            base_swatch.pack(side="left", padx=(0, 8))
            self.led_base_swatches[led] = base_swatch

            ttk.Label(live_group, text="LIVE", style="PanelMuted.TLabel",
                      font=("TkDefaultFont", 7, "bold")).pack(side="left", padx=(0, 3))
            swatch = tk.Label(
                live_group, text="   ", bg="#111827",
                padx=3, pady=3, bd=0,
            )
            swatch.pack(side="left")
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
        head = ttk.Frame(inputbox, style="Panel.TFrame")
        head.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 5))
        ttk.Label(head, text="GAMEPAD INPUT  •  LIVE TOUCH / USB STATE", style="Section.TLabel").pack(side="left")
        ttk.Label(head, text="FULL controls stay visible on SIMPLE", style="PanelMuted.TLabel").pack(side="right")

        controls = (
            ("↑ UP", "up"), ("↓ DOWN", "down"), ("← LEFT", "left"), ("→ RIGHT", "right"),
            ("A", "a"), ("B / ESC", "b"),
            ("X", "x"), ("Y", "y"), ("L", "l"), ("R", "r"),
            ("START", "start"), ("SELECT", "select"),
        )
        for index, (name, key) in enumerate(controls):
            grid_row = 1 + index // 6
            grid_col = index % 6
            tile = ttk.Frame(inputbox, style="Panel2.TFrame", padding=5)
            tile.grid(row=grid_row, column=grid_col, sticky="nsew", padx=3, pady=2)
            name_label = tk.Label(
                tile, text=name, bg=PANEL_2, fg=MUTED,
                font=("TkDefaultFont", 8, "bold"), bd=0,
            )
            name_label.pack()
            value_label = tk.Label(
                tile, textvariable=self.touch_vars[key], bg=PANEL_2, fg=TEXT,
                font=("TkFixedFont", 11, "bold"), bd=0,
            )
            value_label.pack()
            self.input_tiles[key] = tile
            self.input_name_labels[key] = name_label
            self.input_value_labels[key] = value_label
            inputbox.columnconfigure(grid_col, weight=1)

        self._apply_input_capabilities(self.device_capabilities)
        self._build_mini_console(root)

    def _build_mini_console(self, root):
        outer, mini = self._card(root, 8)
        outer.pack(fill="both", expand=True, pady=(8, 0))

        header = ttk.Frame(mini, style="Panel.TFrame")
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text="HAPPY JARZ MINI  •  LIVE OLED + APP GAMEPAD",
                  style="Section.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.oled_mirror_status,
                  style="PanelMuted.TLabel").pack(side="right")
        ttk.Label(header, textvariable=self.gamepad_status,
                  style="PanelMuted.TLabel").pack(side="right", padx=(0, 14))

        body = ttk.Frame(mini, style="Panel.TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        # Actual 128x64 device framebuffer, displayed at 2x.
        screen_box = tk.Frame(body, bg="#05080d", bd=1, relief="sunken")
        screen_box.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        self.oled_image = tk.PhotoImage(width=128, height=64)
        self.oled_image.put("#000000", to=(0, 0, 128, 64))
        self.oled_scaled_image = self.oled_image.zoom(2, 2)
        self.oled_mirror_label = tk.Label(
            screen_box, image=self.oled_scaled_image,
            bg="#000000", bd=0, padx=0, pady=0,
        )
        self.oled_mirror_label.pack(padx=6, pady=6)
        self.oled_mirror_labels.append(self.oled_mirror_label)

        controls = ttk.Frame(body, style="Panel.TFrame")
        controls.grid(row=0, column=1, sticky="nsew")
        for col in range(6):
            controls.columnconfigure(col, weight=1)

        button_defs = (
            ("↑ UP", "up"), ("↓ DOWN", "down"), ("← LEFT", "left"),
            ("→ RIGHT", "right"), ("A", "a"), ("B", "b"),
            ("X", "x"), ("Y", "y"), ("L", "l"),
            ("R", "r"), ("START", "start"), ("SELECT", "select"),
        )
        for index, (label, key) in enumerate(button_defs):
            row = index // 6
            col = index % 6
            btn = tk.Button(
                controls,
                text=label,
                command=lambda k=key: self._mini_key(k),
                bg=PANEL_2,
                fg=TEXT,
                activebackground="#24324d",
                activeforeground="#ffffff",
                disabledforeground="#4b5563",
                relief="raised",
                bd=1,
                font=("TkDefaultFont", 9, "bold"),
                padx=6,
                pady=7,
                takefocus=False,
            )
            btn.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
            self.mini_buttons[key] = btn

        ttk.Label(
            controls,
            text="Buttons send into the Jar's normal input path. FULL-only controls stay disabled until advertised by the device.",
            style="PanelMuted.TLabel",
            wraplength=620,
        ).grid(row=2, column=0, columnspan=6, sticky="w", padx=3, pady=(5, 0))

        self._apply_input_capabilities(self.device_capabilities)

    def _queue_host_key(self, key: str):
        key = key.strip().lower()
        if key in self.input_names:
            self.events.put(("host_key", key))

    @staticmethod
    def _event_gamepad_candidates():
        out = []
        for dev in sorted(glob.glob("/dev/input/event*")):
            base = os.path.basename(dev)
            name_path = f"/sys/class/input/{base}/device/name"
            try:
                name = open(name_path, "r", encoding="utf-8", errors="replace").read().strip()
            except OSError:
                name = ""
            low = name.lower()
            words = (
                "gamepad", "controller", "joystick", "xbox", "8bitdo",
                "dualshock", "dualsense", "gamesir", "pro controller", "usb game",
            )
            if any(word in low for word in words):
                out.append((dev, name or base))
        return out

    def _read_event_gamepad(self, dev: str, name: str) -> bool:
        """Read one Linux event gamepad. Return False when unavailable."""
        EV_KEY = 0x01
        EV_ABS = 0x03

        BTN_SOUTH = 304
        BTN_EAST = 305
        BTN_NORTH = 307
        BTN_WEST = 308
        BTN_TL = 310
        BTN_TR = 311
        BTN_SELECT = 314
        BTN_START = 315

        BTN_DPAD_UP = 544
        BTN_DPAD_DOWN = 545
        BTN_DPAD_LEFT = 546
        BTN_DPAD_RIGHT = 547

        ABS_X = 0
        ABS_Y = 1
        ABS_HAT0X = 16
        ABS_HAT0Y = 17

        button_map = {
            BTN_SOUTH: "a",
            BTN_EAST: "b",
            BTN_WEST: "x",
            BTN_NORTH: "y",
            BTN_TL: "l",
            BTN_TR: "r",
            BTN_START: "start",
            BTN_SELECT: "select",
            BTN_DPAD_UP: "up",
            BTN_DPAD_DOWN: "down",
            BTN_DPAD_LEFT: "left",
            BTN_DPAD_RIGHT: "right",
        }

        event_size = struct.calcsize("llHHi")
        axis_state = {}
        fd = None
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            self.events.put(("gamepad_status", f"GAMEPAD: {name}"))
            while self.gamepad_running and os.path.exists(dev):
                try:
                    packet = os.read(fd, event_size)
                except BlockingIOError:
                    time.sleep(0.01)
                    continue
                except OSError:
                    break
                if len(packet) != event_size:
                    time.sleep(0.01)
                    continue

                _sec, _usec, etype, code, value = struct.unpack("llHHi", packet)

                if etype == EV_KEY and value == 1:
                    key = button_map.get(code)
                    if key:
                        self._queue_host_key(key)
                elif etype == EV_ABS and code in (ABS_X, ABS_Y, ABS_HAT0X, ABS_HAT0Y):
                    if code in (ABS_HAT0X, ABS_HAT0Y):
                        pos = -1 if value < 0 else (1 if value > 0 else 0)
                    else:
                        pos = -1 if value < -12000 else (1 if value > 12000 else 0)

                    old = axis_state.get(code, 0)
                    axis_state[code] = pos
                    if pos == 0 or pos == old:
                        continue

                    if code in (ABS_X, ABS_HAT0X):
                        self._queue_host_key("left" if pos < 0 else "right")
                    else:
                        self._queue_host_key("up" if pos < 0 else "down")
            return True
        except PermissionError:
            self.events.put(("gamepad_log", f"No permission for {dev}; trying joystick fallback"))
            return False
        except OSError as exc:
            self.events.put(("gamepad_log", f"Gamepad event read failed on {dev}: {exc}"))
            return False
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _read_js_gamepad(self, dev: str) -> bool:
        """Semantic Linux joystick fallback based on the proven BloomPetz path."""
        if fcntl is None:
            return False

        ABS_X = 0x00
        ABS_Y = 0x01
        ABS_HAT0X = 0x10
        ABS_HAT0Y = 0x11

        BTN_SOUTH = 0x130
        BTN_EAST = 0x131
        BTN_NORTH = 0x133
        BTN_WEST = 0x134
        BTN_TL = 0x136
        BTN_TR = 0x137
        BTN_SELECT = 0x13a
        BTN_START = 0x13b

        button_map = {
            BTN_SOUTH: "a",
            BTN_EAST: "b",
            BTN_WEST: "x",
            BTN_NORTH: "y",
            BTN_TL: "l",
            BTN_TR: "r",
            BTN_START: "start",
            BTN_SELECT: "select",
        }

        IOC_NRBITS = 8
        IOC_TYPEBITS = 8
        IOC_SIZEBITS = 14
        IOC_NRSHIFT = 0
        IOC_TYPESHIFT = IOC_NRSHIFT + IOC_NRBITS
        IOC_SIZESHIFT = IOC_TYPESHIFT + IOC_TYPEBITS
        IOC_DIRSHIFT = IOC_SIZESHIFT + IOC_SIZEBITS
        IOC_READ = 2

        def _ior(type_chr, nr, size):
            return ((IOC_READ << IOC_DIRSHIFT) |
                    (ord(type_chr) << IOC_TYPESHIFT) |
                    (nr << IOC_NRSHIFT) |
                    (size << IOC_SIZESHIFT))

        JSIOCGAXMAP = _ior("j", 0x32, 0x40)
        JSIOCGBTNMAP = _ior("j", 0x34, 0x400)

        fd = None
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            axmap = array.array("B", [0] * 0x40)
            btnmap = array.array("H", [0] * 0x200)
            fcntl.ioctl(fd, JSIOCGAXMAP, axmap, True)
            fcntl.ioctl(fd, JSIOCGBTNMAP, btnmap, True)

            name = os.path.basename(dev)
            self.events.put(("gamepad_status", f"GAMEPAD: {name}"))
            axis_state = {}

            while self.gamepad_running and os.path.exists(dev):
                try:
                    packet = os.read(fd, 8)
                except BlockingIOError:
                    time.sleep(0.01)
                    continue
                except OSError:
                    break
                if len(packet) != 8:
                    time.sleep(0.01)
                    continue

                _ms, value, etype, number = struct.unpack("IhBB", packet)
                etype &= ~0x80  # JS_EVENT_INIT

                if etype == 0x01 and value:
                    code = btnmap[number] if number < len(btnmap) else None
                    key = button_map.get(code)
                    if key:
                        self._queue_host_key(key)

                elif etype == 0x02:
                    code = axmap[number] if number < len(axmap) else None
                    if code not in (ABS_X, ABS_Y, ABS_HAT0X, ABS_HAT0Y):
                        continue
                    pos = -1 if value < -16000 else (1 if value > 16000 else 0)
                    old = axis_state.get(code, 0)
                    axis_state[code] = pos
                    if pos == 0 or pos == old:
                        continue
                    if code in (ABS_X, ABS_HAT0X):
                        self._queue_host_key("left" if pos < 0 else "right")
                    else:
                        self._queue_host_key("up" if pos < 0 else "down")
            return True
        except (OSError, PermissionError) as exc:
            self.events.put(("gamepad_log", f"Joystick fallback failed on {dev}: {exc}"))
            return False
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _gamepad_worker(self):
        """Prefer event* semantic mapping; fall back to js* semantic mapping."""
        while self.gamepad_running:
            handled = False

            candidates = self._event_gamepad_candidates()
            if candidates:
                dev, name = candidates[0]
                handled = self._read_event_gamepad(dev, name)

            if not handled:
                js_devices = sorted(glob.glob("/dev/input/js*"))
                if js_devices:
                    handled = self._read_js_gamepad(js_devices[0])

            if not handled:
                self.events.put(("gamepad_status", "GAMEPAD: SEARCHING"))
                time.sleep(0.75)
            else:
                # Device was disconnected or reader ended; rescan cleanly.
                self.events.put(("gamepad_status", "GAMEPAD: SEARCHING"))
                time.sleep(0.35)

    def _mini_key(self, key: str):
        key = key.strip().lower()
        if key not in self.device_capabilities:
            return
        if self.link.send(f"KEY {key.upper()}"):
            self._pulse_mini_button(key)

    def _pulse_mini_button(self, key: str):
        btn = self.mini_buttons.get(key)
        if btn is None or str(btn.cget("state")) == "disabled":
            return
        try:
            btn.configure(relief="sunken", bg=ACCENT)
            self.after(120, lambda b=btn: b.configure(relief="raised", bg=PANEL_2))
        except tk.TclError:
            pass

    def _render_oled_frame(self, seq: int, encoded: str):
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception:
            self.oled_mirror_status.set("OLED FRAME ERROR")
            return
        if len(raw) != 1024:
            self.oled_mirror_status.set(f"OLED BAD SIZE {len(raw)}")
            return
        if seq and seq <= self.oled_last_seq:
            return
        self.oled_last_seq = seq

        # U8g2 SSD1306 full-buffer layout: 8 vertical pixels per byte,
        # 128 bytes per page. This mirrors the actual device framebuffer.
        on = "#3b82f6"
        off = "#000000"
        rows = []
        for y in range(64):
            page = (y >> 3) * 128
            bit = 1 << (y & 7)
            row = [on if (raw[page + x] & bit) else off for x in range(128)]
            rows.append("{" + " ".join(row) + "}")
        try:
            self.oled_image.put(" ".join(rows))
            self.oled_scaled_image = self.oled_image.zoom(2, 2)
            for label in tuple(self.oled_mirror_labels):
                try:
                    label.configure(image=self.oled_scaled_image)
                except tk.TclError:
                    pass
            self.oled_mirror_status.set(f"LIVE  •  FRAME {seq}")
        except tk.TclError:
            self.oled_mirror_status.set("OLED DRAW ERROR")

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

    @staticmethod
    def _rgb_hex(rgb):
        r, g, b = (max(0, min(255, int(v))) for v in rgb)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _blend_hex(a: str, b: str, amount: float):
        amount = max(0.0, min(1.0, float(amount)))
        av = tuple(int(a[i:i + 2], 16) for i in (1, 3, 5))
        bv = tuple(int(b[i:i + 2], 16) for i in (1, 3, 5))
        out = tuple(round(x + (y - x) * amount) for x, y in zip(av, bv))
        return HappyJarzApp._rgb_hex(out)

    def _apply_theme_from_base_colors(self):
        # BASE lamp colors are the stable product palette:
        # L1=background, L2=panel, L3=outline, L4=text.
        new_roles = {
            "bg": self._rgb_hex(self.led_colors[1]),
            "panel": self._rgb_hex(self.led_colors[2]),
            "border": self._rgb_hex(self.led_colors[3]),
            "text": self._rgb_hex(self.led_colors[4]),
        }
        old_roles = dict(self._theme_roles)
        self._theme_roles = new_roles

        bg = new_roles["bg"]
        panel = new_roles["panel"]
        border = new_roles["border"]
        text = new_roles["text"]

        # Secondary UI colors are derived from the four physical lamp colors;
        # they are not additional independent theme inputs.
        panel2 = self._blend_hex(panel, border, 0.24)
        muted = self._blend_hex(text, panel, 0.46)
        hover = self._blend_hex(panel2, text, 0.14)
        accent = border
        accent2 = self._blend_hex(border, text, 0.42)

        style = ttk.Style(self)
        style.configure(".", background=bg, foreground=text, fieldbackground=panel2,
                        bordercolor=border, lightcolor=border, darkcolor=border)
        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("Panel2.TFrame", background=panel2)
        style.configure("TLabel", background=bg, foreground=text)
        style.configure("Panel.TLabel", background=panel, foreground=text)
        style.configure("Muted.TLabel", background=bg, foreground=muted)
        style.configure("PanelMuted.TLabel", background=panel, foreground=muted)
        style.configure("Title.TLabel", background=bg, foreground=text)
        style.configure("Section.TLabel", background=panel, foreground=text)
        style.configure("Value.TLabel", background=panel, foreground=accent2)
        style.configure("TouchValue.TLabel", background=panel2, foreground=text)
        style.configure("TButton", background=panel2, foreground=text)
        style.map("TButton", background=[("active", hover)], foreground=[("active", text)])
        style.configure("Accent.TButton", background=accent, foreground=text)
        style.map("Accent.TButton", background=[("active", accent2)], foreground=[("active", text)])
        style.configure("TScale", background=panel, troughcolor=panel2)
        style.configure("TCombobox", fieldbackground=panel2, background=panel2,
                        foreground=text, arrowcolor=text, bordercolor=border)
        style.map("TCombobox", fieldbackground=[("readonly", panel2)],
                  foreground=[("readonly", text)])
        style.configure("TEntry", fieldbackground=panel2, foreground=text, bordercolor=border)
        style.configure("TCheckbutton", background=panel, foreground=text)
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=panel2, foreground=muted)
        style.map("TNotebook.Tab", background=[("selected", border)],
                  foreground=[("selected", text)])
        style.configure("Vertical.TScrollbar", background=panel2, troughcolor=panel,
                        bordercolor=panel, arrowcolor=muted)

        # ttk handles most of the app. Recolor the handful of classic Tk widgets
        # that use literal bg/fg values (card borders, touch tiles, Mini buttons,
        # text editors). Leave the black OLED framebuffer surfaces untouched.
        previous = {
            BG: ("bg", bg), PANEL: ("panel", panel), PANEL_2: ("panel2", panel2),
            BORDER: ("border", border), TEXT: ("text", text), MUTED: ("muted", muted),
        }
        for role, old in old_roles.items():
            replacement = new_roles.get(role, old)
            previous[old] = (role, replacement)

        def recolor(widget):
            try:
                current_bg = widget.cget("bg")
                if current_bg in previous:
                    role = previous[current_bg][0]
                    repl = {
                        "bg": bg, "panel": panel, "border": border, "text": text,
                        "panel2": panel2, "muted": muted,
                    }.get(role)
                    if repl:
                        widget.configure(bg=repl)
            except (tk.TclError, AttributeError):
                pass
            try:
                current_fg = widget.cget("fg")
                if current_fg in previous:
                    role = previous[current_fg][0]
                    repl = {
                        "bg": bg, "panel": panel, "border": border, "text": text,
                        "panel2": panel2, "muted": muted,
                    }.get(role)
                    if repl:
                        widget.configure(fg=repl)
            except (tk.TclError, AttributeError):
                pass
            for child in widget.winfo_children():
                # OLED pixels/bezel intentionally stay black + blue.
                if child in self.oled_mirror_labels:
                    continue
                recolor(child)

        self.configure(bg=bg)
        recolor(self)

        # Text editors/logs use classic Tk colors rather than ttk styles.
        def retheme_text_boxes(widget):
            if isinstance(widget, tk.Text):
                try:
                    widget.configure(
                        bg=panel2,
                        fg=text,
                        insertbackground=text,
                        selectbackground=border,
                    )
                except tk.TclError:
                    pass
            for child in widget.winfo_children():
                retheme_text_boxes(child)

        retheme_text_boxes(self)

        # Preserve literal lamp swatches after walking the widget tree. These
        # must always show the actual BASE/LIVE lamp colors, not theme roles.
        for led, rgb in self.led_colors.items():
            if led in self.led_base_swatches:
                self.led_base_swatches[led].configure(bg=self._rgb_hex(rgb))
        for led, rgb in self.live_led_colors.items():
            if rgb is not None and led in self.led_swatches:
                self.led_swatches[led].configure(bg=self._rgb_hex(rgb))

        # These are classic Tk controls whose intended role is known even after
        # several theme changes.
        for key, label in self.input_name_labels.items():
            if key in self.device_capabilities:
                label.configure(bg=panel2, fg=muted)
        for key, label in self.input_value_labels.items():
            if key in self.device_capabilities:
                label.configure(bg=panel2, fg=text)
        for key, btn in self.mini_buttons.items():
            btn.configure(
                bg=panel2,
                fg=text,
                activebackground=hover,
                activeforeground=text,
            )

    def _choose_color(self, led: int):
        initial = "#%02x%02x%02x" % self.led_colors[led]
        _rgb, hex_color = colorchooser.askcolor(color=initial, title=f"Light {led} color")
        if not hex_color:
            return
        rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        self._set_led(led, *rgb)

    def _set_led(self, led: int, r: int, g: int, b: int):
        self.led_colors[led] = (r, g, b)
        if led in self.led_base_swatches:
            self.led_base_swatches[led].configure(bg=f"#{r:02x}{g:02x}{b:02x}")
        self._apply_theme_from_base_colors()
        self.link.send(f"SET LED{led} COLOR {r} {g} {b}")

    def _set_live_led(self, led: int, rgb):
        if led not in self.live_led_colors:
            return
        try:
            r, g, b = (int(value) for value in rgb)
        except (TypeError, ValueError):
            return
        if not all(0 <= value <= 255 for value in (r, g, b)):
            return
        self.live_led_colors[led] = (r, g, b)
        if led in self.led_swatches:
            self.led_swatches[led].configure(bg=f"#{r:02x}{g:02x}{b:02x}")

    def _apply_input_capabilities(self, capabilities):
        caps = {str(name).strip().lower() for name in capabilities}
        self.device_capabilities = caps
        for key in self.input_names:
            enabled = key in caps
            if key in self.input_name_labels:
                self.input_name_labels[key].configure(
                    fg=MUTED if enabled else "#4b5563"
                )
            if key in self.input_value_labels:
                self.input_value_labels[key].configure(
                    fg=TEXT if enabled else "#4b5563"
                )
            if key in self.mini_buttons:
                self.mini_buttons[key].configure(state="normal" if enabled else "disabled")
            if not enabled:
                self.touch_vars[key].set("N/A")
            elif self.touch_vars[key].get() == "N/A":
                self.touch_vars[key].set("—")

    def _apply_identity_capabilities(self, fields):
        hw = fields.get("hw", "").upper()
        if "FULL" in hw:
            self._apply_input_capabilities(self.input_names)
        elif hw:
            self._apply_input_capabilities(self.simple_inputs)

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
        # OLED frames are intentionally not copied into the visible/session log:
        # each payload is ~1.4 KB Base64 and can arrive several times per second.
        if line.startswith("HJ|OLED|"):
            fields = self._parse_fields(line)
            if fields.get("codec") == "b64v1" and fields.get("data"):
                try:
                    seq = int(fields.get("seq", "0"))
                except ValueError:
                    seq = 0
                self._render_oled_frame(seq, fields["data"])
            return

        if line.startswith("HJ|TOUCH|") or line.startswith("HJ|INPUT|"):
            fields = self._parse_fields(line)
            aliases = {
                "c1": "a", "c2": "b",
                "up": "up", "down": "down", "left": "left", "right": "right",
                "a": "a", "b": "b", "x": "x", "y": "y", "l": "l", "r": "r",
                "start": "start", "select": "select",
            }
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
            self._apply_identity_capabilities(fields)
        elif line.startswith("HJ|CAPS|"):
            raw = fields.get("controls", "")
            if raw:
                caps = {part.strip().lower() for part in raw.split(",") if part.strip()}
                self._apply_input_capabilities(caps)
        elif line.startswith("HJ|EVENT|") and fields.get("input"):
            key = fields["input"].strip().lower()
            if key in self.mini_buttons:
                self._pulse_mini_button(key)
        elif line.startswith("HJ|LED_FRAME|"):
            for led in (1, 2, 3, 4):
                raw = fields.get(f"led{led}") or fields.get(f"live_led{led}")
                if not raw:
                    continue
                try:
                    rgb = tuple(int(part) for part in raw.split(",", 2))
                except ValueError:
                    continue
                self._set_live_led(led, rgb)
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
            for led in (1, 2, 3, 4):
                key = f"led{led}"
                if key not in fields:
                    continue
                try:
                    r, g, b = (int(part) for part in fields[key].split(",", 2))
                except (ValueError, TypeError):
                    continue
                if all(0 <= value <= 255 for value in (r, g, b)):
                    self.led_colors[led] = (r, g, b)
                    if led in self.led_base_swatches:
                        self.led_base_swatches[led].configure(bg=f"#{r:02x}{g:02x}{b:02x}")
                    if self.pattern_var.get() == "SOLID":
                        self._set_live_led(led, (r, g, b))
            self._apply_theme_from_base_colors()
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
                    for key, var in self.touch_vars.items():
                        var.set("—" if key in self.device_capabilities else "N/A")
                    for led in self.live_led_colors:
                        self.live_led_colors[led] = None
                        if led in self.led_swatches:
                            self.led_swatches[led].configure(bg="#111827")
                    self.oled_last_seq = 0
                    self.oled_mirror_status.set("WAITING FOR OLED")
                    if self.oled_image is not None:
                        try:
                            self.oled_image.put("#000000", to=(0, 0, 128, 64))
                            self.oled_scaled_image = self.oled_image.zoom(2, 2)
                            for label in tuple(self.oled_mirror_labels):
                                try:
                                    label.configure(image=self.oled_scaled_image)
                                except tk.TclError:
                                    pass
                        except tk.TclError:
                            pass
                elif kind == "line":
                    self._handle_line(payload)
                elif kind == "host_key":
                    self._mini_key(payload)
                elif kind == "gamepad_status":
                    self.gamepad_status.set(payload)
                elif kind == "gamepad_log":
                    self._log(payload)
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
        self.gamepad_running = False
        self.link.close()
        self.destroy()


if __name__ == "__main__":
    HappyJarzApp().mainloop()
