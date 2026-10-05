#!/usr/bin/env python3
"""BloomPetz desktop companion v0.1.

BloomCore role:
- live mirror of the device's four-line OLED contract
- send normal/service commands over USB CDC serial
- create/select/feed/treat pets without needing a serial terminal
- push the host's local calendar date to the pet on connect

Dependency: pyserial
Run: python3 bloompetz_app.py

The app intentionally speaks only the documented BP|... serial protocol. It does
not reach around the firmware or invent a second pet engine.
"""

from __future__ import annotations

import datetime as _dt
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    import serial.tools.list_ports
except ImportError as exc:
    raise SystemExit("pyserial is required: python3 -m pip install pyserial") from exc

BAUD = 115200


class BloomPetzApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BloomPetz")
        self.geometry("700x520")
        self.minsize(620, 460)

        self.ser: serial.Serial | None = None
        self.rx = queue.Queue()
        self.stop_event = threading.Event()
        self.reader_thread: threading.Thread | None = None

        self.screen_vars = [tk.StringVar(value=" " * 16) for _ in range(4)]
        self.status_var = tk.StringVar(value="Disconnected")
        self.port_var = tk.StringVar()
        self.slot_var = tk.IntVar(value=1)
        self.name_var = tk.StringVar(value="Lophire")
        self.type_var = tk.StringVar(value="Cat")
        self.art_var = tk.StringVar(value="[=^.^=] zZz")
        self.raw_var = tk.BooleanVar(value=False)

        self._build_ui()
        self.refresh_ports()
        self.after(50, self._drain_rx)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Port").pack(side="left")
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=24, state="readonly")
        self.port_box.pack(side="left", padx=6)
        ttk.Button(top, text="Refresh", command=self.refresh_ports).pack(side="left")
        ttk.Button(top, text="Connect", command=self.connect).pack(side="left", padx=6)
        ttk.Button(top, text="Disconnect", command=self.disconnect).pack(side="left")
        ttk.Label(top, textvariable=self.status_var).pack(side="right")

        display = ttk.LabelFrame(self, text="Live BloomPetz screen", padding=14)
        display.pack(fill="x", padx=10, pady=(0, 10))
        for var in self.screen_vars:
            ttk.Label(display, textvariable=var, font=("DejaVu Sans Mono", 22)).pack(anchor="center")

        controls = ttk.Frame(self, padding=(10, 0))
        controls.pack(fill="x")
        for label, command in [
            ("Feed", lambda: self.send("FEED")),
            ("Treat", lambda: self.send("TREAT")),
            ("Status", lambda: self.send("GET STATUS")),
            ("Slots", lambda: self.send("GET SLOTS")),
            ("Stats", lambda: self.send("GET STATS")),
            ("Touch diag", lambda: self.send("DIAG TOUCH")),
            ("LED diag", lambda: self.send("DIAG LED")),
        ]:
            ttk.Button(controls, text=label, command=command).pack(side="left", padx=3)

        creator = ttk.LabelFrame(self, text="Create / replace pet slot", padding=10)
        creator.pack(fill="x", padx=10, pady=10)
        ttk.Label(creator, text="Slot").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(creator, from_=1, to=3, width=4, textvariable=self.slot_var).grid(row=0, column=1, padx=4)
        ttk.Label(creator, text="Name").grid(row=0, column=2, sticky="w")
        ttk.Entry(creator, width=14, textvariable=self.name_var).grid(row=0, column=3, padx=4)
        ttk.Label(creator, text="Type").grid(row=0, column=4, sticky="w")
        ttk.Entry(creator, width=14, textvariable=self.type_var).grid(row=0, column=5, padx=4)
        ttk.Label(creator, text="16-char art").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(creator, width=24, textvariable=self.art_var).grid(row=1, column=1, columnspan=3, sticky="w", padx=4, pady=(8, 0))
        ttk.Button(creator, text="Create", command=self.create_pet).grid(row=1, column=5, sticky="e", pady=(8, 0))

        bottom = ttk.LabelFrame(self, text="Protocol log", padding=8)
        bottom.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log = tk.Text(bottom, height=9, font=("DejaVu Sans Mono", 9), wrap="none")
        self.log.pack(fill="both", expand=True)

        cmd = ttk.Frame(bottom)
        cmd.pack(fill="x", pady=(6, 0))
        self.command_entry = ttk.Entry(cmd)
        self.command_entry.pack(side="left", fill="x", expand=True)
        self.command_entry.bind("<Return>", lambda _e: self.send_manual())
        ttk.Button(cmd, text="Send", command=self.send_manual).pack(side="left", padx=(6, 0))

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_box["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])

    def connect(self):
        if self.ser and self.ser.is_open:
            return
        port = self.port_var.get().strip()
        if not port:
            messagebox.showerror("BloomPetz", "No serial port selected.")
            return
        try:
            self.ser = serial.Serial(port, BAUD, timeout=0.2)
        except Exception as exc:
            messagebox.showerror("BloomPetz", f"Could not open {port}:\n{exc}")
            return
        self.stop_event.clear()
        self.reader_thread = threading.Thread(target=self._reader, daemon=True)
        self.reader_thread.start()
        self.status_var.set(f"Connected: {port}")
        self.after(350, self._on_connected)

    def _on_connected(self):
        self.send("HELLO")
        self.send(f"SET DATE {_dt.date.today().isoformat()}")
        self.send("GET STATUS")
        self.send("GET SCREEN")
        self.send("GET SLOTS")

    def disconnect(self):
        self.stop_event.set()
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.status_var.set("Disconnected")

    def _reader(self):
        while not self.stop_event.is_set() and self.ser and self.ser.is_open:
            try:
                raw = self.ser.readline()
            except Exception as exc:
                self.rx.put(f"APP|ERROR|serial={exc}")
                return
            if raw:
                self.rx.put(raw.decode("utf-8", errors="replace").rstrip("\r\n"))

    def _drain_rx(self):
        try:
            while True:
                line = self.rx.get_nowait()
                self._handle_line(line)
        except queue.Empty:
            pass
        self.after(50, self._drain_rx)

    def _handle_line(self, line: str):
        self.log.insert("end", line + "\n")
        self.log.see("end")
        if line.startswith("BP|SCREEN|"):
            fields = {}
            for part in line.split("|")[2:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key] = value
            for i in range(4):
                self.screen_vars[i].set(fields.get(str(i + 1), ""))
        elif line.startswith("BP|STATUS|"):
            self.status_var.set(line.replace("BP|STATUS|", ""))
        elif line.startswith("BP|BOOT|"):
            self.status_var.set(line.replace("BP|BOOT|", ""))

    def send(self, command: str):
        if not self.ser or not self.ser.is_open:
            return
        try:
            self.ser.write((command.strip() + "\n").encode("utf-8"))
            self.ser.flush()
        except Exception as exc:
            self.status_var.set(f"Send failed: {exc}")

    def send_manual(self):
        command = self.command_entry.get().strip()
        if command:
            self.send(command)
            self.command_entry.delete(0, "end")

    def create_pet(self):
        slot = max(1, min(3, int(self.slot_var.get())))
        name = self.name_var.get().strip()[:12] or "Pet"
        ptype = self.type_var.get().strip()[:12] or "Unknown"
        art = self.art_var.get()[:16] or "[=^.^=]"
        if "|" in name + ptype + art:
            messagebox.showerror("BloomPetz", "The | character is reserved by the USB protocol.")
            return
        if not messagebox.askyesno("Create BloomPet", f"Create/replace slot {slot} with {name}?"):
            return
        self.send(f"CREATE {slot}|{name}|{ptype}|{art}")

    def on_close(self):
        self.disconnect()
        self.destroy()


if __name__ == "__main__":
    BloomPetzApp().mainloop()
