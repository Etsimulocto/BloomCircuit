#!/usr/bin/env python3
"""BloomPetz Mini — tiny OLED mirror + keyboard controller.

UI contract:
- mirrors the device's 4 x 16-character OLED screen
- keyboard arrows map to UP/DOWN/LEFT/RIGHT
- keyboard A/B map to the two BloomPetz action keys
- no hold/repeat behavior: one firmware key event per physical key press
- only visible app controls are previous/next screen color and Close

Serial behavior intentionally follows the proven HAPPY JARZ desktop path:
- identify the controller by BP protocol, never by a hard-coded ttyACM number
- open USB CDC with DTR/RTS false so connecting does not intentionally reset it
- wait for a USB port to be stable before probing
- do not grab serial while arduino-cli/esptool is running
- tolerate unplug/replug and reconnect while the window stays open
"""

from __future__ import annotations

import colorsys
import datetime as dt
import glob
import json
import os
import queue
import subprocess
import threading
import time
import tkinter as tk

try:
    import serial
except ImportError as exc:
    raise SystemExit("pyserial is required: sudo apt install -y python3-serial") from exc

BAUD = 115200
POLL_SECONDS = 0.25
STABLE_SECONDS = 2.0
HANDSHAKE_TIMEOUT = 1.0
RETRY_SECONDS = 1.0
CONFIG_PATH = os.path.expanduser("~/.config/bloompetz/mini.json")

SCREEN_W = 384
SCREEN_H = 192
HEADER_H = 30
FONT = ("DejaVu Sans Mono", 20, "bold")


def programmer_running() -> bool:
    try:
        p = subprocess.run(
            ["pgrep", "-f", "arduino-cli|esptool"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return p.returncode == 0
    except Exception:
        return False


def serial_ports() -> list[str]:
    return sorted(glob.glob("/dev/ttyACM*"))


def make_palette() -> list[str]:
    """128 bright OLED-like foreground colors."""
    out = []
    for i in range(128):
        h = i / 128.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.72, 1.0)
        out.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
    return out


PALETTE = make_palette()


class BloomPetzMini(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BloomPetz Mini")
        self.geometry(f"{SCREEN_W}x{SCREEN_H + HEADER_H}")
        self.resizable(False, False)
        self.configure(bg="#050505")
        self.overrideredirect(True)

        self.rx: queue.Queue[str] = queue.Queue()
        self.stop_event = threading.Event()
        self.ser: serial.Serial | None = None
        self.ser_lock = threading.Lock()
        self.connected_port: str | None = None
        self.first_seen: dict[str, float] = {}
        self.last_probe: dict[str, float] = {}
        self.key_down: set[str] = set()
        self.screen_lines = [" " * 16 for _ in range(4)]
        self.color_index = self._load_color_index()

        self._drag_x = 0
        self._drag_y = 0
        self._build_ui()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.close_app)

        threading.Thread(target=self._connection_loop, daemon=True).start()
        self.after(25, self._drain_rx)
        self.after(100, self.focus_force)

    def _build_ui(self):
        self.header = tk.Frame(self, bg="#151515", height=HEADER_H)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.header.bind("<ButtonPress-1>", self._drag_start)
        self.header.bind("<B1-Motion>", self._drag_move)

        self.title_label = tk.Label(
            self.header,
            text="BloomPetz",
            bg="#151515",
            fg="#b8b8b8",
            font=("DejaVu Sans", 9, "bold"),
        )
        self.title_label.pack(side="left", padx=(9, 4))
        self.title_label.bind("<ButtonPress-1>", self._drag_start)
        self.title_label.bind("<B1-Motion>", self._drag_move)

        close = tk.Button(
            self.header,
            text="×",
            command=self.close_app,
            bg="#151515",
            fg="#dddddd",
            activebackground="#333333",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            width=3,
            font=("DejaVu Sans", 12, "bold"),
            takefocus=False,
        )
        close.pack(side="right")

        next_color = tk.Button(
            self.header,
            text="›",
            command=lambda: self.change_color(1),
            bg="#151515",
            fg="#dddddd",
            activebackground="#333333",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            width=2,
            font=("DejaVu Sans", 12, "bold"),
            takefocus=False,
        )
        next_color.pack(side="right")

        self.swatch = tk.Label(
            self.header,
            text="●",
            bg="#151515",
            fg=PALETTE[self.color_index],
            font=("DejaVu Sans", 11),
            width=2,
        )
        self.swatch.pack(side="right")

        prev_color = tk.Button(
            self.header,
            text="‹",
            command=lambda: self.change_color(-1),
            bg="#151515",
            fg="#dddddd",
            activebackground="#333333",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            width=2,
            font=("DejaVu Sans", 12, "bold"),
            takefocus=False,
        )
        prev_color.pack(side="right")

        self.screen = tk.Frame(self, bg="#000000", width=SCREEN_W, height=SCREEN_H)
        self.screen.pack(fill="both", expand=True)
        self.screen.pack_propagate(False)

        self.line_labels: list[tk.Label] = []
        for i in range(4):
            label = tk.Label(
                self.screen,
                text=self.screen_lines[i],
                bg="#000000",
                fg=PALETTE[self.color_index],
                font=FONT,
                anchor="center",
                justify="center",
                padx=0,
                pady=0,
            )
            label.place(relx=0.5, rely=(i + 0.5) / 4.0, anchor="center")
            self.line_labels.append(label)

    def _bind_keys(self):
        mapping = {
            "Up": "UP",
            "Down": "DOWN",
            "Left": "LEFT",
            "Right": "RIGHT",
            "a": "A",
            "A": "A",
            "b": "B",
            "B": "B",
        }
        for keysym, bpkey in mapping.items():
            self.bind_all(f"<KeyPress-{keysym}>", lambda e, k=bpkey: self._key_press(k))
            self.bind_all(f"<KeyRelease-{keysym}>", lambda e, k=bpkey: self._key_release(k))

    def _key_press(self, key: str):
        # Ignore OS key-repeat; BloomPetz has no hold behaviors.
        if key in self.key_down:
            return "break"
        self.key_down.add(key)
        self.send(f"KEY {key}")
        return "break"

    def _key_release(self, key: str):
        self.key_down.discard(key)
        return "break"

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _drag_move(self, event):
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _load_color_index(self) -> int:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                value = int(json.load(f).get("color_index", 42))
                return value % 128
        except Exception:
            return 42

    def _save_color_index(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"color_index": self.color_index}, f)
        except Exception:
            pass

    def change_color(self, delta: int):
        self.color_index = (self.color_index + delta) % 128
        color = PALETTE[self.color_index]
        self.swatch.configure(fg=color)
        for label in self.line_labels:
            label.configure(fg=color)
        self._save_color_index()
        self.focus_force()

    def _set_connected(self, connected: bool):
        self.title_label.configure(
            text="BloomPetz" if connected else "BloomPetz ·",
            fg="#d8d8d8" if connected else "#777777",
        )

    def _open_candidate(self, port: str) -> serial.Serial | None:
        s = None
        try:
            s = serial.Serial()
            s.port = port
            s.baudrate = BAUD
            s.timeout = 0.12
            s.write_timeout = 0.25
            s.dtr = False
            s.rts = False
            s.open()
            s.dtr = False
            s.rts = False
            try:
                s.reset_input_buffer()
            except Exception:
                pass

            s.write(b"HELLO\n")
            s.flush()
            deadline = time.monotonic() + HANDSHAKE_TIMEOUT
            while time.monotonic() < deadline:
                raw = s.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if line:
                    self.rx.put(line)
                if line.startswith("BP|IDENTITY|product=BloomPetz|"):
                    return s
            s.close()
            return None
        except Exception:
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass
            return None

    def _connection_loop(self):
        while not self.stop_event.is_set():
            if self.ser is not None:
                try:
                    raw = self.ser.readline()
                    if raw:
                        self.rx.put(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
                except Exception:
                    self._drop_serial()
                continue

            now = time.monotonic()
            ports = set(serial_ports())

            for port in list(self.first_seen):
                if port not in ports:
                    self.first_seen.pop(port, None)
                    self.last_probe.pop(port, None)

            for port in ports:
                self.first_seen.setdefault(port, now)

            if not programmer_running():
                for port in sorted(ports):
                    if now - self.first_seen.get(port, now) < STABLE_SECONDS:
                        continue
                    if now - self.last_probe.get(port, 0.0) < RETRY_SECONDS:
                        continue
                    self.last_probe[port] = now
                    s = self._open_candidate(port)
                    if s is None:
                        continue
                    with self.ser_lock:
                        self.ser = s
                        self.connected_port = port
                    self.rx.put("APP|CONNECTED")
                    self._send_initial_state()
                    break

            time.sleep(POLL_SECONDS)

    def _send_initial_state(self):
        self.send(f"SET DATE {dt.date.today().isoformat()}")
        self.send("GET SCREEN")

    def _drop_serial(self):
        with self.ser_lock:
            s = self.ser
            self.ser = None
            self.connected_port = None
        try:
            if s is not None:
                s.close()
        except Exception:
            pass
        self.rx.put("APP|DISCONNECTED")

    def send(self, command: str):
        with self.ser_lock:
            s = self.ser
        if s is None or not s.is_open:
            return
        try:
            s.write((command.strip() + "\n").encode("utf-8"))
            s.flush()
        except Exception:
            self._drop_serial()

    def _drain_rx(self):
        try:
            while True:
                line = self.rx.get_nowait()
                self._handle_line(line)
        except queue.Empty:
            pass
        if not self.stop_event.is_set():
            self.after(25, self._drain_rx)

    def _handle_line(self, line: str):
        if line == "APP|CONNECTED":
            self._set_connected(True)
            return
        if line == "APP|DISCONNECTED":
            self._set_connected(False)
            return
        if not line.startswith("BP|SCREEN|"):
            return

        fields: dict[str, str] = {}
        for part in line.split("|")[2:]:
            if "=" in part:
                key, value = part.split("=", 1)
                fields[key] = value
        for i in range(4):
            text = fields.get(str(i + 1), self.screen_lines[i])[:16].ljust(16)
            self.screen_lines[i] = text
            self.line_labels[i].configure(text=text)

    def close_app(self):
        self.stop_event.set()
        self._drop_serial()
        self.destroy()


if __name__ == "__main__":
    BloomPetzMini().mainloop()
