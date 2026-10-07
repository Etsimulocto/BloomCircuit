#!/usr/bin/env python3
"""BloomGyro Mini — live orientation monitor, ZERO control, and CSV logger.

Uses the proven BloomPetz ESP32-S3 serial-open pattern:
DTR/RTS are forced low before and after open so attaching the app does not
intentionally reset the controller.
"""
from __future__ import annotations

import csv
import glob
import os
import queue
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk

try:
    import serial
except ImportError as exc:
    raise SystemExit("pyserial is required: sudo apt install -y python3-serial") from exc

BAUD = 115200
POLL_SECONDS = 0.20
STABLE_SECONDS = 0.8
DISCONNECT_GRACE_SEC = 3.0
ASSIGNED_PORT = os.environ.get("BLOOMGYRO_PORT", "").strip()
LOG_DIR = Path(os.environ.get(
    "BLOOMGYRO_LOG_DIR",
    str(Path.home() / ".local" / "share" / "bloomgyro" / "logs"),
)).expanduser()

WINDOW_W = 330
WINDOW_H = 255


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
    if ASSIGNED_PORT:
        return [ASSIGNED_PORT] if os.path.exists(ASSIGNED_PORT) else []
    by_id = sorted(glob.glob("/dev/serial/by-id/*Espressif*"))
    if by_id:
        return by_id
    return sorted(glob.glob("/dev/ttyACM*"))


class BloomGyroMini(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BloomGyro Mini")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.resizable(False, False)

        self.running = True
        self.rx: queue.Queue[tuple] = queue.Queue()
        self.ser: serial.Serial | None = None
        self.ser_lock = threading.Lock()
        self.connected_port: str | None = None
        self.port_seen_since: dict[str, float] = {}

        self.values = {"x": 0.0, "y": 0.0, "z": 0.0, "gz_dps": 0.0, "touch": 0}
        self.boot = {"oled": "?", "mpu": "?", "led": "?"}
        self.whoami = "?"
        self.samples = 0
        self.last_rx_monotonic = 0.0
        self.zero_count = 0

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = LOG_DIR / f"bloomgyro_{stamp}.csv"
        self.log_file = self.log_path.open("w", newline="", encoding="utf-8")
        self.log = csv.writer(self.log_file)
        self.log.writerow([
            "local_time_iso", "monotonic_s", "event", "x_deg", "y_deg", "z_deg",
            "gz_dps", "touch", "port", "oled_ok", "mpu_ok", "led_ok", "detail"
        ])
        self.log_file.flush()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        threading.Thread(target=self._serial_worker, daemon=True).start()
        self.after(25, self._drain_rx)
        self.after(250, self._refresh_age)

    def _build_ui(self):
        self.configure(bg="#111111")

        top = tk.Frame(self, bg="#111111")
        top.pack(fill="x", padx=10, pady=(9, 4))
        self.title_lbl = tk.Label(
            top, text="BLOOMGYRO", bg="#111111", fg="#e7e7e7",
            font=("DejaVu Sans", 11, "bold")
        )
        self.title_lbl.pack(side="left")
        self.status_lbl = tk.Label(
            top, text="CONNECTING", bg="#111111", fg="#888888",
            font=("DejaVu Sans Mono", 8, "bold")
        )
        self.status_lbl.pack(side="right")

        axes = tk.Frame(self, bg="#050505", bd=1, relief="solid")
        axes.pack(fill="x", padx=10, pady=4)
        self.axis_labels = {}
        for col, axis in enumerate(("X", "Y", "Z")):
            cell = tk.Frame(axes, bg="#050505")
            cell.grid(row=0, column=col, sticky="nsew", padx=1)
            axes.columnconfigure(col, weight=1)
            tk.Label(
                cell, text=axis, bg="#050505", fg="#888888",
                font=("DejaVu Sans", 8, "bold")
            ).pack(pady=(7, 0))
            value = tk.Label(
                cell, text="+000.0°", bg="#050505", fg="#00e5ff",
                font=("DejaVu Sans Mono", 16, "bold")
            )
            value.pack(padx=5, pady=(0, 8))
            self.axis_labels[axis.lower()] = value

        stats = tk.Frame(self, bg="#111111")
        stats.pack(fill="x", padx=11, pady=(3, 1))
        self.gz_lbl = tk.Label(
            stats, text="Z RATE   +000.00°/s", bg="#111111", fg="#bdbdbd",
            font=("DejaVu Sans Mono", 9)
        )
        self.gz_lbl.pack(anchor="w")
        self.touch_lbl = tk.Label(
            stats, text="TOUCH    0", bg="#111111", fg="#bdbdbd",
            font=("DejaVu Sans Mono", 9)
        )
        self.touch_lbl.pack(anchor="w")
        self.hw_lbl = tk.Label(
            stats, text="IMU ?   OLED ?   LED ?", bg="#111111", fg="#777777",
            font=("DejaVu Sans Mono", 8)
        )
        self.hw_lbl.pack(anchor="w", pady=(2, 0))

        controls = tk.Frame(self, bg="#111111")
        controls.pack(fill="x", padx=10, pady=(7, 3))

        self.zero_btn = tk.Button(
            controls, text="ZERO / RESET", command=self.zero_reference,
            state="disabled", bg="#242424", fg="#ffffff",
            activebackground="#333333", activeforeground="#ffffff",
            font=("DejaVu Sans", 10, "bold"), relief="raised", bd=2
        )
        self.zero_btn.pack(side="left", fill="x", expand=True)

        self.sample_lbl = tk.Label(
            controls, text="0 samples", bg="#111111", fg="#777777",
            font=("DejaVu Sans Mono", 8)
        )
        self.sample_lbl.pack(side="right", padx=(8, 0))

        self.log_lbl = tk.Label(
            self, text=f"LOG: {self.log_path.name}", bg="#111111", fg="#666666",
            font=("DejaVu Sans Mono", 7), anchor="w"
        )
        self.log_lbl.pack(fill="x", padx=11, pady=(2, 1))

        self.port_lbl = tk.Label(
            self, text="PORT: waiting", bg="#111111", fg="#666666",
            font=("DejaVu Sans Mono", 7), anchor="w"
        )
        self.port_lbl.pack(fill="x", padx=11)

    @staticmethod
    def _fields(line: str) -> dict[str, str]:
        out = {}
        for part in line.split("|")[2:]:
            if "=" in part:
                k, v = part.split("=", 1)
                out[k] = v
        return out

    @staticmethod
    def _f(fields: dict[str, str], key: str, default: float = 0.0) -> float:
        try:
            return float(fields.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _i(fields: dict[str, str], key: str, default: int = 0) -> int:
        try:
            return int(fields.get(key, default))
        except (TypeError, ValueError):
            return default

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
        while self.running:
            if programmer_running():
                time.sleep(POLL_SECONDS)
                continue

            if self.ser is None:
                ports = serial_ports()
                if not ports:
                    self.port_seen_since.clear()
                    time.sleep(POLL_SECONDS)
                    continue

                opened = False
                now = time.monotonic()
                for port in ports:
                    first = self.port_seen_since.setdefault(port, now)
                    if now - first < STABLE_SECONDS:
                        continue
                    try:
                        s = self._open_port(port)
                    except Exception:
                        continue
                    with self.ser_lock:
                        self.ser = s
                        self.connected_port = port
                    self.rx.put(("status", True, port))
                    self._log_event("CONNECT", detail=port)
                    time.sleep(0.12)
                    self.send("HELLO")
                    self.send("GET STATUS")
                    opened = True
                    break
                if not opened:
                    time.sleep(POLL_SECONDS)
                continue

            try:
                raw = self.ser.readline() if self.ser else b""
            except Exception as exc:
                port = self.connected_port or ""
                self._log_event("DISCONNECT", detail=str(exc))
                with self.ser_lock:
                    old = self.ser
                    self.ser = None
                    self.connected_port = None
                try:
                    if old:
                        old.close()
                except Exception:
                    pass
                self.rx.put(("status", False, port))
                self.port_seen_since.clear()

                # When launched by the plug watcher, the assigned path represents
                # this exact BloomGyro. Brief USB re-enumeration is tolerated;
                # a real unplug closes the Mini automatically.
                if ASSIGNED_PORT:
                    missing_since = time.monotonic()
                    while self.running and not os.path.exists(ASSIGNED_PORT):
                        if time.monotonic() - missing_since >= DISCONNECT_GRACE_SEC:
                            self.rx.put(("quit",))
                            return
                        time.sleep(POLL_SECONDS)

                time.sleep(0.35)
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
            s.write((command.strip() + "\n").encode("utf-8"))
            s.flush()
            self._log_event("TX", detail=command.strip())
        except Exception as exc:
            self._log_event("TX_ERROR", detail=str(exc))

    def zero_reference(self):
        self.send("ZERO")
        self.zero_btn.configure(state="disabled", text="ZEROING...")
        self.after(500, self._reenable_zero)

    def _reenable_zero(self):
        if self.ser is not None:
            self.zero_btn.configure(state="normal", text="ZERO / RESET")

    def _log_event(self, event: str, detail: str = ""):
        try:
            self.log.writerow([
                datetime.now().astimezone().isoformat(timespec="milliseconds"),
                f"{time.monotonic():.3f}", event,
                f"{self.values['x']:.3f}", f"{self.values['y']:.3f}",
                f"{self.values['z']:.3f}", f"{self.values['gz_dps']:.3f}",
                self.values["touch"], self.connected_port or "",
                self.boot["oled"], self.boot["mpu"], self.boot["led"], detail
            ])
            self.log_file.flush()
        except Exception:
            pass

    def _handle_line(self, line: str):
        self.last_rx_monotonic = time.monotonic()

        if line.startswith("BG|ANGLES|"):
            f = self._fields(line)
            self.values["x"] = self._f(f, "x")
            self.values["y"] = self._f(f, "y")
            self.values["z"] = self._f(f, "z")
            self.values["gz_dps"] = self._f(f, "gz_dps")
            self.values["touch"] = self._i(f, "touch")
            self.samples += 1
            self._update_readout()
            self._log_event("ANGLES")
            return

        if line.startswith("BG|STATUS|"):
            f = self._fields(line)
            for key in ("oled", "mpu", "led"):
                if key in f:
                    self.boot[key] = f[key]
            for key in ("x", "y", "z", "gz_dps"):
                if key in f:
                    self.values[key] = self._f(f, key)
            if "touch" in f:
                self.values["touch"] = self._i(f, "touch")
            self._update_readout()
            return

        if line.startswith("BG|BOOT|"):
            f = self._fields(line)
            for key in ("oled", "mpu", "led"):
                self.boot[key] = f.get(key, self.boot[key])
            self._update_hw()
            self._log_event("BOOT", detail=line)
            return

        if line.startswith("BG|IMU|"):
            self.whoami = self._fields(line).get("whoami", "?")
            self._update_hw()
            self._log_event("IMU", detail=line)
            return

        if line.startswith("BG|ZERO|"):
            self.zero_count += 1
            self._log_event("ZERO", detail=line)
            self.zero_btn.configure(text=f"ZERO SET #{self.zero_count}")
            self.after(650, self._reenable_zero)
            return

        if line.startswith("BG|ERROR|"):
            self._log_event("ERROR", detail=line)
            self.status_lbl.configure(text="ERROR", fg="#ff6666")
            return

        if line.startswith("BG|IDENTITY|"):
            self._log_event("IDENTITY", detail=line)
            self.status_lbl.configure(text="LIVE", fg="#6dff8a")
            return

        if line.startswith("BG|CAL|"):
            self._log_event("CAL", detail=line)
            self.status_lbl.configure(text="CALIBRATING", fg="#ffd166")

    def _update_readout(self):
        for key in ("x", "y", "z"):
            self.axis_labels[key].configure(text=f"{self.values[key]:+06.1f}°")
        self.gz_lbl.configure(text=f"Z RATE   {self.values['gz_dps']:+07.2f}°/s")
        self.touch_lbl.configure(text=f"TOUCH    {self.values['touch']}")
        self.sample_lbl.configure(text=f"{self.samples} samples")
        self._update_hw()

    def _update_hw(self):
        imu = f"IMU {self.boot['mpu']}"
        if self.whoami != "?":
            imu += f" ({self.whoami})"
        self.hw_lbl.configure(
            text=f"{imu}   OLED {self.boot['oled']}   LED {self.boot['led']}"
        )

    def _set_connected(self, connected: bool, port: str = ""):
        if connected:
            self.status_lbl.configure(text="LIVE", fg="#6dff8a")
            self.port_lbl.configure(text=f"PORT: {port}")
            self.zero_btn.configure(state="normal", text="ZERO / RESET")
        else:
            self.status_lbl.configure(text="RECONNECTING", fg="#ffd166")
            self.port_lbl.configure(text=f"PORT: lost {port}")
            self.zero_btn.configure(state="disabled")

    def _drain_rx(self):
        try:
            while True:
                item = self.rx.get_nowait()
                if item[0] == "status":
                    self._set_connected(bool(item[1]), item[2])
                elif item[0] == "line":
                    self._handle_line(item[1])
                elif item[0] == "quit":
                    self.close_app()
                    return
        except queue.Empty:
            pass
        if self.running:
            self.after(25, self._drain_rx)

    def _refresh_age(self):
        if self.running:
            if self.ser is not None and self.last_rx_monotonic:
                age = time.monotonic() - self.last_rx_monotonic
                if age > 1.5:
                    self.status_lbl.configure(text=f"STALE {age:.1f}s", fg="#ffd166")
            self.after(250, self._refresh_age)

    def close_app(self):
        if not self.running:
            return
        self.running = False
        self._log_event("APP_CLOSE")
        with self.ser_lock:
            s = self.ser
            self.ser = None
        try:
            if s:
                s.close()
        except Exception:
            pass
        try:
            self.log_file.close()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    BloomGyroMini().mainloop()
