#!/usr/bin/env python3
"""BloomGyro Mini — live orientation monitor, ZERO control, and CSV logger.

Uses the proven BloomPetz ESP32-S3 serial-open pattern:
DTR/RTS are forced low before and after open so attaching the app does not
intentionally reset the controller.
"""
from __future__ import annotations

import csv
import glob
from collections import deque
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
WINDOW_H = 285


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
        self.recent_samples = deque(maxlen=120)
        self.cal_window = None
        self.cal_step_index = 0
        self.cal_rows = []
        self.cal_csv_path = None
        self.cal_txt_path = None

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

        self.cal_btn = tk.Button(
            controls, text="SIMON CAL", command=self.open_calibration,
            state="disabled", bg="#242424", fg="#ffffff",
            activebackground="#333333", activeforeground="#ffffff",
            font=("DejaVu Sans", 9, "bold"), relief="raised", bd=2
        )
        self.cal_btn.pack(side="left", padx=(6, 0))

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

    CAL_STEPS = [
        ("FLAT / STILL", "Keep the whole rig flat and still. This starts a fresh zero.", "BASE", 0),

        ("CW 45°", "Rotate CLOCKWISE to exactly 45° from the start mark; keep it flat and hold still.", "Z", 45),
        ("CW 90°", "Continue CLOCKWISE to exactly 90° from the start mark; hold still.", "Z", 90),
        ("CW 135°", "Continue CLOCKWISE to exactly 135°; hold still.", "Z", 135),
        ("CW 180°", "Continue CLOCKWISE to exactly 180°; hold still.", "Z", 180),
        ("CW 225°", "Continue CLOCKWISE to exactly 225°; hold still.", "Z", 225),
        ("CW 270°", "Continue CLOCKWISE to exactly 270°; hold still.", "Z", 270),
        ("CW 315°", "Continue CLOCKWISE to exactly 315°; hold still.", "Z", 315),
        ("CW 360°", "Complete one full CLOCKWISE turn to 360° / the original physical heading; hold still.", "Z", 360),

        ("RE-ZERO FOR CCW", "Return to the original physical start mark. Press capture and the app will set a fresh zero.", "REZERO", 0),

        ("CCW 45°", "Rotate COUNTERCLOCKWISE to exactly 45° from the start mark; keep it flat and hold still.", "Z", -45),
        ("CCW 90°", "Continue COUNTERCLOCKWISE to exactly 90°; hold still.", "Z", -90),
        ("CCW 135°", "Continue COUNTERCLOCKWISE to exactly 135°; hold still.", "Z", -135),
        ("CCW 180°", "Continue COUNTERCLOCKWISE to exactly 180°; hold still.", "Z", -180),
        ("CCW 225°", "Continue COUNTERCLOCKWISE to exactly 225°; hold still.", "Z", -225),
        ("CCW 270°", "Continue COUNTERCLOCKWISE to exactly 270°; hold still.", "Z", -270),
        ("CCW 315°", "Continue COUNTERCLOCKWISE to exactly 315°; hold still.", "Z", -315),
        ("CCW 360°", "Complete one full COUNTERCLOCKWISE turn to 360° / the original physical heading; hold still.", "Z", -360),

        ("RE-ZERO FOR TILT", "Return to the original flat/start position. Press capture for a fresh tilt zero.", "REZERO", 0),
        ("FRONT EDGE UP 45°", "Lift the FRONT edge about 45° and hold still.", "TILT", 45),
        ("BACK EDGE UP 45°", "Return flat, then lift the BACK edge about 45° and hold still.", "TILT", 45),
        ("RIGHT EDGE UP 45°", "Return flat, then lift the RIGHT edge about 45° and hold still.", "TILT", 45),
        ("LEFT EDGE UP 45°", "Return flat, then lift the LEFT edge about 45° and hold still.", "TILT", 45),
    ]

    def open_calibration(self):
        if self.cal_window is not None and self.cal_window.winfo_exists():
            self.cal_window.lift()
            return

        self.cal_step_index = 0
        self.cal_rows = []
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.cal_csv_path = LOG_DIR / f"bloomgyro_cal_{stamp}.csv"
        self.cal_txt_path = LOG_DIR / f"bloomgyro_cal_{stamp}.txt"

        w = tk.Toplevel(self)
        self.cal_window = w
        w.title("BloomGyro Simon Calibration")
        w.geometry("500x350")
        w.resizable(False, False)
        w.configure(bg="#111111")

        tk.Label(
            w, text="SIMON SAYS — CALIBRATION RUN",
            bg="#111111", fg="#ffffff", font=("DejaVu Sans", 12, "bold")
        ).pack(pady=(12, 4))

        self.cal_progress_lbl = tk.Label(
            w, text="", bg="#111111", fg="#888888",
            font=("DejaVu Sans Mono", 9)
        )
        self.cal_progress_lbl.pack()

        self.cal_title_lbl = tk.Label(
            w, text="", bg="#050505", fg="#00e5ff",
            font=("DejaVu Sans", 16, "bold"), width=34, height=2
        )
        self.cal_title_lbl.pack(padx=12, pady=(8, 2))

        self.cal_instruction_lbl = tk.Label(
            w, text="", bg="#111111", fg="#dddddd",
            font=("DejaVu Sans", 10), wraplength=430, justify="center"
        )
        self.cal_instruction_lbl.pack(padx=16, pady=(5, 8))

        self.cal_live_lbl = tk.Label(
            w, text="X +000.0   Y +000.0   Z +000.0",
            bg="#111111", fg="#bdbdbd", font=("DejaVu Sans Mono", 10, "bold")
        )
        self.cal_live_lbl.pack(pady=4)

        self.cal_note_lbl = tk.Label(
            w, text="Move into the requested position, HOLD STILL, then capture.",
            bg="#111111", fg="#777777", font=("DejaVu Sans", 8)
        )
        self.cal_note_lbl.pack(pady=(2, 6))

        buttons = tk.Frame(w, bg="#111111")
        buttons.pack(fill="x", padx=12, pady=8)

        self.cal_capture_btn = tk.Button(
            buttons, text="ZERO & START", command=self.calibration_capture,
            bg="#242424", fg="#ffffff", activebackground="#333333",
            activeforeground="#ffffff", font=("DejaVu Sans", 10, "bold")
        )
        self.cal_capture_btn.pack(side="left", fill="x", expand=True)

        tk.Button(
            buttons, text="CANCEL", command=self.close_calibration,
            bg="#242424", fg="#cccccc", activebackground="#333333",
            activeforeground="#ffffff", font=("DejaVu Sans", 9)
        ).pack(side="left", padx=(8, 0))

        self.cal_result_lbl = tk.Label(
            w, text="", bg="#111111", fg="#6dff8a",
            font=("DejaVu Sans Mono", 8), wraplength=440, justify="left"
        )
        self.cal_result_lbl.pack(padx=12, pady=(4, 8))

        w.protocol("WM_DELETE_WINDOW", self.close_calibration)
        self._show_cal_step()

    def close_calibration(self):
        if self.cal_window is not None:
            try:
                self.cal_window.destroy()
            except Exception:
                pass
        self.cal_window = None

    def _show_cal_step(self):
        if self.cal_window is None or not self.cal_window.winfo_exists():
            return
        total = len(self.CAL_STEPS)
        if self.cal_step_index >= total:
            self._finish_calibration()
            return
        title, instruction, _axis, _target = self.CAL_STEPS[self.cal_step_index]
        self.cal_progress_lbl.configure(text=f"STEP {self.cal_step_index + 1} / {total}")
        self.cal_title_lbl.configure(text=title)
        self.cal_instruction_lbl.configure(text=instruction)
        _title, _instruction, axis, _target = self.CAL_STEPS[self.cal_step_index]
        if self.cal_step_index == 0:
            button_text = "ZERO & START"
        elif axis == "REZERO":
            button_text = "SET FRESH ZERO"
        else:
            button_text = "CAPTURE / NEXT"
        self.cal_capture_btn.configure(text=button_text, state="normal")

    def _recent_average(self, seconds: float = 0.7):
        cutoff = time.monotonic() - seconds
        rows = [r for r in self.recent_samples if r["t"] >= cutoff]
        if len(rows) < 3:
            rows = list(self.recent_samples)[-5:]
        if not rows:
            return None

        def avg(key):
            return sum(r[key] for r in rows) / len(rows)

        def lo(key):
            return min(r[key] for r in rows)

        def hi(key):
            return max(r[key] for r in rows)

        return {
            "n": len(rows),
            "x": avg("x"), "y": avg("y"), "z": avg("z"),
            "gz": avg("gz_dps"), "touch": round(avg("touch")),
            "x_min": lo("x"), "x_max": hi("x"),
            "y_min": lo("y"), "y_max": hi("y"),
            "z_min": lo("z"), "z_max": hi("z"),
        }

    def calibration_capture(self):
        if self.cal_step_index >= len(self.CAL_STEPS):
            return
        _title, _instruction, axis, _target = self.CAL_STEPS[self.cal_step_index]
        if self.cal_step_index == 0 or axis == "REZERO":
            self.send("ZERO")
            self.cal_capture_btn.configure(text="ZEROING...", state="disabled")
            self.after(850, self._capture_current_cal_step)
            return
        self._capture_current_cal_step()

    def _capture_current_cal_step(self):
        if self.cal_step_index >= len(self.CAL_STEPS):
            return
        snap = self._recent_average()
        if snap is None:
            self.cal_result_lbl.configure(text="No live samples yet — hold still and try again.", fg="#ff6666")
            self.cal_capture_btn.configure(state="normal", text="CAPTURE / NEXT")
            return

        title, instruction, axis, target = self.CAL_STEPS[self.cal_step_index]
        row = {
            "step": self.cal_step_index + 1,
            "title": title,
            "instruction": instruction,
            "target_axis": axis,
            "target_deg": target,
            **snap,
        }
        self.cal_rows.append(row)
        self._log_event(
            "CAL_CAPTURE",
            detail=f"step={row['step']}|title={title}|target={target}|avg_x={snap['x']:.2f}|avg_y={snap['y']:.2f}|avg_z={snap['z']:.2f}"
        )
        error_text = ""
        if axis == "Z":
            err = snap["z"] - target
            error_text = f"   ERR {err:+.1f}°"
        self.cal_result_lbl.configure(
            text=f"CAPTURED  X {snap['x']:+.1f}°   Y {snap['y']:+.1f}°   Z {snap['z']:+.1f}°{error_text}   ({snap['n']} samples)",
            fg="#6dff8a"
        )
        self.cal_step_index += 1
        self.after(350, self._show_cal_step)

    def _finish_calibration(self):
        if not self.cal_rows:
            return

        with self.cal_csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "step", "instruction_name", "instruction", "target_axis", "target_deg",
                "samples", "avg_x_deg", "avg_y_deg", "avg_z_deg", "z_error_deg", "z_ratio_measured_over_target",
                "avg_gz_dps", "avg_touch", "x_min", "x_max", "y_min", "y_max", "z_min", "z_max"
            ])
            for r in self.cal_rows:
                zerr = r["z"] - r["target_deg"] if r["target_axis"] == "Z" else ""
                zratio = (r["z"] / r["target_deg"]) if r["target_axis"] == "Z" and r["target_deg"] else ""
                writer.writerow([
                    r["step"], r["title"], r["instruction"], r["target_axis"], r["target_deg"],
                    r["n"], f"{r['x']:.3f}", f"{r['y']:.3f}", f"{r['z']:.3f}",
                    f"{zerr:.3f}" if zerr != "" else "",
                    f"{zratio:.6f}" if zratio != "" else "",
                    f"{r['gz']:.3f}", r["touch"],
                    f"{r['x_min']:.3f}", f"{r['x_max']:.3f}",
                    f"{r['y_min']:.3f}", f"{r['y_max']:.3f}",
                    f"{r['z_min']:.3f}", f"{r['z_max']:.3f}",
                ])

        with self.cal_txt_path.open("w", encoding="utf-8") as f:
            f.write("BloomGyro Simon Calibration Report\n")
            f.write(f"Created: {datetime.now().astimezone().isoformat()}\n")
            f.write(f"IMU WHO_AM_I: {self.whoami}\n")
            f.write(f"Hardware: OLED={self.boot['oled']} MPU={self.boot['mpu']} LED={self.boot['led']}\n\n")
            for r in self.cal_rows:
                extra = ""
                if r["target_axis"] == "Z":
                    err = r["z"] - r["target_deg"]
                    ratio = (r["z"] / r["target_deg"]) if r["target_deg"] else 0.0
                    extra = f" | err={err:+.2f} | ratio={ratio:+.4f}"
                f.write(
                    f"{r['step']:02d}. {r['title']} | target={r['target_deg']} "
                    f"| X={r['x']:+.2f} Y={r['y']:+.2f} Z={r['z']:+.2f} "
                    f"| gz={r['gz']:+.2f} dps | n={r['n']}{extra}\n"
                )

        self._log_event("CAL_COMPLETE", detail=str(self.cal_csv_path))
        self.cal_progress_lbl.configure(text="CALIBRATION COMPLETE")
        self.cal_title_lbl.configure(text="DONE")
        self.cal_instruction_lbl.configure(
            text="The run is saved. Send me the calibration CSV or TXT and I can calculate the axis/scale corrections."
        )
        self.cal_capture_btn.configure(text="CLOSE", state="normal", command=self.close_calibration)
        self.cal_result_lbl.configure(
            text=f"CSV: {self.cal_csv_path.name}\nTXT: {self.cal_txt_path.name}",
            fg="#6dff8a"
        )

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
            self.cal_btn.configure(state="normal")

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
            self.recent_samples.append({
                "t": time.monotonic(),
                "x": self.values["x"], "y": self.values["y"], "z": self.values["z"],
                "gz_dps": self.values["gz_dps"], "touch": self.values["touch"],
            })
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
        if self.cal_window is not None and self.cal_window.winfo_exists():
            self.cal_live_lbl.configure(
                text=f"X {self.values['x']:+06.1f}   Y {self.values['y']:+06.1f}   Z {self.values['z']:+06.1f}"
            )
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
            self.cal_btn.configure(state="normal")
        else:
            self.status_lbl.configure(text="RECONNECTING", fg="#ffd166")
            self.port_lbl.configure(text=f"PORT: lost {port}")
            self.zero_btn.configure(state="disabled")
            self.cal_btn.configure(state="disabled")

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
