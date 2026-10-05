#!/usr/bin/env python3
"""BloomPetz Mini — half-size OLED mirror + keyboard controller.

App-only color selector: changes this window's text color only.
Lifecycle follows HAPPY JARZ: open one assigned USB port, keep it, and close
this app after the controller is physically gone for the disconnect grace.
"""
from __future__ import annotations

import colorsys
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
POLL_SECONDS = 0.20
STABLE_SECONDS = 2.0
DISCONNECT_GRACE_SEC = 3.0
CONFIG_PATH = os.path.expanduser("~/.config/bloompetz/mini.json")
ASSIGNED_PORT = os.environ.get("BLOOMPETZ_PORT", "").strip()

SCREEN_W = 192
SCREEN_H = 96
HEADER_H = 18
FONT = ("DejaVu Sans Mono", 10, "bold")
HEADER_FONT = ("DejaVu Sans", 7, "bold")


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
    out = []
    for i in range(128):
        r, g, b = colorsys.hsv_to_rgb(i / 128.0, 0.72, 1.0)
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

        self.rx: queue.Queue[tuple] = queue.Queue()
        self.running = True
        self.ser: serial.Serial | None = None
        self.ser_lock = threading.Lock()
        self.connected_port: str | None = None
        self.key_down: set[str] = set()
        self.screen_lines = [" " * 16 for _ in range(4)]
        self.pet_name = "NO PET"
        self.color_index = self._load_color_index()
        self._drag_x = self._drag_y = 0

        self._build_ui()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        threading.Thread(target=self._serial_worker, daemon=True).start()
        self.after(25, self._drain_rx)
        self.after(100, self.focus_force)

    def _build_ui(self):
        self.header = tk.Frame(self, bg="#151515", height=HEADER_H)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.header.bind("<ButtonPress-1>", self._drag_start)
        self.header.bind("<B1-Motion>", self._drag_move)

        self.title_label = tk.Label(
            self.header, text=self.pet_name, bg="#151515", fg="#888888",
            font=HEADER_FONT, anchor="w"
        )
        self.title_label.pack(side="left", padx=(4, 1))
        self.title_label.bind("<ButtonPress-1>", self._drag_start)
        self.title_label.bind("<B1-Motion>", self._drag_move)

        close = tk.Label(
            self.header, text="×", bg="#151515", fg="#dddddd",
            width=2, font=("DejaVu Sans", 9, "bold"), cursor="hand2"
        )
        close.pack(side="right")
        close.bind("<Button-1>", self._close_click)

        self.next_color = tk.Label(
            self.header, text="▶", bg="#151515", fg="#eeeeee",
            width=2, font=("DejaVu Sans", 8, "bold"), cursor="hand2"
        )
        self.next_color.pack(side="right")
        self.next_color.bind("<Button-1>", lambda _e: self._color_click(1))

        self.color_label = tk.Label(
            self.header, text="COLOR", bg="#151515", fg=PALETTE[self.color_index],
            width=5, font=("DejaVu Sans", 7, "bold"), cursor="hand2"
        )
        self.color_label.pack(side="right")
        self.color_label.bind("<Button-1>", lambda _e: self._color_click(1))

        self.prev_color = tk.Label(
            self.header, text="◀", bg="#151515", fg="#eeeeee",
            width=2, font=("DejaVu Sans", 8, "bold"), cursor="hand2"
        )
        self.prev_color.pack(side="right")
        self.prev_color.bind("<Button-1>", lambda _e: self._color_click(-1))

        self.screen = tk.Frame(self, bg="#000000", width=SCREEN_W, height=SCREEN_H)
        self.screen.pack(fill="both", expand=True)
        self.screen.pack_propagate(False)
        self.line_labels = []
        for i in range(4):
            label = tk.Label(
                self.screen, text=self.screen_lines[i], bg="#000000",
                fg=PALETTE[self.color_index], font=FONT,
                anchor="center", justify="center", padx=0, pady=0
            )
            label.place(relx=0.5, rely=(i + 0.5) / 4.0, anchor="center")
            self.line_labels.append(label)

    def _bind_keys(self):
        mapping = {
            "Up":"UP", "Down":"DOWN", "Left":"LEFT", "Right":"RIGHT",
            "a":"A", "A":"A", "b":"B", "B":"B"
        }
        for keysym, bpkey in mapping.items():
            self.bind_all(f"<KeyPress-{keysym}>", lambda _e, k=bpkey: self._key_press(k))
            self.bind_all(f"<KeyRelease-{keysym}>", lambda _e, k=bpkey: self._key_release(k))

    def _key_press(self, key: str):
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
        self.geometry(f"+{event.x_root-self._drag_x}+{event.y_root-self._drag_y}")

    def _close_click(self, _event=None):
        self.close_app()
        return "break"

    def _color_click(self, delta: int):
        self.color_index = (self.color_index + delta) % 128
        color = PALETTE[self.color_index]
        self.color_label.configure(fg=color)
        for label in self.line_labels:
            label.configure(fg=color)
        self._save_color_index()
        self.after_idle(self.focus_force)
        return "break"

    def _load_color_index(self) -> int:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return int(json.load(f).get("color_index", 42)) % 128
        except Exception:
            return 42

    def _save_color_index(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"color_index": self.color_index}, f)
        except Exception:
            pass

    def _set_connected(self, connected: bool):
        self.title_label.configure(
            text=self.pet_name,
            fg="#d8d8d8" if connected else "#777777"
        )

    def _choose_port(self) -> str | None:
        if ASSIGNED_PORT:
            return ASSIGNED_PORT if os.path.exists(ASSIGNED_PORT) else None
        ports = serial_ports()
        return ports[0] if ports else None

    def _open_port(self, port: str) -> serial.Serial:
        s = serial.Serial()
        s.port = port
        s.baudrate = BAUD
        s.timeout = 0.25
        s.write_timeout = 0.25
        s.dtr = False
        s.rts = False
        s.open()
        s.dtr = False
        s.rts = False
        return s

    def _serial_worker(self):
        seen_since = None
        while self.running:
            if programmer_running():
                time.sleep(POLL_SECONDS)
                continue

            if self.ser is None:
                port = self._choose_port()
                if port is None:
                    if ASSIGNED_PORT:
                        self.rx.put(("quit",))
                        return
                    seen_since = None
                    time.sleep(POLL_SECONDS)
                    continue
                if seen_since is None:
                    seen_since = time.monotonic()
                if time.monotonic() - seen_since < STABLE_SECONDS:
                    time.sleep(POLL_SECONDS)
                    continue
                try:
                    s = self._open_port(port)
                except Exception:
                    time.sleep(0.4)
                    continue
                with self.ser_lock:
                    self.ser = s
                    self.connected_port = port
                self.rx.put(("status", True))
                time.sleep(0.15)
                self.send("HELLO")
                self.send("GET SCREEN")
                self.send("GET STATUS")
                continue

            port = self.connected_port
            if not port:
                self.rx.put(("quit",))
                return

            if not os.path.exists(port):
                missing_since = time.monotonic()
                while self.running and not os.path.exists(port):
                    if time.monotonic() - missing_since >= DISCONNECT_GRACE_SEC:
                        self.rx.put(("quit",))
                        return
                    time.sleep(POLL_SECONDS)
                continue

            try:
                raw = self.ser.readline() if self.ser else b""
            except Exception:
                if not os.path.exists(port):
                    self.rx.put(("quit",))
                    return
                time.sleep(POLL_SECONDS)
                continue
            if raw:
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if line:
                    self.rx.put(("line", line))

    def send(self, command: str):
        with self.ser_lock:
            s = self.ser
        if s is None or not s.is_open:
            return
        try:
            s.write((command.strip()+"\n").encode("utf-8"))
            s.flush()
        except Exception:
            pass

    @staticmethod
    def _fields(line: str) -> dict[str, str]:
        out = {}
        for part in line.split("|")[2:]:
            if "=" in part:
                k, v = part.split("=", 1)
                out[k] = v
        return out

    def _update_pet_name_from_screen(self):
        line2 = self.screen_lines[1].strip()
        if not line2 or line2.lower().startswith("slot "):
            self.pet_name = "NO PET"
        else:
            self.pet_name = line2.split()[0][:12]
        self.title_label.configure(text=self.pet_name)

    def _drain_rx(self):
        try:
            while True:
                item = self.rx.get_nowait()
                if item[0] == "status":
                    self._set_connected(bool(item[1]))
                elif item[0] == "line":
                    self._handle_line(item[1])
                elif item[0] == "quit":
                    self.close_app()
                    return
        except queue.Empty:
            pass
        if self.running:
            self.after(25, self._drain_rx)

    def _handle_line(self, line: str):
        if line.startswith("BP|STATUS|"):
            fields = self._fields(line)
            name = fields.get("name", "").strip()
            occupied = fields.get("occupied", "0") == "1"
            self.pet_name = name[:12] if occupied and name else "NO PET"
            self.title_label.configure(text=self.pet_name)
            return

        if line.startswith("BP|BOOT|") or line.startswith("BP|IDENTITY|"):
            self._set_connected(True)
            return

        if not line.startswith("BP|SCREEN|"):
            return

        fields = self._fields(line)
        for i in range(4):
            text = fields.get(str(i+1), self.screen_lines[i])[:16].ljust(16)
            self.screen_lines[i] = text
            self.line_labels[i].configure(text=text)
        self._update_pet_name_from_screen()

    def close_app(self):
        if not self.running:
            return
        self.running = False
        with self.ser_lock:
            s = self.ser
            self.ser = None
        try:
            if s:
                s.close()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    BloomPetzMini().mainloop()
