#!/usr/bin/env python3
"""HAPPY JARZ Controller release UI — current Fuel Gauge power telemetry layer."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

import happyjarz_controller_v0_3_2 as previous


def _read_app_version() -> str:
    version_file = Path(__file__).resolve().with_name("VERSION")
    try:
        value = version_file.read_text(encoding="utf-8").strip()
        return value or "UNKNOWN"
    except OSError:
        return "UNKNOWN"


APP_VERSION = _read_app_version()


class HappyJarzApp(previous.HappyJarzApp):
    def __init__(self):
        self.power_voltage = None
        self.power_percent = None
        self.power_usb = None
        self.power_sensor = None
        self.power_charge = None
        self.power_adc = None
        self._power_poll_started = False
        super().__init__()
        self.title(f"HAPPY JARZ Controller v{APP_VERSION}")
        self._log(f"HAPPY JARZ app v{APP_VERSION} • Fuel Gauge UI + GET POWER telemetry active")

    def _build_service_tab(self, root):
        super()._build_service_tab(root)

        if self.power_voltage is None:
            self.power_voltage = tk.StringVar(master=self, value="—")
        if self.power_percent is None:
            self.power_percent = tk.StringVar(master=self, value="—")
        if self.power_usb is None:
            self.power_usb = tk.StringVar(master=self, value="—")
        if self.power_sensor is None:
            self.power_sensor = tk.StringVar(master=self, value="WAITING")
        if self.power_charge is None:
            self.power_charge = tk.StringVar(master=self, value="HW LED")
        if self.power_adc is None:
            self.power_adc = tk.StringVar(master=self, value="—")

        outer, power = self._card(root, 9)
        outer.pack(fill="x", pady=(8, 0))

        head = ttk.Frame(power, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="FUEL GAUGE", style="Section.TLabel").pack(side="left")
        ttk.Label(head, textvariable=self.power_sensor, style="PanelMuted.TLabel").pack(side="right")

        row = ttk.Frame(power, style="Panel.TFrame")
        row.pack(fill="x", pady=(7, 0))

        items = (
            ("BATTERY", self.power_percent),
            ("VOLTAGE", self.power_voltage),
            ("USB DATA", self.power_usb),
            ("CHARGE", self.power_charge),
            ("ADC", self.power_adc),
        )
        for col, (label, var) in enumerate(items):
            box = ttk.Frame(row, style="Panel2.TFrame", padding=7)
            box.grid(row=0, column=col, sticky="nsew", padx=(0, 5) if col < len(items) - 1 else 0)
            ttk.Label(box, text=label, background=previous.previous.base.PANEL_2,
                      foreground=previous.previous.base.MUTED,
                      font=("TkDefaultFont", 8, "bold")).pack()
            ttk.Label(box, textvariable=var, style="TouchValue.TLabel").pack()
            row.columnconfigure(col, weight=1)

        footer = ttk.Frame(power, style="Panel.TFrame")
        footer.pack(fill="x", pady=(7, 0))
        ttk.Label(
            footer,
            text="Battery % is voltage-estimated. CHARGING/FULL remains hardware-only until charger status is wired to a GPIO.",
            style="PanelMuted.TLabel",
        ).pack(side="left")
        ttk.Button(footer, text="Refresh Power", style="Accent.TButton",
                   command=lambda: self.link.send("GET POWER")).pack(side="right")

    def _poll_power(self):
        try:
            if self.link.ser is not None and self.link.ser.is_open:
                self.link.send("GET POWER")
        finally:
            self.after(5000, self._poll_power)

    def _handle_line(self, line: str):
        if line.startswith("HJ|POWER|"):
            fields = self._parse_fields(line)
            sensor = fields.get("sensor", "UNKNOWN")
            if self.power_sensor is not None:
                self.power_sensor.set(sensor)

            voltage = fields.get("voltage", "")
            if self.power_voltage is not None:
                self.power_voltage.set(f"{voltage} V" if voltage else "—")

            percent = fields.get("percent", "")
            if self.power_percent is not None:
                if percent and percent != "-1":
                    self.power_percent.set(f"{percent}%")
                else:
                    self.power_percent.set("CHECK")

            if self.power_usb is not None:
                self.power_usb.set("IN" if fields.get("usb_data", "0") == "1" else "OUT")

            if self.power_charge is not None:
                charge = fields.get("charge", "HW_ONLY")
                self.power_charge.set("HW LED" if charge == "HW_ONLY" else charge)

            if self.power_adc is not None:
                adc = fields.get("adc_mv", "")
                self.power_adc.set(f"{adc} mV" if adc else "—")

            self._log(f"RX  {line}")
            return

        super()._handle_line(line)
        if line.startswith("HJ|IDENTITY|"):
            self.after(250, lambda: self.link.send("GET POWER"))
            if not self._power_poll_started:
                self._power_poll_started = True
                self.after(5000, self._poll_power)


if __name__ == "__main__":
    HappyJarzApp().mainloop()
